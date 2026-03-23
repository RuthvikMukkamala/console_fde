import os

import streamlit as st
import requests

st.set_page_config(page_title="Macro Intelligence Report", page_icon="📊", layout="wide")

TREND_ARROW = {"UP": "↑", "DOWN": "↓", "FLAT": "→"}
REGIME_STYLE = {
    "HAWKISH": ("🔴", "Hawkish / Tightening Bias"),
    "DOVISH": ("🟢", "Dovish / Easing Bias"),
    "NEUTRAL": ("🟡", "Neutral / Mixed Signals"),
}
DISPLAY_NAMES = {
    "inflation": "Inflation (CPI)",
    "labor_market": "Labor Market",
    "treasury_yields": "Treasury Yields",
    "inflation_expectations": "Inflation Expectations",
}

API_KEY = os.environ.get("API_SECRET_KEY", "")

st.title("📊 Daily Macro Intelligence Report")

with st.sidebar:
    st.header("Configuration")
    backend_url = st.text_input("Backend URL", value="https://console-fde.onrender.com")
    days = st.slider("Observations to fetch", min_value=1, max_value=1000, value=100)
    report_name = st.text_input("Report Name", placeholder="Daily Macro Report")
    author = st.text_input("Author", placeholder="Your name")
    generate = st.button("Generate Report", type="primary", use_container_width=True)

if generate:
    params = {"days": days}
    if report_name:
        params["report_name"] = report_name
    if author:
        params["author"] = author

    with st.spinner("Fetching data and generating report..."):
        try:
            resp = requests.post(
                f"{backend_url}/generate-report",
                params=params,
                headers={"X-API-Key": API_KEY},
                timeout=120,
            )
            resp.raise_for_status()
            data = resp.json()
        except requests.exceptions.ConnectionError:
            st.error(f"Cannot connect to backend at `{backend_url}`. Is the server running?")
            st.stop()
        except requests.exceptions.Timeout:
            st.error("Request timed out. The backend may be overloaded.")
            st.stop()
        except requests.exceptions.HTTPError as exc:
            st.error(f"Backend returned an error: {exc}")
            st.stop()

    status = data.get("status", "unknown")
    if status == "success":
        st.success(f"Report generated successfully — {data['report_date']}")
    elif status == "partial_success":
        st.warning(f"Report generated with warnings — {data['report_date']}")
    else:
        st.error(f"Report failed — {data.get('report_summary', 'Unknown error')}")
        st.stop()

    regime = data.get("overall_regime", "UNKNOWN")
    emoji, label = REGIME_STYLE.get(regime, ("❓", regime))
    st.markdown(f"### {emoji} Overall Regime: {label}")

    if data.get("notion_page_url"):
        st.markdown(f"[Open in Notion]({data['notion_page_url']})")

    st.divider()

    signals = data.get("signals", {})
    cols = st.columns(len(signals) if signals else 1)

    for i, (name, sig) in enumerate(signals.items()):
        with cols[i]:
            display = DISPLAY_NAMES.get(name, name)
            arrow = TREND_ARROW.get(sig["trend"], "?")
            delta = sig.get("delta")
            delta_str = f"{'+' if delta and delta > 0 else ''}{delta}" if delta is not None else "N/A"

            st.metric(
                label=display,
                value=f"{sig['latest']}",
                delta=delta_str,
            )
            st.caption(f"{arrow} {sig['signal']}")

    warnings = data.get("warnings")
    if warnings:
        st.divider()
        with st.expander("⚠️ Warnings"):
            for w in warnings:
                st.warning(w)

    st.divider()
    with st.expander("Report Summary"):
        st.text(data.get("report_summary", ""))

    st.caption(f"Actions taken: {', '.join(data.get('actions_taken', []))}")
