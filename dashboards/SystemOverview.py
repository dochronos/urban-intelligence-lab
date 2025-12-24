import sys
from pathlib import Path
import streamlit as st
import pandas as pd
import duckdb

# --- Project path setup ---
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from llm.insights import generate_insights
from llm.router import build_ticket

# --- Page config ---
st.set_page_config(
    page_title="Urban Intelligence Lab — System Overview",
    layout="wide"
)

st.title("🚦 Urban Intelligence Lab — System Overview (v2.0.0)")
st.caption(
    "Unified operational view combining analytics, anomaly detection, LLM insights, "
    "and smart incident routing."
)

# --- Sidebar ---
st.sidebar.header("Navigation")
section = st.sidebar.radio(
    "Select a section",
    [
        "Overview",
        "Anomaly Monitoring",
        "LLM Insights",
        "Incident Routing",
        "Roadmap",
    ]
)

# --- Load data ---
DATA_PATH = PROJECT_ROOT / "data" / "processed" / "subte_molinetes_ridership_clean.csv"
df = pd.read_csv(DATA_PATH, low_memory=False)
df.columns = df.columns.str.strip().str.lower()

if "fecha" in df.columns:
    df["fecha"] = pd.to_datetime(df["fecha"], dayfirst=True, errors="coerce")

# --- Overview ---
if section == "Overview":
    st.subheader("System Summary")

    col1, col2, col3 = st.columns(3)
    col1.metric("Total Records", f"{len(df):,}")
    col2.metric("Stations", df["estacion"].nunique() if "estacion" in df.columns else "N/A")
    col3.metric("Date Range", f"{df['fecha'].min().date()} → {df['fecha'].max().date()}")

    st.markdown(
        """
        **Urban Intelligence Lab v2.0.0** integrates:
        - Cleaned mobility analytics
        - Anomaly detection foundations
        - LLM-powered narrative insights
        - Smart incident routing logic

        This dashboard acts as a central operational entry point for future real-time extensions.
        """
    )

# --- Anomaly Monitoring ---
elif section == "Anomaly Monitoring":
    st.subheader("Anomaly Monitoring (Preview)")

    st.info(
        "This section previews how anomaly indicators generated in Week 10 "
        "can be monitored and extended to alerting workflows."
    )

    df_daily = df.dropna(subset=["fecha"]).copy()
    df_daily["date"] = df_daily["fecha"].dt.date

    daily = (
        df_daily.groupby("date", as_index=False)["pax_total"]
        .sum()
    )

    st.line_chart(daily.set_index("date"))

# --- LLM Insights ---
elif section == "LLM Insights":
    st.subheader("LLM Narrative Insights")

    if st.button("Generate insights with local LLM"):
        with st.spinner("Generating insights..."):
            text = generate_insights(df.head(5000))
            st.write(text)

# --- Incident Routing ---
elif section == "Incident Routing":
    st.subheader("Smart Incident Routing Demo")

    incident_text = st.text_area(
        "Incident description",
        "20-minute delay on Line B at Carlos Pellegrini due to a mechanical failure.",
        height=120,
    )

    if st.button("Route incident"):
        llm_result = {
            "category": "infrastructure",
            "severity": "high",
            "line": "B",
            "station": "Carlos Pellegrini",
            "target_team": "manual_review",
        }

        ticket = build_ticket(incident_text, llm_result)
        st.json(ticket)

# --- Roadmap ---
elif section == "Roadmap":
    st.subheader("Project Roadmap")

    st.markdown(
        """
        **Phase 3 (Weeks 9–12)** — Completed  
        - Daily data pipelines & logging  
        - Anomaly detection  
        - Smart routing logic  
        - Unified system overview  

        **Phase 4 (Planned)**  
        - Near real-time ingestion  
        - Automated alerts  
        - Multi-city support  
        - Deployment & packaging
        """
    )
