import os
import json
import base64
import requests
import datetime
from datetime import datetime as dt, time, timedelta, timezone
import pandas as pd
import numpy as np
import streamlit as st

# ==============================================================================
# 0. STREAMLIT APP CONFIGURATION (Mobile-friendly layout)
# ==============================================================================
LOGO_PATH = os.path.join(os.path.dirname(__file__), "app_logo.png")

st.set_page_config(
    page_title="Institutional Trading Terminal",
    page_icon=LOGO_PATH if os.path.exists(LOGO_PATH) else "📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

if os.path.exists(LOGO_PATH) and hasattr(st, "logo"):
    try:
        st.logo(LOGO_PATH, icon_image=LOGO_PATH)
    except Exception:
        pass

# Custom premium & mobile-first responsive CSS
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');

    html, body, [class*="css"] {
        font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    }

    /* Mobile Header & Typography */
    .dashboard-header {
        background: linear-gradient(135deg, rgba(30, 41, 59, 0.7) 0%, rgba(15, 23, 42, 0.9) 100%);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 16px;
        padding: 20px 24px;
        margin-bottom: 20px;
        box-shadow: 0 10px 30px -10px rgba(0, 0, 0, 0.5);
        backdrop-filter: blur(12px);
    }
    .main-title {
        font-size: 1.6rem;
        font-weight: 800;
        letter-spacing: -0.02em;
        background: linear-gradient(135deg, #ffffff 0%, #cbd5e1 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 6px;
    }
    .sub-title {
        color: #94a3b8;
        font-size: 0.9rem;
        margin-bottom: 0;
        line-height: 1.4;
    }

    /* Touch-friendly Large Buttons */
    .stButton>button {
        width: 100% !important;
        border-radius: 14px !important;
        min-height: 52px !important;
        font-size: 1.05rem !important;
        font-weight: 700 !important;
        background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%) !important;
        color: #ffffff !important;
        border: 1px solid rgba(255, 255, 255, 0.15) !important;
        box-shadow: 0 4px 18px 0 rgba(37, 99, 235, 0.45) !important;
        transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1) !important;
        margin-top: 10px !important;
    }
    .stButton>button:active {
        transform: scale(0.98) !important;
        filter: brightness(0.95);
    }

    /* Metric & Control Cards */
    .glass-card {
        background: rgba(17, 24, 39, 0.7);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 14px;
        padding: 16px 18px;
        backdrop-filter: blur(10px);
        margin-bottom: 14px;
    }
    
    /* Trade Card for Mobile */
    .trade-card {
        background: linear-gradient(145deg, #1e293b 0%, #0f172a 100%);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 16px;
        padding: 18px;
        margin-bottom: 14px;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.25);
    }
    .badge-long {
        background: #065f46;
        color: #34d399;
        font-weight: 800;
        padding: 4px 10px;
        border-radius: 20px;
        font-size: 0.8rem;
        display: inline-block;
        border: 1px solid rgba(52, 211, 153, 0.3);
    }
    .badge-short {
        background: #881337;
        color: #fb7185;
        font-weight: 800;
        padding: 4px 10px;
        border-radius: 20px;
        font-size: 0.8rem;
        display: inline-block;
        border: 1px solid rgba(251, 113, 133, 0.3);
    }
    .badge-sync {
        background: #1e1b4b;
        color: #818cf8;
        font-weight: 700;
        padding: 4px 10px;
        border-radius: 20px;
        font-size: 0.78rem;
        display: inline-block;
        border: 1px solid rgba(129, 140, 248, 0.3);
    }

    /* Android & Mobile Specific Layout Adjustments */
    @media (max-width: 768px) {
        .main-title {
            font-size: 1.35rem !important;
        }
        .dashboard-header {
            padding: 16px !important;
            border-radius: 14px !important;
        }
        div[data-testid="column"] {
            min-width: 100% !important;
            flex: 1 1 100% !important;
            margin-bottom: 8px !important;
        }
        .stMetric {
            background: rgba(30, 41, 59, 0.6) !important;
            border: 1px solid rgba(255, 255, 255, 0.06) !important;
            border-radius: 12px !important;
            padding: 12px 14px !important;
        }
    }
