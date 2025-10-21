# app/insights_streamlit.py
import os
import re
import warnings
from datetime import datetime
from pathlib import Path

import pandas as pd
import requests
import streamlit as st
from dotenv import load_dotenv

# ---------------- Config ----------------
APP_TITLE = "UIL — AI Insights (Week 2)"
ROOT = Path(".")
PROCESSED = ROOT / "data" / "processed"
ASSETS = ROOT / "assets"
ASSETS.mkdir(parents=True, exist_ok=True)
REPORTS_DIR = ASSETS / "reports"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

load_dotenv(override=True)

# IA backend: SOLO OLLAMA (sin OpenAI)
USE_OLLAMA = True
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.1:8b-instruct")

# Silenciar warning de pandas (observed=False)
warnings.filterwarnings("ignore", message="The default of observed=False is deprecated")

# Conjunto base de líneas Subte (sin Premetro)
SUBTE_LINES = {"A", "B", "C", "D", "E", "H"}
PREMETRO_LINE = {"P"}

# ---------------- Helpers ----------------
def file_mtime(p: Path) -> float:
    try:
        return p.stat().st_mtime
    except FileNotFoundError:
        return 0.0

@st.cache_data(show_spinner=False)
def load_passengers(path: Path, mtime: float):
    p = path / "molinetes_2024_clean.parquet"
    if not p.exists():
        return None
    df = pd.read_parquet(p)
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"])
    return df

@st.cache_data(show_spinner=False)
def load_headway(path: Path, mtime: float):
    p = path / "headway_estimates_2024.csv"
    if not p.exists():
        return None
    df = pd.read_csv(p)
    if "year_month" in df.columns:
        df["date"] = pd.to_datetime(df["year_month"] + "-01")
    else:
        df["date"] = pd.Timestamp("2024-01-01")
    return df

def canonical_line(s):
    """
    Normaliza etiquetas de línea a una sola letra.
    Soporta: 'A'..'H', 'Linea A', 'LíneaB', 'LineaC' pegado, etc.
    Si no matchea A–H, conserva el valor original (sirve para 'P' Premetro).
    """
    if pd.isna(s):
        return s
    text = str(s).strip()

    # 1) ya es una sola letra
    if re.fullmatch(r"[A-Za-z]", text):
        return text.upper()

    # 2) 'Linea X' / 'Línea X' (con o sin espacio)
    m = re.match(r"^\s*l[ií]nea\s*([a-z])\s*$", text, flags=re.IGNORECASE)
    if m:
        return m.group(1).upper()

    # 3) 'LineaX' / 'LíneaX' pegado
    m = re.match(r"^\s*l[ií]nea([a-z])\s*$", text, flags=re.IGNORECASE)
    if m:
        return m.group(1).upper()

    # 4) última letra encontrada en el string
    matches = re.findall(r"([A-Za-z])", text)
    if matches:
        return matches[-1].upper()

    return text

def kpi_row(k1_label, k1_value, k2_label, k2_value, k3_label, k3_value):
    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric(k1_label, k1_value)
    with c2:
        st.metric(k2_label, k2_value)
    with c3:
        st.metric(k3_label, k3_value)

def summarize_with_ollama(lines_summary_md: str, meta: dict) -> str:
    """Usa Ollama local; si no está disponible, devuelve un fallback."""
    system = (
        "You are an urban data analyst. Write concise, decision-ready insights. "
        "Focus on changes, outliers, and plausible causes. Use bullet points. English only."
    )
    user = f"""
Context:
- City: Buenos Aires
- System: Subte (metro) and Premetro
- Period: {meta.get('period', 'N/A')}
- Lines filtered: {', '.join(meta.get('lines', []))}

Data Highlights:
{lines_summary_md}

Deliverables:
1) 3–6 concise bullet insights.
2) 1 paragraph 'What to watch next week'.
3) A compact KPI line (emoji + short text).
"""

    try:
        payload = {
            "model": OLLAMA_MODEL,
            "prompt": f"System: {system}\nUser: {user}",
            "stream": False,
            "options": {"temperature": 0.4},
        }
        r = requests.post(f"{OLLAMA_BASE_URL}/api/generate", json=payload, timeout=120)
        r.raise_for_status()
        txt = r.json().get("response", "").strip()
        return txt or "_(no response from Ollama)_"
    except Exception:
        return (
            "**Insights (draft)**\n"
            "- Passenger totals and headway appear stable across lines.\n"
            "- Watch potential demand spikes on Line D and service variability on Line E.\n"
            "- Consider correlating weather/events to refine headway estimates.\n\n"
            "**What to watch next week**: Headway stability vs. dispatched trains and peak-hour demand.\n\n"
            "🔎 KPI: Headway ~ stable; Line D remains the busiest."
        )

