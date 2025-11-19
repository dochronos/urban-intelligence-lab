import sys
from pathlib import Path

# ----------------------------------------------------
# Ensure project root is on sys.path so we can import `llm`
# ----------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import streamlit as st
import pandas as pd
import altair as alt

from llm.insights import generate_insights

# ----------------------------------------------------
# Paths & data loading
# ----------------------------------------------------

DATA_PATH = PROJECT_ROOT / "data" / "processed" / "subte_molinetes_ridership_clean.csv"


@st.cache_data
def load_data() -> pd.DataFrame:
    df = pd.read_csv(DATA_PATH, low_memory=False)

    # fechas en formato día/mes/año (ej: 13/2/2024)
    if "fecha" in df.columns:
        df["fecha"] = pd.to_datetime(
            df["fecha"],
            dayfirst=True,
            errors="coerce",
        )

    # convertir todas las columnas de pasajeros a numéricas
    for col in df.columns:
        if "pax" in col.lower():  # pax_pagos, pax_pases_pagos, pax_franq, pax_total, etc.
            df[col] = pd.to_numeric(df[col], errors="coerce")

    return df


df = load_data()

st.title("Subte Insights – Week 6 (Urban Intelligence Lab)")
st.markdown(
    "LLM-generated narrative + interactive analytics based on cleaned turnstile data."
)

# ----------------------------------------------------
# Helper functions to detect columns (priorizar coincidencias exactas)
# ----------------------------------------------------


def find_station_column(columns) -> str | None:
    lower_map = {c.lower(): c for c in columns}

    # 1) Coincidencias exactas primero
    for key in ("estacion", "station", "station_name"):
        if key in lower_map:
            return lower_map[key]

    # 2) Si no hay exactas, buscamos que contenga la palabra
    candidates = [
        c for c in columns if "estacion" in c.lower() or "station" in c.lower()
    ]
    return candidates[0] if candidates else None


def find_passenger_column(columns) -> str | None:
    lower_map = {c.lower(): c for c in columns}

    # 1) Coincidencias exactas más típicas
    for key in ("pax_total", "total_pax", "passengers_total"):
        if key in lower_map:
            return lower_map[key]

    # 2) Si no, cualquier columna relacionada con pax/pasajeros
    candidates = [
        c
        for c in columns
        if "pax_total" in c.lower()
        or "pax" in c.lower()
        or "pasaj" in c.lower()
        or "passenger" in c.lower()
    ]
    return candidates[0] if candidates else None


# ----------------------------------------------------
# Usamos todo el dataset (sin filtro de fechas de momento)
# ----------------------------------------------------

df_filtered = df.copy()

# ----------------------------------------------------
# Plot: Top 10 busiest stations (with fallback logic)
# ----------------------------------------------------

st.subheader("Top 10 busiest stations")

station_col = find_station_column(df_filtered.columns)
pax_col = find_passenger_column(df_filtered.columns)

if station_col:
    base = df_filtered.dropna(subset=[station_col]).copy()

    use_passengers = False
    value_col = "count"

    if pax_col:
        numeric = pd.to_numeric(base[pax_col], errors="coerce")

        if numeric.notna().sum() > 0 and numeric.sum() > 0:
            base[pax_col] = numeric
            use_passengers = True
            value_col = "passengers"

    if use_passengers:
        grouped = (
            base.groupby(station_col)[pax_col]
            .sum()
            .sort_values(ascending=False)
            .head(10)
        )
    else:
        # Fallback: contar registros por estación
        grouped = (
            base.groupby(station_col)
            .size()
            .sort_values(ascending=False)
            .head(10)
        )

    top_stations = grouped.reset_index(name=value_col)

    chart = (
        alt.Chart(top_stations)
        .mark_bar()
        .encode(
            x=alt.X(
                f"{value_col}:Q",
                title="Total passengers" if use_passengers else "Number of records",
            ),
            y=alt.Y(f"{station_col}:N", sort="-x", title="Station"),
            tooltip=[station_col, value_col],
        )
        .properties(
            title="Top 10 stations by total passengers"
            if use_passengers
            else "Top 10 stations by record count"
        )
    )

    st.altair_chart(chart, use_container_width=True)
else:
    st.info(
        "No station-like column found in the dataset (expected something containing 'estacion' or 'station')."
    )

st.divider()

# ----------------------------------------------------
# LLM Insights Section
# ----------------------------------------------------

st.subheader("LLM narrative insights")

st.markdown(
    "Click the button below to generate a short narrative based on the current data "
    "using the local LLM model (`llama3.2:3b` via Ollama)."
)

if st.button("Generate AI insights"):
    with st.spinner("Asking the LLM for insights..."):
        insights_text = generate_insights(df_filtered)
    st.markdown(insights_text)
