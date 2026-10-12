import os
import json
import requests
import datetime
from datetime import datetime as dt, time, timedelta
import pandas as pd
import numpy as np
import streamlit as st

# ==============================================================================
# 0. STREAMLIT APP CONFIGURATION (Mobile-friendly layout)
# ==============================================================================
st.set_page_config(
    page_title="Institutional Trading Dashboard",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom responsive CSS
st.markdown("""
<style>
    .main-title {
        font-size: 1.8rem;
        font-weight: 700;
        margin-bottom: 0.2rem;
    }
    .sub-title {
        color: #888888;
        font-size: 0.95rem;
        margin-bottom: 1.2rem;
    }
    .metric-card {
        background-color: #1a1c24;
        border-radius: 8px;
        padding: 12px 16px;
        border: 1px solid #2e3440;
    }
    .stButton>button {
        width: 100%;
        border-radius: 8px;
        height: 3em;
        font-weight: 600;
        background-color: #2563eb;
        color: white;
    }
</style>
""", unsafe_allow_html=True)

# ==============================================================================
# 1. SESSION STATE INITIALIZATION
# ==============================================================================
DEFAULT_AMOUNT = 300.0  # $300 risk amount per strategy

if "base44_token" not in st.session_state:
    st.session_state.base44_token = os.environ.get("BASE44_API_KEY", "")

if "strat_1_id" not in st.session_state:
    st.session_state.strat_1_id = "6acaf2a887cd7b6cb6a1267c"  # USDJPY SELFSWEEP

if "strat_2_id" not in st.session_state:
    st.session_state.strat_2_id = "6acaf29762d5f24891c0c9bc"  # GBPUSD ASIA 1.2 - 1.4 FIB RETRACMENT

if "strat_3_id" not in st.session_state:
    st.session_state.strat_3_id = "6acaf24d7a78a186a5430938"  # XAUUSD 2H 4:30/5:30 DOL

if "selected_date" not in st.session_state:
    st.session_state.selected_date = datetime.date.today()

# ==============================================================================
# 2. SIDEBAR SETTINGS
# ==============================================================================
with st.sidebar:
    st.title("⚙️ Config & Auth")
    st.markdown("Credentials persist automatically in your active session.")
    
    st.session_state.base44_token = st.text_input(
        "Base44 Personal Access Token",
        value=st.session_state.base44_token,
        type="password",
        help="Paste your Base44 bearer token here"
    )
    
    st.divider()
    st.subheader("📋 Strategy Identifiers")
    
    st.session_state.strat_1_id = st.text_input(
        "USDJPY SELFSWEEP ID",
        value=st.session_state.strat_1_id
    )
    
    st.session_state.strat_2_id = st.text_input(
        "GBPUSD ASIA FIB ID",
        value=st.session_state.strat_2_id
    )
    
    st.session_state.strat_3_id = st.text_input(
        "XAUUSD 2H DOL ID",
        value=st.session_state.strat_3_id
    )
    
    st.divider()
    st.session_state.selected_date = st.date_input(
        "Select Trading Date",
        value=st.session_state.selected_date
    )
    
    st.caption(f"Default Risk Allocation: **${DEFAULT_AMOUNT:,.2f}** per asset")

# ==============================================================================
# 3. BASE44 TRADE JOURNAL API INTEGRATION
# ==============================================================================
BASE44_API_URL = "https://trading-journal-2-0.base44.app/api/entities/Trade"

def check_duplicate_trade(api_key: str, strategy_id: str, symbol: str, trade_date: datetime.date) -> bool:
    """Queries Base44 to check if a trade has already been logged for strategy_id & symbol on trade_date."""
    if not api_key:
        return False
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    # Query parameter format specified by Base44
    params = {"q": f'{{"strategy_id": "{strategy_id}", "symbol": "{symbol}"}}'}
    
    try:
        resp = requests.get(BASE44_API_URL, headers=headers, params=params, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            items = data.get("items", []) if isinstance(data, dict) else (data if isinstance(data, list) else [])
            date_str = trade_date.isoformat()
            for item in items:
                entry_ts = str(item.get("entry_timestamp", ""))
                if entry_ts.startswith(date_str):
                    return True
        return False
    except Exception as e:
        print(f"Error checking duplicate: {e}")
        return False

def sync_trade_to_base44(api_key: str, strategy_id: str, trade_info: dict) -> tuple[str, str]:
    """Logs the trade into Base44 Trade Journal using the exact schema specified."""
    if not api_key:
        return "Not Connected", "Base44 Personal Access Token not provided in sidebar."
    
    symbol = trade_info["symbol"]
    direction = trade_info["direction"]
    entry_price = float(trade_info["entry_price"])
    sl_pct = trade_info["sl_percentage"]
    tp_pct = trade_info["tp_percentage"]
    trade_date = trade_info.get("date", datetime.date.today())
    
    # A. Check Duplicate
    if check_duplicate_trade(api_key, strategy_id, symbol, trade_date):
        return "Skipped (Duplicate)", f"Trade already logged for {symbol} on {trade_date}."
    
    # B. Record Entry (POST)
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "strategy_id": strategy_id,
        "symbol": symbol,
        "direction": direction.lower(),
        "buy_price": float(entry_price),
        "quantity": 1,
        "entry_timestamp": dt.utcnow().isoformat() + "Z",
        "status": "open",
        "notes": f"{sl_pct}% SL , {tp_pct}% TP"
    }
    
    try:
        resp = requests.post(BASE44_API_URL, headers=headers, json=payload, timeout=10)
        if resp.status_code in [200, 201]:
            return "Success", f"Logged {symbol} {direction.upper()} @ {entry_price}"
        else:
            return "Error", f"HTTP {resp.status_code}: {resp.text}"
    except Exception as e:
        return "Error", f"Request exception: {str(e)}"

# ==============================================================================
# 4. STRATEGY EXECUTION ENGINES
# ==============================================================================

# Helper for US DST
def is_us_dst(dt_utc):
    year = dt_utc.year
    d_mar = dt(year, 3, 1)
    mar_second_sun = 1 + (6 - d_mar.weekday() + 7) % 7 + 7
    dst_start = dt(year, 3, mar_second_sun, 7, 0)
    d_nov = dt(year, 11, 1)
    nov_first_sun = 1 + (6 - d_nov.weekday()) % 7
    dst_end = dt(year, 11, nov_first_sun, 6, 0)
    return dst_start <= dt_utc < dst_end

# ------------------------------------------------------------------------------
# Strategy 1: USDJPY SELFSWEEP
# ------------------------------------------------------------------------------
def run_usdjpy_strategy(target_date: datetime.date) -> dict:
    """
    USDJPY Selfsweep Strategy:
    - M15 Session extremes, filtered with 1:5.0 target and No BE
    - Day Filter: No Tuesdays
    - SL Range: 0.045% to 0.154%
    """
    result_template = {
        "strategy_name": "USDJPY SELFSWEEP",
        "symbol": "USDJPY",
        "date": target_date,
        "direction": "none",
        "entry_price": 0.0,
        "sl_price": 0.0,
        "tp_price": 0.0,
        "sl_percentage": 0.0,
        "tp_percentage": 0.0,
        "status": "No Trade Setup",
        "details": ""
    }
    
    # Rule 1: No Tuesdays
    if target_date.weekday() == 1:
        result_template["status"] = "Skipped (Tuesday Rule)"
        result_template["details"] = "Tuesday is strictly excluded by base champion rule."
        return result_template
        
    csv_file = "USDJPY_M15_2024-03_to_2026-09.csv"
    if not os.path.exists(csv_file):
        result_template["status"] = "Data File Missing"
        result_template["details"] = f"{csv_file} not found in workspace."
        return result_template
        
    try:
        # Load date slice
        df = pd.read_csv(csv_file)
        df['dt_ist'] = pd.to_datetime(df['time_ist'])
        day_df = df[df['dt_ist'].dt.date == target_date].sort_values('dt_ist').reset_index(drop=True)
        
        if len(day_df) < 8:
            result_template["status"] = "No Session Data"
            result_template["details"] = f"Insufficient candles for {target_date}."
            return result_template
            
        # Determine DST
        sample_utc = pd.to_datetime(day_df['time_utc'].iloc[0])
        is_summer = is_us_dst(sample_utc)
        
        # Session filters
        t_col = day_df['dt_ist'].dt.time
        if is_summer:
            cond_asia = (t_col >= time(5, 30)) & (t_col <= time(9, 0))
            cond_london = (t_col >= time(11, 30)) & (t_col <= time(14, 0))
        else:
            cond_asia = (t_col >= time(6, 30)) & (t_col <= time(10, 0))
            cond_london = (t_col >= time(12, 30)) & (t_col <= time(15, 0))
            
        # Scan for selfsweep trigger
        for s_name, cond in [("ASIA", cond_asia), ("LONDON", cond_london)]:
            s_df = day_df[cond].reset_index(drop=True)
            N = len(s_df)
            if N < 4: continue
            
            opens, highs, lows, closes = s_df['open'].values, s_df['high'].values, s_df['low'].values, s_df['close'].values
            
            # Long Check
            ext_low, ceiling, state = lows[0], highs[0], 'SEEK_CC'
            for i in range(1, N):
                c_o, c_h, c_l, c_c = opens[i], highs[i], lows[i], closes[i]
                if state == 'SEEK_CC':
                    if c_l <= ext_low: ext_low, ceiling = c_l, c_h
                    else:
                        if c_c > ceiling: state = 'WAIT_SUSTAIN'
                        ceiling = max(ceiling, c_h)
                elif state == 'WAIT_SUSTAIN':
                    if c_l <= ext_low: ext_low, ceiling, state = c_l, c_h, 'SEEK_CC'
                    else: state = 'WAIT_SWEEP'
                elif state == 'WAIT_SWEEP':
                    if c_l <= ext_low - 0.001:
                        if c_c <= ext_low: ext_low, ceiling, state = c_l, c_h, 'SEEK_CC'
                        else:
                            if c_c > c_o:
                                body = c_c - c_o
                                l_wick = c_o - c_l
                                ratio_ok = (body >= 0.002) if (l_wick >= 0.100) else (body >= 0.003)
                                if ratio_ok:
                                    # Candidate Long Found
                                    entry = c_c
                                    init_sl = c_l
                                    sl_pct = (abs(entry - init_sl) / entry) * 100.0
                                    if 0.045 <= sl_pct <= 0.154:
                                        buffer_p = 0.006 + max(0, int((sl_pct - 0.055) / 0.010)) * 0.001
                                        ext_sl = init_sl - buffer_p
                                        risk = entry - ext_sl
                                        tp = entry + 5.0 * risk
                                        result_template.update({
                                            "direction": "long",
                                            "entry_price": round(entry, 3),
                                            "sl_price": round(ext_sl, 3),
                                            "tp_price": round(tp, 3),
                                            "sl_percentage": round(sl_pct, 3),
                                            "tp_percentage": round(sl_pct * 5.0, 3),
                                            "status": f"Active Signal ({s_name} Long)",
                                            "details": f"Confirmed M15 Selfsweep in {s_name} session."
                                        })
                                        return result_template
                                    
            # Short Check
            ext_high, floor, state = highs[0], lows[0], 'SEEK_CC'
            for i in range(1, N):
                c_o, c_h, c_l, c_c = opens[i], highs[i], lows[i], closes[i]
                if state == 'SEEK_CC':
                    if c_h >= ext_high: ext_high, floor = c_h, c_l
                    else:
                        if c_c < floor: state = 'WAIT_SUSTAIN'
                        floor = min(floor, c_l)
                elif state == 'WAIT_SUSTAIN':
                    if c_h >= ext_high: ext_high, floor, state = c_h, c_l, 'SEEK_CC'
                    else: state = 'WAIT_SWEEP'
                elif state == 'WAIT_SWEEP':
                    if c_h >= ext_high + 0.001:
                        if c_c >= ext_high: ext_high, floor, state = c_h, c_l, 'SEEK_CC'
                        else:
                            if c_c < c_o:
                                body = c_o - c_c
                                u_wick = c_h - c_o
                                ratio_ok = (body >= 0.002) if (u_wick >= 0.100) else (body >= 0.003)
                                if ratio_ok:
                                    entry = c_c
                                    init_sl = c_h
                                    sl_pct = (abs(entry - init_sl) / entry) * 100.0
                                    if 0.045 <= sl_pct <= 0.154:
                                        buffer_p = 0.006 + max(0, int((sl_pct - 0.055) / 0.010)) * 0.001
                                        ext_sl = init_sl + buffer_p
                                        risk = ext_sl - entry
                                        tp = entry - 5.0 * risk
                                        result_template.update({
                                            "direction": "short",
                                            "entry_price": round(entry, 3),
                                            "sl_price": round(ext_sl, 3),
                                            "tp_price": round(tp, 3),
                                            "sl_percentage": round(sl_pct, 3),
                                            "tp_percentage": round(sl_pct * 5.0, 3),
                                            "status": f"Active Signal ({s_name} Short)",
                                            "details": f"Confirmed M15 Selfsweep in {s_name} session."
                                        })
                                        return result_template
        return result_template
    except Exception as e:
        result_template["status"] = "Error"
        result_template["details"] = str(e)
        return result_template

# ------------------------------------------------------------------------------
# Strategy 2: GBPUSD ASIA 1.2 - 1.4 FIB RETRACEMENT (GodMode)
# ------------------------------------------------------------------------------
def run_gbpusd_strategy(target_date: datetime.date) -> dict:
    """
    GBPUSD Asian Fib Strategy (GodMode):
    - Asian Range 05:30-09:30 IST
    - Pre-London Gap Invalidation (09:45-11:15 IST)
    - London Entry Window (11:30-14:30 IST)
    - 1:3.75 Target, No BE
    - SL: 0.035% to 0.154%
    """
    result_template = {
        "strategy_name": "GBPUSD ASIA 1.2 - 1.4 FIB RETRACMENT",
        "symbol": "GBPUSD",
        "date": target_date,
        "direction": "none",
        "entry_price": 0.0,
        "sl_price": 0.0,
        "tp_price": 0.0,
        "sl_percentage": 0.0,
        "tp_percentage": 0.0,
        "status": "No Trade Setup",
        "details": ""
    }
    
    csv_file = "GBPUSD_2YEARS.csv"
    if not os.path.exists(csv_file):
        result_template["status"] = "Data File Missing"
        result_template["details"] = f"{csv_file} not found in workspace."
        return result_template
        
    try:
        df = pd.read_csv(csv_file)
        df.columns = [c.strip().lower() for c in df.columns]
        time_col = 'time' if 'time' in df.columns else ('timestamp' if 'timestamp' in df.columns else df.columns[0])
        df['dt'] = pd.to_datetime(df[time_col])
        day_df = df[df['dt'].dt.date == target_date].sort_values('dt').reset_index(drop=True)
        
        if len(day_df) < 12:
            result_template["status"] = "No Session Data"
            result_template["details"] = f"Insufficient candles for {target_date}."
            return result_template
            
        t_col = day_df['dt'].dt.time
        asia_df = day_df[(t_col >= time(5, 30)) & (t_col <= time(9, 30))]
        if len(asia_df) < 4:
            result_template["status"] = "No Asia Range"
            result_template["details"] = "Asian range incomplete."
            return result_template
            
        asia_high = asia_df['high'].max()
        asia_low = asia_df['low'].min()
        asia_open = asia_df.iloc[0]['open']
        asia_close = asia_df.iloc[-1]['close']
        rng = asia_high - asia_low
        
        if rng <= 0.0005:
            result_template["status"] = "Flat Asian Range"
            result_template["details"] = f"Asian range too tight: {rng:.5f}"
            return result_template
            
        # Directional bias
        is_asia_bearish = asia_close < asia_open
        direction = "long" if is_asia_bearish else "short"
        
        # Fibonacci levels
        if direction == "long":
            level_sweep = asia_low - 0.20 * rng
            level_inval = asia_high + 0.20 * rng
        else:
            level_sweep = asia_high + 0.20 * rng
            level_inval = asia_low - 0.20 * rng
            
        # Gap filter (09:45 to 11:15 IST)
        gap_df = day_df[(t_col >= time(9, 45)) & (t_col <= time(11, 15))]
        if len(gap_df) > 0:
            if direction == "long":
                if gap_df['low'].min() <= level_sweep or gap_df['high'].max() >= level_inval:
                    result_template["status"] = "Skipped (Gap Invalidation)"
                    result_template["details"] = "Level touched during pre-London gap."
                    return result_template
            else:
                if gap_df['high'].max() >= level_sweep or gap_df['low'].min() <= level_inval:
                    result_template["status"] = "Skipped (Gap Invalidation)"
                    result_template["details"] = "Level touched during pre-London gap."
                    return result_template
                    
        # London Entry Window (11:30 to 14:30 IST)
        lon_df = day_df[(t_col >= time(11, 30)) & (t_col <= time(14, 30))].reset_index(drop=True)
        for idx, row in lon_df.iterrows():
            c_o, c_h, c_l, c_c = row['open'], row['high'], row['low'], row['close']
            if direction == "long" and c_l <= level_sweep and c_c > level_sweep:
                entry = c_c
                sl = c_l - 0.00002
                sl_pct = (abs(entry - sl) / entry) * 100.0
                if 0.035 <= sl_pct <= 0.154:
                    risk = entry - sl
                    tp = entry + 3.75 * risk
                    result_template.update({
                        "direction": "long",
                        "entry_price": round(entry, 5),
                        "sl_price": round(sl, 5),
                        "tp_price": round(tp, 5),
                        "sl_percentage": round(sl_pct, 3),
                        "tp_percentage": round(sl_pct * 3.75, 3),
                        "status": "Active Signal (London Long)",
                        "details": f"Level -0.2 swept ({level_sweep:.5f}) & rejected."
                    })
                    return result_template
            elif direction == "short" and c_h >= level_sweep and c_c < level_sweep:
                entry = c_c
                sl = c_h + 0.00002
                sl_pct = (abs(entry - sl) / entry) * 100.0
                if 0.035 <= sl_pct <= 0.154:
                    risk = sl - entry
                    tp = entry - 3.75 * risk
                    result_template.update({
                        "direction": "short",
                        "entry_price": round(entry, 5),
                        "sl_price": round(sl, 5),
                        "tp_price": round(tp, 5),
                        "sl_percentage": round(sl_pct, 3),
                        "tp_percentage": round(sl_pct * 3.75, 3),
                        "status": "Active Signal (London Short)",
                        "details": f"Level -0.2 swept ({level_sweep:.5f}) & rejected."
                    })
                    return result_template
        return result_template
    except Exception as e:
        result_template["status"] = "Error"
        result_template["details"] = str(e)
        return result_template

# ------------------------------------------------------------------------------
# Strategy 3: XAUUSD 2H 4:30/5:30 DOL
# ------------------------------------------------------------------------------
def run_xauusd_strategy(target_date: datetime.date) -> dict:
    """
    XAUUSD 2H DOL Strategy:
    - 2H morning structure (18:00 NY / 06:30 IST)
    - Clean & Swept Breakouts with 1:3.30 RRR and BE @ 2.5R
    - SL Range: 0.165% to 0.994%
    - Thursday Skipped
    """
    result_template = {
        "strategy_name": "XAUUSD 2H 4:30/5:30 DOL",
        "symbol": "XAUUSD",
        "date": target_date,
        "direction": "none",
        "entry_price": 0.0,
        "sl_price": 0.0,
        "tp_price": 0.0,
        "sl_percentage": 0.0,
        "tp_percentage": 0.0,
        "status": "No Trade Setup",
        "details": ""
    }
    
    # Rule: Thursday skipped
    if target_date.weekday() == 3:
        result_template["status"] = "Skipped (Thursday Rule)"
        result_template["details"] = "Thursday is strictly skipped by base strategy."
        return result_template
        
    csv_file = "XAUUSD_1M_Sep2024_Sep2026.csv"
    if not os.path.exists(csv_file):
        result_template["status"] = "Data File Missing"
        result_template["details"] = f"{csv_file} not found in workspace."
        return result_template
        
    try:
        df = pd.read_csv(csv_file)
        df['time_utc'] = pd.to_datetime(df['time_utc'], utc=True)
        df['time_ny'] = df['time_utc'].dt.tz_convert('America/New_York')
        
        # P = 18:00 to 18:59 NY, S = 19:00 to 20:59 NY
        day_p = df[(df['time_ny'].dt.date == target_date) & (df['time_ny'].dt.hour == 18)]
        day_s = df[(df['time_ny'].dt.date == target_date) & (df['time_ny'].dt.hour.isin([19, 20]))]
        
        if len(day_p) < 20 or len(day_s) < 40:
            result_template["status"] = "No Session Data"
            result_template["details"] = f"Insufficient 2H DOL candles for {target_date}."
            return result_template
            
        p_high, p_low = day_p['high'].max(), day_p['low'].min()
        s_open = day_s.iloc[0]['open']
        s_close = day_s.iloc[-1]['close']
        s_high, s_low = day_s['high'].max(), day_s['low'].min()
        
        # Invalidation check
        if s_open <= p_low or s_open >= p_high:
            result_template["status"] = "Skipped (Invalid Open)"
            result_template["details"] = "S open opened outside P range."
            return result_template
            
        is_bullish = s_close > s_open
        is_bearish = s_close < s_open
        swept_high = s_high > p_high
        swept_low = s_low < p_low
        
        trade_dir = None
        sl_raw = None
        rule_name = ""
        
        if s_close > p_high and is_bullish:
            trade_dir = "long"
            sl_raw = s_low
            rule_name = "BULL BREAKOUT CLEAN" if not swept_low else "BULL BREAKOUT SWEPT"
        elif s_close < p_low and is_bearish:
            trade_dir = "short"
            sl_raw = s_high
            rule_name = "BEAR BREAKOUT CLEAN" if not swept_high else "BEAR BREAKOUT SWEPT"
        elif swept_low and s_close > p_low:
            # Rule 7 is blacklisted, but check if user wants base
            trade_dir = "long"
            sl_raw = s_low
            rule_name = "BULL SWEEP REJECTION"
        elif swept_high and s_close < p_high:
            trade_dir = "short"
            sl_raw = s_high
            rule_name = "BEAR SWEEP REJECTION"
            
        if not trade_dir:
            return result_template
            
        # Entry price is open of next candle
        entry = s_close
        if trade_dir == "long":
            ext_sl = sl_raw * (1.0 - 0.0001)
            raw_diff = entry - sl_raw
            sl_pct = (raw_diff / entry) * 100.0
            tp = entry + 3.30 * (entry - ext_sl)
        else:
            ext_sl = sl_raw * (1.0 + 0.0001)
            raw_diff = sl_raw - entry
            sl_pct = (raw_diff / entry) * 100.0
            tp = entry - 3.30 * (ext_sl - entry)
            
        if 0.165 <= sl_pct <= 0.994:
            result_template.update({
                "direction": trade_dir,
                "entry_price": round(entry, 2),
                "sl_price": round(ext_sl, 2),
                "tp_price": round(tp, 2),
                "sl_percentage": round(sl_pct, 3),
                "tp_percentage": round(sl_pct * 3.30, 3),
                "status": f"Active Signal ({rule_name})",
                "details": f"2H DOL confirmed: {rule_name}"
            })
            return result_template
        else:
            result_template["status"] = "Skipped (SL Out of Range)"
            result_template["details"] = f"SL {sl_pct:.3f}% outside 0.165% - 0.994% corridor."
            return result_template
    except Exception as e:
        result_template["status"] = "Error"
        result_template["details"] = str(e)
        return result_template

# ==============================================================================
# 5. MAIN DASHBOARD VIEW
# ==============================================================================
st.markdown('<div class="main-title">📊 Multi-Strategy Trade Execution Dashboard</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-title">Real-time daily evaluation and automated syncing with Base44 Trade Journal</div>', unsafe_allow_html=True)

# Top KPI Summary Cards
kpi1, kpi2, kpi3, kpi4 = st.columns(4)
with kpi1:
    st.metric("Strategy 1", "USDJPY", "1:5.0 RRR | No BE")
with kpi2:
    st.metric("Strategy 2", "GBPUSD", "1:3.75 RRR | No BE")
with kpi3:
    st.metric("Strategy 3", "XAUUSD", "1:3.30 RRR | BE @ 2.5R")
with kpi4:
    conn_status = "🟢 Connected" if st.session_state.base44_token else "🔴 Auth Token Required"
    st.metric("Base44 API", conn_status)

st.markdown("---")

# Execution Action Button
run_clicked = st.button("🚀 Run Strategies & Sync to Base44", type="primary")

if run_clicked:
    date_val = st.session_state.selected_date
    st.info(f"🔍 Evaluating institutional models for **{date_val.strftime('%A, %B %d, %Y')}**...")
    
    with st.spinner("Executing candle analysis across USDJPY, GBPUSD, and XAUUSD..."):
        res_usdjpy = run_usdjpy_strategy(date_val)
        res_gbpusd = run_gbpusd_strategy(date_val)
        res_xauusd = run_xauusd_strategy(date_val)
        
    trades_list = [res_usdjpy, res_gbpusd, res_xauusd]
    strat_ids = [
        st.session_state.strat_1_id,
        st.session_state.strat_2_id,
        st.session_state.strat_3_id
    ]
    
    sync_results = []
    
    # Process Base44 sync
    for trade, s_id in zip(trades_list, strat_ids):
        if trade["direction"] in ["long", "short"]:
            status_text, msg = sync_trade_to_base44(st.session_state.base44_token, s_id, trade)
            sync_results.append({
                "Strategy": trade["strategy_name"],
                "Symbol": trade["symbol"],
                "Signal": trade["direction"].upper(),
                "Entry": trade["entry_price"],
                "SL%": f"{trade['sl_percentage']}%",
                "TP%": f"{trade['tp_percentage']}%",
                "Default Risk": f"${DEFAULT_AMOUNT:,.2f}",
                "Base44 Sync": status_text,
                "API Message": msg
            })
            if status_text == "Success":
                st.toast(f"✅ {trade['symbol']} {trade['direction'].upper()} trade successfully logged to Base44!", icon="🎯")
            elif status_text == "Skipped (Duplicate)":
                st.toast(f"ℹ️ {trade['symbol']} already exists in Base44 journal (skipped duplicate).", icon="🛡️")
            elif status_text == "Error":
                st.error(f"❌ Failed to sync {trade['symbol']}: {msg}")
        else:
            sync_results.append({
                "Strategy": trade["strategy_name"],
                "Symbol": trade["symbol"],
                "Signal": "NO TRADE",
                "Entry": "-",
                "SL%": "-",
                "TP%": "-",
                "Default Risk": f"${DEFAULT_AMOUNT:,.2f}",
                "Base44 Sync": "N/A (No Setup)",
                "API Message": trade["status"] + f" ({trade['details']})"
            })
            
    st.subheader(f"📋 Signals Summary for {date_val.strftime('%Y-%m-%d')}")
    summary_df = pd.DataFrame(sync_results)
    
    # Styled display
    def highlight_signals(val):
        if val == "LONG":
            return "background-color: #065f46; color: white; font-weight: bold;"
        elif val == "SHORT":
            return "background-color: #991b1b; color: white; font-weight: bold;"
        elif val == "Success":
            return "color: #10b981; font-weight: bold;"
        elif val == "Skipped (Duplicate)":
            return "color: #f59e0b; font-weight: bold;"
        elif val == "Error":
            return "color: #ef4444; font-weight: bold;"
        return ""
        
    styled_df = summary_df.style.map(highlight_signals)
    st.dataframe(styled_df, use_container_width=True, hide_index=True)
    
    with st.expander("🔍 Deep Candle Execution & Invalidation Breakdown", expanded=True):
        col1, col2, col3 = st.columns(3)
        for col, t in zip([col1, col2, col3], trades_list):
            with col:
                st.markdown(f"### {t['symbol']}")
                st.markdown(f"**Strategy:** {t['strategy_name']}")
                st.markdown(f"**Setup Status:** `{t['status']}`")
                if t['direction'] in ['long', 'short']:
                    st.markdown(f"**Direction:** :{'green' if t['direction']=='long' else 'red'}[**{t['direction'].upper()}**]")
                    st.markdown(f"**Entry Price:** `{t['entry_price']}`")
                    st.markdown(f"**Stop Loss:** `{t['sl_price']}` ({t['sl_percentage']}%)")
                    st.markdown(f"**Take Profit:** `{t['tp_price']}` ({t['tp_percentage']}%)")
                st.caption(f"**Technical Note:** {t['details']}")

else:
    st.info("💡 Select your desired date from the sidebar and click **'🚀 Run Strategies & Sync to Base44'** to analyze candle setups.")
