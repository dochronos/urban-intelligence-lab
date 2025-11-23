import streamlit as st
import pandas as pd
import plotly.express as px
from pathlib import Path
import sys

# ----------------------------------------------------
# Adjust path so we can import from /llm and /utils
# ----------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from llm.insights import generate_insights
from llm.classifier import classify_incident


# ----------------------------------------------------
# Load cleaned dataset for analytics
# ----------------------------------------------------
DATA_PATH = PROJECT_ROOT / "data" / "processed" / "subte_molinetes_ridership_clean.csv"

@st.cache_data
def load_data():
    if not DATA_PATH.exists():
        return None
    
    df = pd.read_csv(DATA_PATH, low_memory=False)
    
    # Normalize column names (safety)
    df.columns = df.columns.str.strip().str.lower()
    
    # Parse date if exists
    if "fecha" in df.columns:
        df["fecha"] = pd.to_datetime(df["fecha"], dayfirst=True, errors="coerce")
    
    return df


# ----------------------------------------------------
# UI Layout
# ----------------------------------------------------
st.set_page_config(
    page_title="Urban Intelligence Lab – Master Dashboard",
    layout="wide",
)

st.title("Urban Intelligence Lab – Master Dashboard")
st.markdown("Unified dashboard combining analytics, LLM insights, and automated incident classification.")


# ----------------------------------------------------
# Sidebar Navigation
# ----------------------------------------------------
st.sidebar.header("Navigation")
section = st.sidebar.radio(
    "Go to section:",
    [
        "📊 Subte Analytics",
        "🧠 LLM Insights",
        "🚨 Incident Classification Demo",
        "📘 About & Roadmap",
    ]
)


# ----------------------------------------------------
# SECTION A — Subte Analytics
# ----------------------------------------------------
if section == "📊 Subte Analytics":
    st.subheader("Subte Analytics (Turnstile Data)")
    
    df = load_data()
    
    if df is None:
        st.error("Clean dataset not found. Please run Week 5 first.")
    else:
        st.write("Dataset loaded successfully.", df.shape)

        # Simple Top 10 busiest stations
        if "estacion" in df.columns and "pax_total" in df.columns:
            top10 = (
                df.groupby("estacion")["pax_total"]
                .sum()
                .sort_values(ascending=False)
                .head(10)
                .reset_index()
            )

            st.markdown("### Top 10 busiest stations")
            fig = px.bar(
                top10,
                x="pax_total",
                y="estacion",
                orientation="h",
                title="Top 10 stations by total passengers",
            )
            fig.update_layout(height=450)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.warning("Columns 'estacion' or 'pax_total' missing from dataset.")

        # Optional KPIs
        st.markdown("### Global KPIs")
        col1, col2, col3 = st.columns(3)

        with col1:
            st.metric("Total entries", int(df["pax_pagos"].sum()) if "pax_pagos" in df else "N/A")

        with col2:
            st.metric("Total passes", int(df["pax_pases_pagos"].sum()) if "pax_pases_pagos" in df else "N/A")

        with col3:
            st.metric("Total traffic", int(df["pax_total"].sum()) if "pax_total" in df else "N/A")


# ----------------------------------------------------
# SECTION B — LLM Insights
# ----------------------------------------------------
elif section == "🧠 LLM Insights":
    st.subheader("LLM-Generated Narrative Insights")
    st.write("Uses 'generate_insights()' to produce narrative insights from cleaned Subte data.")

    df = load_data()
    if df is None:
        st.error("Dataset not found.")
    else:
        if st.button("Generate Narrative"):
            with st.spinner("Running local LLM…"):
                text = generate_insights(df)
            st.markdown("#### Narrative:")
            st.success(text)


# ----------------------------------------------------
# SECTION C — Incident Classification Demo
# ----------------------------------------------------
elif section == "🚨 Incident Classification Demo":
    st.subheader("Incident Classification (Local LLM)")
    st.write("Type any Subte-related incident and classify it using the local model (llama3.2:3b).")

    user_input = st.text_area("Describe an incident:", height=160)

    if st.button("Classify Incident"):
        if not user_input.strip():
            st.warning("Please type a description first.")
        else:
            with st.spinner("Classifying using local LLM…"):
                result = classify_incident(user_input)

            st.markdown("### Classification Result")
            st.json(result)


# ----------------------------------------------------
# SECTION D — ABOUT
# ----------------------------------------------------
elif section == "📘 About & Roadmap":
    st.subheader("About This Dashboard")
    st.write("""
    This master dashboard integrates:
    - Subte mobility analytics  
    - LLM-generated insights  
    - Automated incident classification  

    It concludes **Phase 2** of the Urban Intelligence Lab.
    """)

    st.markdown("### Roadmap – Next Phase (Phase 3)")
    st.write("""
    - More real-time data sources  
    - Automated logging of n8n outputs  
    - Anomaly detection (ML models)  
    - Multi-line analytics comparison  
    - Predictive modeling extensions  
    """)

    st.markdown("Developed as part of a multi-week project for portfolio and analytics practice.")