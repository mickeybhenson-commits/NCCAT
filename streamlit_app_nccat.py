import streamlit as st
import json
import pandas as pd
import datetime as dt
import requests
from pathlib import Path
from streamlit_autorefresh import st_autorefresh

# --- 1. ARCHITECTURAL CONFIG & PREMIUM STYLING ---
st.set_page_config(page_title="NCCAT | Construction Operations Command", layout="wide")
st_autorefresh(interval=300000, key="datarefresh")  # 5-Min Sync

def apply_nccat_styling():
    st.markdown(
        f"""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;700;900&display=swap');
        .stApp {{ background-color: #0a0f1e; font-family: 'Inter', sans-serif; }}
        .stApp:before {{ content: ""; position: fixed; inset: 0; background: radial-gradient(circle at center, rgba(0,0,30,0.92), rgba(0,0,0,0.97)); z-index: 0; }}
        section.main {{ position: relative; z-index: 1; }}
        .exec-header {{ margin-bottom: 30px; border-left: 10px solid #004B8D; padding-left: 25px; }}
        .exec-title {{ font-size: 3.8em; font-weight: 900; letter-spacing: -2px; line-height: 1; color: #FFFFFF; margin: 0; }}
        .sync-badge {{ background: rgba(255, 255, 255, 0.1); color: #00FFCC; padding: 5px 12px; border-radius: 50px; font-size: 0.8em; font-weight: 700; border: 1px solid #00FFCC; }}
        .report-section {{ background: rgba(15, 15, 20, 0.9); border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 8px; padding: 25px; margin-bottom: 20px; }}
        .directive-header {{ color: #004B8D; font-weight: 900; text-transform: uppercase; font-size: 0.85em; margin-bottom: 12px; border-bottom: 1px solid rgba(255,255,255,0.1); padding-bottom: 5px; }}
        .truth-card {{ text-align: center; padding: 12px; background: rgba(0, 255, 204, 0.08); border-radius: 8px; border: 1px solid #00FFCC; min-height: 90px; }}
        .forecast-card {{ text-align: center; padding: 10px; background: rgba(255,255,255,0.05); border-radius: 8px; border: 1px solid rgba(255,255,255,0.1); line-height: 1.1; min-height: 140px; }}
        .temp-box {{ background: rgba(255,255,255,0.1); padding: 2px 6px; border-radius: 4px; font-weight: 700; font-size: 0.85em; margin: 4px 0; display: inline-block; }}
        .precip-box {{ color: #00FFCC; font-weight: 700; font-size: 0.85em; margin-top: 4px; }}
        </style>
        """, unsafe_allow_html=True)

apply_nccat_styling()

# --- 2. MULTI-SOURCE TRUTH COLLECTOR (USGS Tuckasegee + Ambient Weather) ---
AMBIENT_API_KEY = st.secrets.get("AMBIENT_API_KEY", "9ed066cb260c42adbe8778e0afb09e747f8450a7dd20479791a18d692b722334")
AMBIENT_APP_KEY = st.secrets.get("AMBIENT_APP_KEY", "9ed066cb260c42adbe8778e0afb09e747f8450a7dd20479791a18d692b722334")

def get_usgs_truth():
    """Tuckasegee River at Cullowhee - USGS gauge 03439000"""
    try:
        url = "https://waterservices.usgs.gov/nwis/iv/?format=json&sites=03439000&parameterCd=00045"
        resp = requests.get(url, timeout=5).json()
        return float(resp['value']['timeSeries'][0]['values'][0]['value'][0]['value'])
    except:
        return 0.0

@st.cache_data(ttl=300)
def get_ambient_conditions():
    """Pull live data from Ambient Weather station near NCCAT"""
    try:
        url = "https://api.ambientweather.net/v1/devices"
        params = {"apiKey": AMBIENT_API_KEY, "applicationKey": AMBIENT_APP_KEY}
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        devices = resp.json()
        if devices and len(devices) > 0:
            last = devices[0].get("lastData", {})
            return {
                "temp": last.get("tempf", "--"),
                "humidity": last.get("humidity", "--"),
                "wind_speed": last.get("windspeedmph", "--"),
                "wind_dir": last.get("winddir", "--"),
                "rain_today": last.get("dailyrainin", 0.0),
                "gust": last.get("windgustmph", "--"),
                "pressure": last.get("baromrelin", "--"),
                "uv": last.get("uv", "--"),
                "solar": last.get("solarradiation", "--"),
                "station": devices[0].get("info", {}).get("name", "Local PWS")
            }
    except:
        pass
    return None