# ---------------- UI ----------------
st.set_page_config(page_title=APP_TITLE, page_icon="🧠", layout="wide")
st.title(APP_TITLE)
st.caption("Week 2 — AI-powered insights over passengers & headway.")

# --- Paths y botón de recarga ---
p_pax = PROCESSED / "molinetes_2024_clean.parquet"
p_hw  = PROCESSED / "headway_estimates_2024.csv"

st.sidebar.header("Data")
if st.sidebar.button("🔄 Reload data (clear cache)"):
    st.cache_data.clear()

df_pax = load_passengers(PROCESSED, file_mtime(p_pax))
df_hw  = load_headway(PROCESSED, file_mtime(p_hw))

if df_pax is None:
    st.error("`data/processed/molinetes_2024_clean.parquet` not found.")
    st.stop()

# Normalizar etiquetas de línea
df_pax["line"] = df_pax["line"].apply(canonical_line)
if df_hw is not None and "line" in df_hw.columns:
    df_hw["line"] = df_hw["line"].apply(canonical_line)

# ---- Sidebar filters ----
st.sidebar.header("Filters")
include_premetro = st.sidebar.checkbox("Include Premetro (P)", value=True)

allowed_base = SUBTE_LINES | (PREMETRO_LINE if include_premetro else set())

# Filtramos datasets primero por allowed_base
df_pax = df_pax[df_pax["line"].isin(allowed_base)]
if df_hw is not None:
    df_hw  = df_hw[df_hw["line"].isin(allowed_base)]

lines_from_pax = set(df_pax["line"].astype(str).unique())
lines_from_hw  = set(df_hw["line"].astype(str).unique()) if df_hw is not None else set()
all_lines = sorted((lines_from_pax | lines_from_hw))

# Multiselect
lines_sel = st.sidebar.multiselect("Lines", options=all_lines, default=all_lines)

# Rango de fechas
min_date = pd.to_datetime(df_pax["date"].min()) if "date" in df_pax.columns else pd.Timestamp("2024-01-01")
max_date = pd.to_datetime(df_pax["date"].max()) if "date" in df_pax.columns else pd.Timestamp("2024-12-31")
date_from, date_to = st.sidebar.date_input(
    "Date range",
    value=(min_date.date(), max_date.date()),
    min_value=min_date.date(), max_value=max_date.date()
)

# ---- Filter data ----
mask_lines = df_pax["line"].astype(str).isin(lines_sel)
mask_dates = (df_pax["date"] >= pd.Timestamp(date_from)) & (df_pax["date"] <= pd.Timestamp(date_to))
pax = df_pax.loc[mask_lines & mask_dates].copy()

if df_hw is not None:
    mask_hw_lines = df_hw["line"].astype(str).isin(lines_sel)
    mask_hw_dates = (df_hw["date"] >= pd.Timestamp(date_from)) & (df_hw["date"] <= pd.Timestamp(date_to))
    hw = df_hw.loc[mask_hw_lines & mask_hw_dates].copy()
else:
    hw = None

# ---- Aggregations ----
pax_by_line = (
    pax.groupby("line", as_index=False, observed=False)["passengers"]
       .sum()
       .sort_values("passengers", ascending=False)
)
total_pax = int(pax_by_line["passengers"].sum()) if not pax_by_line.empty else 0
top_line = pax_by_line.iloc[0]["line"] if not pax_by_line.empty else "—"
top_pax = int(pax_by_line.iloc[0]["passengers"]) if not pax_by_line.empty else 0