</style>
""", unsafe_allow_html=True)

# ==============================================================================
# 1. SESSION STATE INITIALIZATION
# ==============================================================================
DEFAULT_AMOUNT = 300.0  # $300 risk amount per strategy

if "base44_token" not in st.session_state:
    st.session_state.base44_token = os.environ.get(
        "BASE44_API_KEY", 
        "b44u_a42da4afa13a09294364b826325610580674a3365e53e3676ba7693e42240d8f"
    )

if "oanda_token" not in st.session_state:
    st.session_state.oanda_token = os.environ.get(
        "OANDA_TOKEN", 
        "f2b74d1cee1eb5488ba8b6b067e3ffc6-b6ccbdca86ea9ddb162f03996341ae91"
    )

if "oanda_env" not in st.session_state:
    st.session_state.oanda_env = "practice"  # 'practice' or 'trade' (live)

if "strat_1_id" not in st.session_state:
    st.session_state.strat_1_id = "6acaf2a887cd7b6cb6a1267c"  # USDJPY SELFSWEEP

if "strat_2_id" not in st.session_state:
    st.session_state.strat_2_id = "6acaf29762d5f24891c0c9bc"  # GBPUSD ASIA 1.2 - 1.4 FIB RETRACMENT

if "strat_3_id" not in st.session_state:
    st.session_state.strat_3_id = "6acaf24d7a78a186a5430938"  # XAUUSD 2H 4:30/5:30 DOL

if "date_mode" not in st.session_state:
    st.session_state.date_mode = "Single Day"

if "single_date" not in st.session_state:
    st.session_state.single_date = datetime.date.today()

if "start_date" not in st.session_state:
    st.session_state.start_date = datetime.date.today() - timedelta(days=7)

if "end_date" not in st.session_state:
    st.session_state.end_date = datetime.date.today()

# ==============================================================================
# 2. SIDEBAR SETTINGS (MOBILE COMPACT & CLEAN)
# ==============================================================================
with st.sidebar:
    if os.path.exists(LOGO_PATH):
        st.image(LOGO_PATH, width=90)
    st.markdown("### ⚙️ Engine Settings")
    st.caption("Settings persist across session navigations.")
    
    st.session_state.base44_token = st.text_input(
        "Base44 Personal Access Token",
        value=st.session_state.base44_token,
        type="password",
        help="Paste your Base44 bearer token here"
    )
    
    st.divider()
    st.subheader("🌐 Live Broker Feed (OANDA API)")
    st.session_state.oanda_token = st.text_input(
        "OANDA API Token",
        value=st.session_state.oanda_token,
        type="password",
        help="Connects to OANDA for real-time live candles"
    )
    st.session_state.oanda_env = st.selectbox(
        "OANDA Environment",
        ["practice", "trade (live)"],
        index=0 if st.session_state.oanda_env == "practice" else 1
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
    st.caption(f"Default Risk Allocation: **${DEFAULT_AMOUNT:,.2f}** per trade")

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
    
    trade_dt = dt.combine(trade_date, time(12, 0, 0)) if trade_date != datetime.date.today() else dt.now(timezone.utc)
    ts_str = trade_dt.strftime("%Y-%m-%dT%H:%M:%SZ") if trade_date != datetime.date.today() else (dt.utcnow().isoformat() + "Z")
    payload = {
        "strategy_id": strategy_id,
        "symbol": symbol,
        "direction": direction.lower(),
        "buy_price": float(entry_price),
        "quantity": 1,
        "entry_timestamp": ts_str,
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
# 4. OANDA LIVE CANDLE FETCHING & CSV FALLBACK
# ==============================================================================
def get_oanda_base_url():
    token = st.session_state.oanda_token if "oanda_token" in st.session_state else ""
    env = st.session_state.oanda_env if "oanda_env" in st.session_state else "practice"
    if "live" in env.lower():
        return "https://api-fxtrade.oanda.com/v3"
    return "https://api-fxpractice.oanda.com/v3"

def is_us_dst(dt_utc):
    year = dt_utc.year
    d_mar = dt(year, 3, 1)
    mar_second_sun = 1 + (6 - d_mar.weekday() + 7) % 7 + 7
    dst_start = dt(year, 3, mar_second_sun, 7, 0, tzinfo=timezone.utc if dt_utc.tzinfo else None)
    d_nov = dt(year, 11, 1)
    nov_first_sun = 1 + (6 - d_nov.weekday()) % 7
    dst_end = dt(year, 11, nov_first_sun, 6, 0, tzinfo=timezone.utc if dt_utc.tzinfo else None)
    return dst_start <= dt_utc < dst_end

def fetch_oanda_candles(instrument: str, granularity: str, target_date: datetime.date) -> pd.DataFrame:
    """
    Fetches candles for target_date from OANDA API with timezone conversions (UTC, IST, NY).
    Handles past dates and live current-day streaming without future-time errors.
    """
    token = st.session_state.oanda_token if "oanda_token" in st.session_state else os.environ.get("OANDA_TOKEN", "f2b74d1cee1eb5488ba8b6b067e3ffc6-b6ccbdca86ea9ddb162f03996341ae91")
    if not token:
        return pd.DataFrame()
        
    base_url = get_oanda_base_url()
    headers = {"Authorization": f"Bearer {token}"}
    
    # Start from previous day 00:00 UTC to ensure full Asian/London sessions are captured
    start_utc = dt(target_date.year, target_date.month, target_date.day, 0, 0, 0, tzinfo=timezone.utc) - timedelta(days=1)
    now_utc = dt.now(timezone.utc)
    
    params = {
        "granularity": granularity,
        "price": "M",
        "from": start_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
    }
    
    # If target date is in the past, add bounded 'to' timestamp
    target_end_utc = dt(target_date.year, target_date.month, target_date.day, 23, 59, 59, tzinfo=timezone.utc)
    if target_end_utc < now_utc:
        params["to"] = target_end_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
        
    try:
        url = f"{base_url}/instruments/{instrument}/candles"
        r = requests.get(url, headers=headers, params=params, timeout=12)
        if r.status_code == 200:
            raw_candles = r.json().get("candles", [])
            records = []
            for c in raw_candles:
                t_str = c["time"][:19] + "Z"
                t_utc = dt.strptime(t_str, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
                records.append({
                    "time_utc": t_utc,
                    "open": float(c["mid"]["o"]),
                    "high": float(c["mid"]["h"]),
                    "low": float(c["mid"]["l"]),
                    "close": float(c["mid"]["c"]),
                    "complete": c.get("complete", True)
                })
            df = pd.DataFrame(records)
            if not df.empty:
                df["dt_ist"] = df["time_utc"].apply(lambda t: t.astimezone(timezone(timedelta(hours=5, minutes=30))))
                df["dt_ny"] = df["time_utc"].apply(lambda t: t.astimezone(timezone(timedelta(hours=-4 if is_us_dst(t) else -5))))
                return df
    except Exception as e:
        print(f"OANDA fetch error for {instrument}: {e}")
    return pd.DataFrame()

# ==============================================================================
# 5. STRATEGY EXECUTION ENGINES
# ==============================================================================

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
        "details": "",
        "data_source": "OANDA Live API"
    }
    
    # Rule 1: No Tuesdays
    if target_date.weekday() == 1:
        result_template["status"] = "Skipped (Tuesday Rule)"
        result_template["details"] = "Tuesday is strictly excluded by base champion rule."
        return result_template
        
    # 1. Try OANDA Live API first
    day_df = pd.DataFrame()
    live_df = fetch_oanda_candles("USD_JPY", "M15", target_date)
    if not live_df.empty:
        day_df = live_df[live_df['dt_ist'].dt.date == target_date].sort_values('dt_ist').reset_index(drop=True)
        result_template["data_source"] = "OANDA Live Feed"
    
    # 2. Fallback to Local CSV if API returned empty
    if day_df.empty:
        csv_file = "USDJPY_M15_2024-03_to_2026-09.csv"
        if os.path.exists(csv_file):
            df = pd.read_csv(csv_file)
            df['dt_ist'] = pd.to_datetime(df['time_ist'])
            day_df = df[df['dt_ist'].dt.date == target_date].sort_values('dt_ist').reset_index(drop=True)
            result_template["data_source"] = "Local Archive CSV"
            
    if day_df.empty or len(day_df) < 4:
        result_template["status"] = "No Session Data"
        result_template["details"] = f"No M15 candles available for {target_date}."
        return result_template
        
    try:
        sample_utc = pd.to_datetime(day_df['time_utc'].iloc[0])
        is_summer = is_us_dst(sample_utc)
        
        # Session filters (IST)
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
                                    entry = c_c
                                    init_sl = c_l
                                    sl_pct = (abs(entry - init_sl) / entry) * 100.0
                                    if 0.015 <= sl_pct <= 0.154:
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
                                    if 0.015 <= sl_pct <= 0.154:
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
        "details": "",
        "data_source": "OANDA Live API"
    }
    
    # 1. Fetch live OANDA candles
    day_df = pd.DataFrame()
    live_df = fetch_oanda_candles("GBP_USD", "M15", target_date)
    if not live_df.empty:
        day_df = live_df[live_df['dt_ist'].dt.date == target_date].sort_values('dt_ist').reset_index(drop=True)
        result_template["data_source"] = "OANDA Live Feed"
        
    # 2. Local CSV fallback
    if day_df.empty:
        csv_file = "GBPUSD_2YEARS.csv"
        if os.path.exists(csv_file):
            df = pd.read_csv(csv_file)
            df.columns = [c.strip().lower() for c in df.columns]
            time_col = 'time' if 'time' in df.columns else ('timestamp' if 'timestamp' in df.columns else df.columns[0])
            df['dt_ist'] = pd.to_datetime(df[time_col])
            day_df = df[df['dt_ist'].dt.date == target_date].sort_values('dt_ist').reset_index(drop=True)
            result_template["data_source"] = "Local Archive CSV"
            
    if day_df.empty or len(day_df) < 12:
        result_template["status"] = "No Session Data"
        result_template["details"] = f"Insufficient M15 candles for {target_date} (Waiting for active sessions)."
        return result_template
        
    try:
        t_col = day_df['dt_ist'].dt.time
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
            
        is_asia_bearish = asia_close < asia_open
        direction = "long" if is_asia_bearish else "short"
        
        if direction == "long":
            level_sweep = asia_low - 0.20 * rng
            level_inval = asia_high + 0.20 * rng
        else:
            level_sweep = asia_high + 0.20 * rng
            level_inval = asia_low - 0.20 * rng
            
        # Gap filter (09:45 to 11:15 IST): Invalidate only if target sweep level was touched prematurely
        gap_df = day_df[(t_col >= time(9, 45)) & (t_col <= time(11, 15))]
        if len(gap_df) > 0:
            if direction == "long" and gap_df['low'].min() <= level_sweep:
                result_template["status"] = "Skipped (Gap Invalidation)"
                result_template["details"] = f"Lower trigger {level_sweep:.5f} touched prematurely in pre-London gap."
                return result_template
            elif direction == "short" and gap_df['high'].max() >= level_sweep:
                result_template["status"] = "Skipped (Gap Invalidation)"
                result_template["details"] = f"Upper trigger {level_sweep:.5f} touched prematurely in pre-London gap."
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
        "details": "",
        "data_source": "OANDA Live API"
    }
    
    # Rule: Thursday skipped
    if target_date.weekday() == 3:
        result_template["status"] = "Skipped (Thursday Rule)"
        result_template["details"] = "Thursday is strictly skipped by base strategy."
        return result_template
        
    # 1. Fetch live OANDA candles (M15)
    day_df = pd.DataFrame()
    live_df = fetch_oanda_candles("XAU_USD", "M15", target_date)
    if not live_df.empty:
        day_df = live_df.copy()
        result_template["data_source"] = "OANDA Live Feed"
        
    # 2. Local CSV fallback
    if day_df.empty:
        csv_file = "XAUUSD_1M_Sep2024_Sep2026.csv"
        if os.path.exists(csv_file):
            df = pd.read_csv(csv_file)
            df['time_utc'] = pd.to_datetime(df['time_utc'], utc=True)
            df['dt_ny'] = df['time_utc'].dt.tz_convert('America/New_York')
            day_df = df
            result_template["data_source"] = "Local Archive CSV"
            
    if day_df.empty:
        result_template["status"] = "No Session Data"
        result_template["details"] = f"No candle data available for {target_date}."
        return result_template
        
    try:
        # The 2H DOL session completing on target_date morning (04:30/05:30 IST) opens at 18:00 NY preceding evening
        session_ny = target_date - timedelta(days=1)
        day_p = day_df[(day_df['dt_ny'].dt.date == session_ny) & (day_df['dt_ny'].dt.hour == 18)]
        day_s = day_df[(day_df['dt_ny'].dt.date == session_ny) & (day_df['dt_ny'].dt.hour.isin([19, 20]))]
        
        # Fallback to target_date if evening session completed or archive CSV is same-day aligned
        if len(day_p) < 2 or len(day_s) < 4:
            day_p = day_df[(day_df['dt_ny'].dt.date == target_date) & (day_df['dt_ny'].dt.hour == 18)]
            day_s = day_df[(day_df['dt_ny'].dt.date == target_date) & (day_df['dt_ny'].dt.hour.isin([19, 20]))]
        
        if len(day_p) < 2 or len(day_s) < 4:
            result_template["status"] = "No Session Data"
            result_template["details"] = f"2H DOL session candles not yet complete for {target_date} morning."
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
            trade_dir = "long"
            sl_raw = s_low
            rule_name = "BULL SWEEP REJECTION"
        elif swept_high and s_close < p_high:
            trade_dir = "short"
            sl_raw = s_high
            rule_name = "BEAR SWEEP REJECTION"
            
        if not trade_dir:
            return result_template
            
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
# 6. MAIN DASHBOARD VIEW (PREMIUM & ANDROID MOBILE-OPTIMIZED)
# ==============================================================================
logo_b64 = ""
if os.path.exists(LOGO_PATH):
    try:
        with open(LOGO_PATH, "rb") as img_f:
            logo_b64 = base64.b64encode(img_f.read()).decode("utf-8")
    except Exception:
        pass

if logo_b64:
    header_html = f"""
    <div class="dashboard-header" style="display: flex; align-items: center; gap: 16px;">
        <img src="data:image/jpeg;base64,{logo_b64}" style="width: 58px; height: 58px; border-radius: 14px; box-shadow: 0 4px 16px rgba(0, 0, 0, 0.4); border: 1px solid rgba(255, 255, 255, 0.15); flex-shrink: 0;" />
        <div>
            <div class="main-title">⚡ Multi-Strategy Trading Terminal</div>
            <div class="sub-title">Live OANDA candle analysis & automatic Base44 Trade Journal synchronizer</div>
        </div>
    </div>
    """
else:
    header_html = """
    <div class="dashboard-header">
        <div class="main-title">⚡ Multi-Strategy Trading Terminal</div>
        <div class="sub-title">Live OANDA candle analysis & automatic Base44 Trade Journal synchronizer</div>
    </div>
    """
st.markdown(header_html, unsafe_allow_html=True)

# Top Strategy Information Cards (Responsive on Mobile)
kpi1, kpi2, kpi3, kpi4 = st.columns(4)
with kpi1:
    st.metric("USDJPY Selfsweep", "1:5.0 RRR", "No BE • No Tue")
with kpi2:
    st.metric("GBPUSD Asia Fib", "1:3.75 RRR", "1.2-1.4 Retracement")
with kpi3:
    st.metric("XAUUSD 2H DOL", "1:3.30 RRR", "BE @ +2.5R • No Thu")
with kpi4:
    oanda_status = "🟢 Connected" if st.session_state.oanda_token else "🔴 Token Needed"
    st.metric("OANDA Live Feed", oanda_status, "M15 & M1 Streams")

st.markdown("<br>", unsafe_allow_html=True)

# ------------------------------------------------------------------------------
# Interactive Date Selection Controller (Single Day or Date Range)
# ------------------------------------------------------------------------------
st.markdown("#### 📅 Date Selection & Mode")

date_mode = st.radio(
    "Choose evaluation mode:",
    ["🎯 Single Day", "🗓️ Date Range (Multi-Day)"],
    horizontal=True,
    key="ui_date_mode"
)

dates_to_run = []

if date_mode == "🎯 Single Day":
    col_d1, col_d2 = st.columns([2, 1])
    with col_d1:
        sel_date = st.date_input(
            "Select Trading Day",
            value=st.session_state.single_date,
            key="input_single_date"
        )
        st.session_state.single_date = sel_date
        dates_to_run = [sel_date]
    with col_d2:
        st.caption("Quick Date Shortcuts")
        q_col1, q_col2 = st.columns(2)
        if q_col1.button("Today"):
            st.session_state.single_date = datetime.date.today()
            st.rerun()
        if q_col2.button("Yesterday"):
            st.session_state.single_date = datetime.date.today() - timedelta(days=1)
            st.rerun()

else:
    col_r1, col_r2 = st.columns(2)
    with col_r1:
        start_d = st.date_input(
            "From (Start Date)",
            value=st.session_state.start_date,
            key="input_start_date"
        )
        st.session_state.start_date = start_d
    with col_r2:
        end_d = st.date_input(
            "To (End Date)",
            value=st.session_state.end_date,
            key="input_end_date"
        )
        st.session_state.end_date = end_d
        
    if start_d > end_d:
        st.warning("⚠️ Start Date is after End Date. Swapping dates automatically.")
        start_d, end_d = end_d, start_d

    num_days = (end_d - start_d).days + 1
    dates_to_run = [start_d + timedelta(days=i) for i in range(num_days)]
    
    # Preset Range Shortcuts
    st.caption(f"Selected: **{num_days} days** ({start_d.strftime('%b %d')} to {end_d.strftime('%b %d, %Y')})")
    p1, p2, p3, p4 = st.columns(4)
    if p1.button("Last 3 Days"):
        st.session_state.start_date = datetime.date.today() - timedelta(days=3)
        st.session_state.end_date = datetime.date.today()
        st.rerun()
    if p2.button("Last 7 Days"):
        st.session_state.start_date = datetime.date.today() - timedelta(days=7)
        st.session_state.end_date = datetime.date.today()
        st.rerun()
    if p3.button("Oct 1 - Oct 10"):
        st.session_state.start_date = datetime.date(2026, 10, 1)
        st.session_state.end_date = datetime.date(2026, 10, 10)
        st.rerun()
    if p4.button("This Month (Oct)"):
        st.session_state.start_date = datetime.date(2026, 10, 1)
        st.session_state.end_date = datetime.date.today()
        st.rerun()

st.markdown("<br>", unsafe_allow_html=True)

# ------------------------------------------------------------------------------
# Action Execution Button
# ------------------------------------------------------------------------------
btn_label = f"🚀 Run Strategies for {len(dates_to_run)} Day{'s' if len(dates_to_run) > 1 else ''} & Sync to Base44"
run_clicked = st.button(btn_label, type="primary")

if run_clicked:
    total_dates = len(dates_to_run)
    all_trades = []
    strat_ids = [
        st.session_state.strat_1_id,
        st.session_state.strat_2_id,
        st.session_state.strat_3_id
    ]
    
    progress_bar = st.progress(0, text="Starting analysis...")
    status_box = st.empty()
    
    for idx, d_val in enumerate(dates_to_run):
        progress_pct = int(((idx + 1) / total_dates) * 100)
        status_box.info(f"⏳ Analyzing candles for **{d_val.strftime('%A, %B %d, %Y')}** ({idx + 1}/{total_dates})...")
        progress_bar.progress(progress_pct, text=f"Processing {d_val.strftime('%b %d')} ({idx+1}/{total_dates})...")
        
        # Run 3 models
        res_u = run_usdjpy_strategy(d_val)
        res_g = run_gbpusd_strategy(d_val)
        res_x = run_xauusd_strategy(d_val)
        
        day_results = [res_u, res_g, res_x]
        
        for trade, s_id in zip(day_results, strat_ids):
            if trade["direction"] in ["long", "short"]:
                status_text, msg = sync_trade_to_base44(st.session_state.base44_token, s_id, trade)
                all_trades.append({
                    "Date": trade["date"].strftime("%Y-%m-%d"),
                    "Strategy": trade["strategy_name"],
                    "Symbol": trade["symbol"],
                    "Signal": trade["direction"].upper(),
                    "Entry": trade["entry_price"],
                    "SL": trade["sl_price"],
                    "TP": trade["tp_price"],
                    "SL%": f"{trade['sl_percentage']}%",
                    "TP%": f"{trade['tp_percentage']}%",
                    "Risk ($)": f"${DEFAULT_AMOUNT:,.2f}",
                    "Base44 Sync": status_text,
                    "Details": msg,
                    "Feed": trade.get("data_source", "OANDA"),
                    "RawTrade": trade
                })
                if status_text == "Success":
                    st.toast(f"✅ {trade['date']} {trade['symbol']} {trade['direction'].upper()} logged to Base44!", icon="🎯")
                elif status_text == "Skipped (Duplicate)":
                    st.toast(f"🛡️ {trade['date']} {trade['symbol']} duplicate skipped.", icon="ℹ️")
                elif status_text == "Error":
                    st.error(f"❌ Failed to sync {trade['symbol']} on {trade['date']}: {msg}")
            else:
                all_trades.append({
                    "Date": trade["date"].strftime("%Y-%m-%d"),
                    "Strategy": trade["strategy_name"],
                    "Symbol": trade["symbol"],
                    "Signal": "NO TRADE",
                    "Entry": "-",
                    "SL": "-",
                    "TP": "-",
                    "SL%": "-",
                    "TP%": "-",
                    "Risk ($)": f"${DEFAULT_AMOUNT:,.2f}",
                    "Base44 Sync": "N/A (No Setup)",
                    "Details": trade["status"] + (f" ({trade['details']})" if trade['details'] else ""),
                    "Feed": trade.get("data_source", "OANDA"),
                    "RawTrade": trade
                })
                
    progress_bar.empty()
    status_box.empty()
    st.success(f"✨ Execution complete across {total_dates} trading day{'s' if total_dates > 1 else ''}!")
    
    # --------------------------------------------------------------------------
    # Results KPI Metrics Bar
    # --------------------------------------------------------------------------
    active_signals = [t for t in all_trades if t["Signal"] in ["LONG", "SHORT"]]
    long_count = sum(1 for t in active_signals if t["Signal"] == "LONG")
    short_count = sum(1 for t in active_signals if t["Signal"] == "SHORT")
    synced_count = sum(1 for t in active_signals if t["Base44 Sync"] == "Success")
    dup_count = sum(1 for t in active_signals if t["Base44 Sync"] == "Skipped (Duplicate)")
    
    m1, m2, m3, m4 = st.columns(4)
    with m1:
        st.metric("Days Scanned", f"{total_dates} Days")
    with m2:
        st.metric("Active Signals", f"{len(active_signals)}", f"🟢 {long_count}L | 🔴 {short_count}S")
    with m3:
        st.metric("Base44 Synced", f"{synced_count} Logged", f"🛡️ {dup_count} Duplicates" if dup_count else "Fresh Entries")
    with m4:
        st.metric("Risk Allocation", f"${DEFAULT_AMOUNT:,.2f}", "Per Valid Signal")
        
    st.markdown("---")
    
    # --------------------------------------------------------------------------
    # Display Tabs
    # --------------------------------------------------------------------------
    tab_active, tab_table, tab_details = st.tabs([
        f"🔥 Active Signals ({len(active_signals)})",
        "📋 Full Daily Log Table",
        "🔍 Detailed Breakdown"
    ])
    
    with tab_active:
        if active_signals:
            st.markdown("##### 🎯 Confirmed Trade Setups Ready for Execution")
            for t in active_signals:
                raw = t["RawTrade"]
                badge_class = "badge-long" if t["Signal"] == "LONG" else "badge-short"
                st.markdown(f"""
                <div class="trade-card">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                        <span style="font-size: 1.15rem; font-weight: 800; color: #ffffff;">{t['Symbol']}</span>
                        <span class="{badge_class}">⚡ {t['Signal']}</span>
                    </div>
                    <div style="color: #94a3b8; font-size: 0.85rem; margin-bottom: 12px;">
                        📅 <strong>{t['Date']}</strong> &bull; {t['Strategy']} &bull; Feed: <code>{t['Feed']}</code>
                    </div>
                    <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(130px, 1fr)); gap: 10px; margin-bottom: 12px;">
                        <div style="background: rgba(15, 23, 42, 0.6); padding: 8px 12px; border-radius: 8px; border: 1px solid rgba(255,255,255,0.05);">
                            <span style="color: #64748b; font-size: 0.75rem;">ENTRY</span><br>
                            <span style="font-weight: 700; color: #f8fafc; font-size: 0.95rem;">{t['Entry']}</span>
                        </div>
                        <div style="background: rgba(15, 23, 42, 0.6); padding: 8px 12px; border-radius: 8px; border: 1px solid rgba(255,255,255,0.05);">
                            <span style="color: #64748b; font-size: 0.75rem;">STOP LOSS</span><br>
                            <span style="font-weight: 700; color: #f87171; font-size: 0.95rem;">{t['SL']} ({t['SL%']})</span>
                        </div>
                        <div style="background: rgba(15, 23, 42, 0.6); padding: 8px 12px; border-radius: 8px; border: 1px solid rgba(255,255,255,0.05);">
                            <span style="color: #64748b; font-size: 0.75rem;">TAKE PROFIT</span><br>
                            <span style="font-weight: 700; color: #34d399; font-size: 0.95rem;">{t['TP']} ({t['TP%']})</span>
                        </div>
                        <div style="background: rgba(15, 23, 42, 0.6); padding: 8px 12px; border-radius: 8px; border: 1px solid rgba(255,255,255,0.05);">
                            <span style="color: #64748b; font-size: 0.75rem;">RISK AMOUNT</span><br>
                            <span style="font-weight: 700; color: #38bdf8; font-size: 0.95rem;">{t['Risk ($)']}</span>
                        </div>
                    </div>
                    <div style="display: flex; justify-content: space-between; align-items: center; border-top: 1px solid rgba(255,255,255,0.06); padding-top: 8px;">
                        <span class="badge-sync">Base44: {t['Base44 Sync']}</span>
                        <span style="color: #cbd5e1; font-size: 0.8rem;">{t['Details']}</span>
                    </div>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.info("ℹ️ No active trade signals triggered on the evaluated dates. All rules and invalidations held true.")
            
    with tab_table:
        st.markdown("##### 📋 Complete Audit History")
        table_records = [{k: v for k, v in row.items() if k != "RawTrade"} for row in all_trades]
        df_summary = pd.DataFrame(table_records)
        
        def color_table(val):
            if val == "LONG":
                return "background-color: #065f46; color: #34d399; font-weight: bold;"
            elif val == "SHORT":
                return "background-color: #881337; color: #fb7185; font-weight: bold;"
            elif val == "Success":
                return "color: #10b981; font-weight: bold;"
            elif val == "Skipped (Duplicate)":
                return "color: #f59e0b; font-weight: bold;"
            elif val == "Error":
                return "color: #ef4444; font-weight: bold;"
            return ""
            
        styled_table = df_summary.style.map(color_table)
        st.dataframe(styled_table, use_container_width=True, hide_index=True)
        
    with tab_details:
        st.markdown("##### 🔬 Technical Candle & Filter Invalidation Notes")
        # Group by date for clear mobile viewing
        unique_dates = sorted(list(set(t["Date"] for t in all_trades)), reverse=True)
        for d_str in unique_dates:
            with st.expander(f"📅 Trading Date: {d_str}", expanded=(d_str == unique_dates[0])):
                day_rows = [t for t in all_trades if t["Date"] == d_str]
                for row in day_rows:
                    t_stat = row["Signal"]
                    status_emoji = "🟢" if t_stat == "LONG" else ("🔴" if t_stat == "SHORT" else "⚪")
                    st.markdown(f"**{status_emoji} {row['Symbol']} ({row['Strategy']}):** `{row['Details']}`")

else:
    st.info("💡 Choose a **Single Day** or a **Date Range** above, then click **'🚀 Run Strategies'** to stream live OANDA candles and audit trade triggers.")