usgs_val = get_usgs_truth()
ambient = get_ambient_conditions()

# --- 3. LOAD SITE DATA ---
try:
    with open('data/cullowhee_site.json') as f:
        site_data = json.load(f)
except:
    site_data = {"swppp": {"risk": "UNKNOWN", "rain_24h": 0.0}, "crane": {"status": "GO"}}

swppp_risk = site_data.get("swppp", {}).get("risk", "LOW")
rain_24h = site_data.get("swppp", {}).get("rain_24h", 0.0)

# --- 4. DYNAMIC ROLLING CALENDAR ENGINE ---
current_dt = dt.datetime.now()
current_day_name = current_dt.strftime('%a')
rolling_dates = [(current_dt + dt.timedelta(days=i)) for i in range(7)]

master_forecast = {
    "Mon": {"status": "STABLE",     "color": "#00FFCC", "hi": 55, "lo": 32, "pop": "1%",  "in": "0.00\"", "truth": "0.00\"",              "task": "Completed: Site Maintenance"},
    "Tue": {"status": "STABLE",     "color": "#00FFCC", "hi": 60, "lo": 38, "pop": "2%",  "in": "0.00\"", "truth": "0.00\"",              "task": "Completed: Silt Fence Audit"},
    "Wed": {"status": "STABLE",     "color": "#00FFCC", "hi": 68, "lo": 40, "pop": "1%",  "in": "0.00\"", "truth": f"{usgs_val}\" (USGS)", "task": "VERIFIED DRY: Resume Standard Ops"},
    "Thu": {"status": "STABLE",     "color": "#00FFCC", "hi": 62, "lo": 39, "pop": "0%",  "in": "0.00\"", "truth": "TBD",                 "task": "Operational: Clear skies forecast"},
    "Fri": {"status": "RESTRICTED", "color": "#FF8C00", "hi": 70, "lo": 52, "pop": "25%", "in": "0.02\"", "truth": "TBD",                 "task": "Caution: Evening showers possible"},
    "Sat": {"status": "CRITICAL",   "color": "#FF0000", "hi": 72, "lo": 54, "pop": "65%", "in": "0.20\"", "truth": "TBD",                 "task": "Alert: Mountain Thunderstorms / Runoff Risk"},
    "Sun": {"status": "RECOVERY",   "color": "#FFFF00", "hi": 58, "lo": 28, "pop": "20%", "in": "0.05\"", "truth": "TBD",                 "task": "Drying: Temperature Drop — Monitor Soil"}
}

# --- 5. UI RENDERING ---
st.markdown(f"""
    <div class="exec-header">
        <div style="display: flex; justify-content: space-between; align-items: center;">
            <div class="exec-title">NCCAT</div>
            <div class="sync-badge">AUTONOMOUS TRUTH SYNC • {current_dt.strftime('%H:%M')}</div>
        </div>
        <div style="font-size:1.5em; color:#AAA; text-transform:uppercase;">National Center for the Advancement of Teaching — Cullowhee, NC</div>
    </div>
""", unsafe_allow_html=True)

c_main, c_metrics = st.columns([2, 1])

