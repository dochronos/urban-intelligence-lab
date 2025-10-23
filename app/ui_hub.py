# app/ui_hub.py
# Urban Intelligence Lab — Unified Portal (Week 4)
# Streamlit-based hub that links all UIL modules, checks services, and summarizes data status.

from __future__ import annotations
import os
from pathlib import Path
from datetime import datetime

import pandas as pd
import requests
import streamlit as st
from dotenv import load_dotenv

# ----------------- Config -----------------
PROJECT_NAME = "Urban Intelligence Lab — Unified Portal"
PROJECT_VERSION = "v1.0.0 (Public Release)"
ROOT = Path(".")
PROCESSED = ROOT / "data" / "processed"
ASSETS = ROOT / "assets"
REPORTS_DIR = ASSETS / "reports"

# Ports/URLs (override via .env)
load_dotenv(override=True)
DASH_URL = os.getenv("UIL_DASH_URL", "http://localhost:8050")
INSIGHTS_URL = os.getenv("UIL_INSIGHTS_URL", "http://localhost:8501")
N8N_URL = os.getenv("UIL_N8N_URL", "http://localhost:5678")
N8N_WEBHOOK_URL = os.getenv("N8N_WEBHOOK_URL", "").strip()

# Files
PAX_FILE = PROCESSED / "molinetes_2024_clean.parquet"
HW_FILE = PROCESSED / "headway_estimates_2024.csv"
FC_FILE = PROCESSED / "passengers_forecast_weekly.csv"

# --------------- Helpers ------------------
def ping(url: str, timeout: float = 1.5) -> tuple[bool, str]:
    try:
        r = requests.get(url, timeout=timeout)
        return (200 <= r.status_code < 400, f"HTTP {r.status_code}")
    except Exception as e:
        return (False, f"{type(e).__name__}")

def file_stats(path: Path) -> str:
    if not path.exists():
        return "❌ missing"
    try:
        if path.suffix.lower() == ".parquet":
            df = pd.read_parquet(path, columns=None)
        else:
            df = pd.read_csv(path)
        rows, cols = df.shape
        mtime = datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
        return f"✅ {rows:,} × {cols}  · updated {mtime}"
    except Exception as e:
        return f"⚠️ exists but failed to read ({type(e).__name__})"

def latest_report() -> Path | None:
    if not REPORTS_DIR.exists():
        return None
    files = sorted(REPORTS_DIR.glob("week*_insights_*.md"), key=lambda p: p.stat().st_mtime, reverse=True)
    return files[0] if files else None

# --------------- UI -----------------------
st.set_page_config(page_title=PROJECT_NAME, page_icon="🧭", layout="wide")
st.title(PROJECT_NAME)
st.caption(PROJECT_VERSION)

colA, colB, colC = st.columns(3)

with colA:
    ok, msg = ping(INSIGHTS_URL)
    st.metric("Streamlit · AI Insights", "UP" if ok else "DOWN", delta=msg)
    st.link_button("Open Insights", INSIGHTS_URL, use_container_width=True)

with colB:
    ok, msg = ping(DASH_URL)
    st.metric("Dash · Week 1 Dashboard", "UP" if ok else "DOWN", delta=msg)
    st.link_button("Open Dash", DASH_URL, use_container_width=True)

with colC:
    ok, msg = ping(N8N_URL)
    st.metric("n8n · Automation", "UP" if ok else "DOWN", delta=msg)
    st.link_button("Open n8n", N8N_URL, use_container_width=True)

st.divider()

# ---------- Data status ----------
st.subheader("Data status (processed)")
c1, c2, c3 = st.columns(3)
with c1:
    st.write("**Passengers**")
    st.code(PAX_FILE.as_posix(), language="text")
    st.write(file_stats(PAX_FILE))
with c2:
    st.write("**Headway estimates**")
    st.code(HW_FILE.as_posix(), language="text")
    st.write(file_stats(HW_FILE))
with c3:
    st.write("**Forecast (4-week)**")
    st.code(FC_FILE.as_posix(), language="text")
    st.write(file_stats(FC_FILE))

st.divider()

# ---------- Quick links & actions ----------
st.subheader("Quick links & actions")

col1, col2, col3 = st.columns(3)
with col1:
    st.write("**Latest weekly report**")
    rep = latest_report()
    if rep:
        st.code(rep.as_posix(), language="text")
        st.download_button("Download latest report", data=rep.read_text(encoding="utf-8"),
                           file_name=rep.name, use_container_width=True)
    else:
        st.info("No weekly report found yet.")

with col2:
    st.write("**CLI helpers**")
    st.code(
        "streamlit run app/insights_streamlit.py\n"
        "python app/main_dashboard.py\n"
        "python scripts/forecast_passengers.py\n"
        "python scripts/generate_screenshot.py --url http://localhost:8501 "
        "--output assets/screenshots/week4_launch.png",
        language="bash"
    )

with col3:
    st.write("**Automation (n8n)**")
    if N8N_WEBHOOK_URL:
        st.caption("Webhook configured:")
        st.code(N8N_WEBHOOK_URL, language="text")
        # small test payload (does not mutate)
        if st.button("Send test ping to n8n", use_container_width=True):
            try:
                r = requests.post(N8N_WEBHOOK_URL, json={"ping": "uil-week4"}, timeout=3)
                st.success(f"Webhook responded: HTTP {r.status_code}")
            except Exception as e:
                st.error(f"Webhook failed: {e}")
    else:
        st.warning("Set N8N_WEBHOOK_URL in .env to enable webhook actions.")

st.divider()

# ---------- About ----------
with st.expander("About this portal"):
    st.markdown(
        """
- **Purpose:** one place to access UIL modules, check services, and verify data freshness.
- **Modules:** Dash dashboard (Week 1), Streamlit insights (Weeks 2–3), n8n automation, forecasting pipeline.
- **AI:** Ollama (local) for summaries.
- **Versioning:** This is the **Week 4 — Public Release** portal.
        """
    )