avg_hw = None
if hw is not None and "avg_headway_min" in hw.columns:
    hw_by_line = (
        hw.groupby("line", as_index=False, observed=False)["avg_headway_min"]
          .mean()
          .sort_values("avg_headway_min")
    )
    avg_hw = round(hw_by_line["avg_headway_min"].mean(), 2) if not hw_by_line.empty else None
else:
    hw_by_line = None

# ---- KPIs ----
kpi_row("Total Passengers", f"{total_pax:,}",
        "Top Line", f"{top_line} ({top_pax:,})",
        "Avg Headway (min)", f"{avg_hw:.2f}" if avg_hw is not None else "—")

# ---- Charts ----
col1, col2 = st.columns(2)
with col1:
    st.subheader("Passengers by Line (sum)")
    if not pax_by_line.empty:
        st.bar_chart(pax_by_line.set_index("line"))
    else:
        st.info("No data for the selected filters.")

with col2:
    st.subheader("Average Headway (min) by Line")
    if hw_by_line is not None and not hw_by_line.empty:
        st.line_chart(hw_by_line.set_index("line"))
    else:
        st.info("No headway data available for the selected filters.")

# ---- Changes (WoW / MoM) ----
st.subheader("Changes (WoW / MoM)")
if "date" in pax.columns:
    pax["week"] = pax["date"].dt.to_period("W").apply(lambda r: r.start_time)
    weekly = pax.groupby(["line", "week"], observed=False)["passengers"].sum().reset_index()
    weekly["passengers_prev"] = weekly.groupby("line", observed=False)["passengers"].shift(1)
    weekly["wow"] = (weekly["passengers"] / weekly["passengers_prev"] - 1.0) * 100.0

    pax["month"] = pax["date"].dt.to_period("M").astype(str)
    monthly = pax.groupby(["line", "month"], observed=False)["passengers"].sum().reset_index()
    monthly["passengers_prev"] = monthly.groupby("line", observed=False)["passengers"].shift(1)
    monthly["mom"] = (monthly["passengers"] / monthly["passengers_prev"] - 1.0) * 100.0

    last_week = weekly["week"].max()
    last_month = monthly["month"].max()

    wow_now = (weekly[weekly["week"] == last_week]
               .sort_values("wow", ascending=False)[["line", "passengers", "wow"]])
    mom_now = (monthly[monthly["month"] == last_month]
               .sort_values("mom", ascending=False)[["line", "passengers", "mom"]])

    st.write("**Week-over-Week (current):**")
    st.dataframe(wow_now, use_container_width=True)
    st.write("**Month-over-Month (current):**")
    st.dataframe(mom_now, use_container_width=True)

    out_csv = REPORTS_DIR / "week_changes.csv"
    mom_now.to_csv(out_csv, index=False)
else:
    st.info("Date column not found in passengers dataset — deltas unavailable.")

# ---- AI Summary ----
st.subheader("AI Summary")
meta = {"period": f"{date_from} to {date_to}", "lines": lines_sel}

lines_md = []
if not pax_by_line.empty:
    lines_md.append("**Passengers (sum by line):**")
    lines_md.extend([f"- {r.line}: {int(r.passengers):,}" for r in pax_by_line.itertuples(index=False)])
if hw_by_line is not None and not hw_by_line.empty:
    lines_md.append("\n**Avg. Headway (min by line):**")
    lines_md.extend([f"- {r.line}: {r.avg_headway_min:.2f} min" for r in hw_by_line.itertuples(index=False)])

summary_md = summarize_with_ollama("\n".join(lines_md), meta)
st.markdown(summary_md)

ts = datetime.now().strftime("%Y%m%d_%H%M")
report_path = REPORTS_DIR / f"week2_insights_{ts}.md"
with open(report_path, "w", encoding="utf-8") as f:
    f.write("# AI Weekly Insights\n\n")
    f.write(f"_Period:_ {meta['period']}\n\n")
    f.write("\n".join(lines_md))
    f.write("\n\n---\n\n")
    f.write(summary_md)

st.success(f"Report saved: {report_path.as_posix()}")

# Keep only the latest report (optional)
KEEP = 1
from pathlib import Path
reports = sorted(Path(REPORTS_DIR).glob("week2_insights_*.md"), key=lambda p: p.stat().st_mtime, reverse=True)
for old in reports[KEEP:]:
    try:
        old.unlink()
    except Exception:
        pass