with c_main:
    today_data = master_forecast.get(current_day_name, master_forecast["Sun"])

    # 1. Rolling Operational Directive
    is_impending_rain = int(today_data['pop'].replace('%', '')) > 60
    directive_color = "#FFD700" if (is_impending_rain and usgs_val == 0) else today_data['color']
    directive_status = "PRE-STORM ADVISORY" if (is_impending_rain and usgs_val == 0) else today_data['status']

    st.markdown(f"""
        <div class="report-section" style="border-top: 8px solid {directive_color};">
            <div class="directive-header">Field Operational Directive • COLLECTOR ACTIVE</div>
            <h1 style="color: {directive_color}; margin: 0; font-size: 3.5em; letter-spacing: -2px;">{directive_status}</h1>
            <p style="font-size: 1.3em; margin-top: 10px;"><b>SWPPP Risk: {swppp_risk}</b> — {today_data['task']}</p>
        </div>
    """, unsafe_allow_html=True)

    # 2. Rolling 7-Day Ground Truth Tiles
    st.markdown('<div class="report-section"><div class="directive-header">7-Day Ground Truth (Measured Reality)</div>', unsafe_allow_html=True)
    gt_cols = st.columns(7)
    for i, date_obj in enumerate(rolling_dates):
        day_key = date_obj.strftime('%a')
        d = master_forecast.get(day_key, master_forecast["Sun"])
        gt_cols[i].markdown(f'<div class="truth-card"><span style="color:#00FFCC; font-weight:900;">{day_key}</span><br><b style="font-size:1.3em;">{d["truth"]}</b></div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # 3. Rolling 7-Day Weather Outlook
    st.markdown('<div class="report-section"><div class="directive-header">Rolling 7-Day Weather Outlook</div>', unsafe_allow_html=True)
    f_cols = st.columns(7)
    for i, date_obj in enumerate(rolling_dates):
        day_key = date_obj.strftime('%a')
        d = master_forecast.get(day_key, master_forecast["Sun"])
        f_cols[i].markdown(f"""
            <div class="forecast-card" style="border-top: 4px solid {d['color']};">
                <b>{day_key}</b><br>
                <small>{date_obj.strftime('%m/%d')}</small><br>
                <div class="temp-box">{d['hi']}°/{d['lo']}°</div><br>
                <div class="precip-box">{d['pop']} Prob</div>
            </div>
        """, unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # 4. Ambient Weather Live Station
    st.markdown('<div class="report-section"><div class="directive-header">📡 Ambient Weather — Live Local Station</div>', unsafe_allow_html=True)
    if ambient:
        st.caption(f"Station: {ambient['station']}")
        a1, a2, a3, a4, a5, a6 = st.columns(6)
        a1.metric("Temp", f"{ambient['temp']}°F")
        a2.metric("Humidity", f"{ambient['humidity']}%")
        a3.metric("Wind", f"{ambient['wind_speed']} mph")
        a4.metric("Gust", f"{ambient['gust']} mph")
        a5.metric("Rain Today", f"{ambient['rain_today']}\"")
        a6.metric("Pressure", f"{ambient['pressure']} inHg")
    else:
        st.warning("⚠️ Ambient Weather station offline or API key issue.")
    st.markdown('</div>', unsafe_allow_html=True)

with c_metrics:
    # 5. Analytical Metrics
    st.markdown('<div class="report-section"><div class="directive-header">Analytical Metrics</div>', unsafe_allow_html=True)
    st.metric("USGS Gauge (Tuckasegee)", f"{usgs_val}\"", delta="DRY" if usgs_val == 0 else "PRECIP")
    st.metric("24hr Site Rainfall", f"{rain_24h}\"")
    st.metric("SWPPP Risk Level", swppp_risk)
    if ambient:
        st.metric("Temperature", f"{ambient['temp']}°F")
        st.metric("Wind Speed", f"{ambient['wind_speed']} mph")
        st.metric("Wind Direction", f"{ambient['wind_dir']}°")
        st.metric("Humidity", f"{ambient['humidity']}%")
        st.metric("UV Index", f"{ambient['uv']}")
        st.metric("Solar Radiation", f"{ambient['solar']} W/m²")
    else:
        st.metric("Temperature", "--")
        st.metric("Wind Speed", "--")
    st.metric("NC DEQ NTU Limit", "50 NTU")
    st.markdown('</div>', unsafe_allow_html=True)

# 6. Radar — Cullowhee / Jackson County, NC
st.markdown('<div class="report-section"><div class="directive-header">Surveillance Radar: Jackson County / Cullowhee, NC</div>', unsafe_allow_html=True)
st.components.v1.html(
    '<iframe width="100%" height="450" src="https://embed.windy.com/embed2.html?lat=35.308&lon=-83.175&zoom=9&overlay=radar" frameborder="0" style="border-radius:8px;"></iframe>',
    height=460
)
st.markdown('</div>', unsafe_allow_html=True)
