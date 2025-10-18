# app/main_dashboard.py
from pathlib import Path
import pandas as pd
from dash import Dash, dcc, html
import dash_bootstrap_components as dbc
import plotly.express as px

APP_TITLE = "Urban Intelligence Lab — Week 1 · Unified Foundations"

DATA_DIR = Path("data")
PROCESSED = DATA_DIR / "processed"

# --- Helpers ---
def read_parquet_or_none(p: Path):
    try:
        return pd.read_parquet(p) if p.exists() else None
    except Exception as e:
        print(f"[WARN] No pude leer {p.name}: {e}")
        return None

def read_csv_or_none(p: Path):
    try:
        return pd.read_csv(p) if p.exists() else None
    except Exception as e:
        print(f"[WARN] No pude leer {p.name}: {e}")
        return None

def group_sum_by_line(df: pd.DataFrame, line_col: str, value_col: str):
    return (df.groupby(line_col, as_index=False, observed=False)[[value_col]]
              .sum()
              .rename(columns={line_col: "line", value_col: "value"})
              .sort_values("line"))

def group_mean_by_line(df: pd.DataFrame, line_col: str, value_col: str):
    return (df.groupby(line_col, as_index=False, observed=False)[[value_col]]
              .mean()
              .rename(columns={line_col: "line", value_col: "value"})
              .sort_values("line"))

# --- 1) Passengers ---
def load_passengers():
    src = PROCESSED / "molinetes_2024_clean.parquet"
    df = read_parquet_or_none(src)
    if df is not None and not df.empty and "line" in df.columns and "passengers" in df.columns:
        agg = group_sum_by_line(df, "line", "passengers")
        agg = agg.rename(columns={"value": "passengers"})
        return agg, src.name
    # DEMO
    agg = pd.DataFrame({
        "line": ["A", "B", "C", "D", "E", "H"],
        "passengers": [120_000, 95_000, 87_000, 110_000, 76_000, 64_000]
    })
    return agg, "DEMO"

# --- 2) Headway/Service ---
def load_other_metric():
    """
    Prioridad:
      a) Headway estimado desde headway_estimates_2024.csv (avg_headway_min)
      b) Service desde freq_from_form_2024.csv (dispatched_trains)
      c) Service desde formaciones_2024.parquet (trains)
      d) DEMO headway
    """
    # a) Headway estimado (nuevo ETL)
    src_h = PROCESSED / "headway_estimates_2024.csv"
    dfh = read_csv_or_none(src_h)
    if dfh is not None and not dfh.empty and "line" in dfh.columns and "avg_headway_min" in dfh.columns:
        # si viene por year_month, hacemos promedio mensual por línea
        if "year_month" in dfh.columns:
            agg = (dfh.groupby("line", as_index=False, observed=False)[["avg_headway_min"]]
                      .mean()
                      .rename(columns={"avg_headway_min": "value"})
                      .sort_values("line"))
        else:
            agg = dfh.rename(columns={"avg_headway_min": "value"})[["line", "value"]].sort_values("line")
        agg = agg.rename(columns={"value": "avg_headway_min"})
        return agg, "headway", src_h.name, "Average Headway (min)", "avg_headway_min"

    # b) Service (mensual)
    src_a = PROCESSED / "freq_from_form_2024.csv"
    dfa = read_csv_or_none(src_a)
    if dfa is not None and not dfa.empty and "line" in dfa.columns and "dispatched_trains" in dfa.columns:
        agg = group_mean_by_line(dfa, "line", "dispatched_trains").rename(columns={"value": "service_level"})
        return agg, "service", src_a.name, "Service Level (trains dispatched)", "service_level"

    # c) Service (diario)
    src_b = PROCESSED / "formaciones_2024.parquet"
    dfb = read_parquet_or_none(src_b)
    if dfb is not None and not dfb.empty and "line" in dfb.columns and "trains" in dfb.columns:
        agg = group_mean_by_line(dfb, "line", "trains").rename(columns={"value": "service_level"})
        return agg, "service", src_b.name, "Service Level (trains dispatched)", "service_level"

    # d) DEMO
    demo = pd.DataFrame({
        "line": ["A", "B", "C", "D", "E", "H"],
        "avg_headway_min": [3.5, 4.0, 4.2, 3.8, 5.0, 4.6]
    })
    return demo, "headway", "DEMO", "Average Headway (min)", "avg_headway_min"

# --- Load data ---
df_passengers, src_pass = load_passengers()
df_other, kind, src_other, other_title, other_y = load_other_metric()

# --- Figures ---
fig_passengers = px.bar(df_passengers, x="line", y="passengers", title="Passengers by Line")
fig_other = px.line(df_other, x="line", y=other_y, markers=True, title=other_title)

# --- App ---
app = Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP], title=APP_TITLE)
source_label = f"passengers: {src_pass} | {('service' if kind=='service' else 'headway')}: {src_other}"

app.layout = dbc.Container([
    html.H1(APP_TITLE, className="my-3"),
    dbc.Row([
        dbc.Col(dbc.Card([
            dbc.CardHeader("Data Source"),
            dbc.CardBody(html.Pre(source_label, style={"margin": 0}))
        ]), width=12)
    ]),
    dbc.Row([
        dbc.Col(dbc.Card([
            dbc.CardHeader("Passengers by Line"),
            dbc.CardBody(dcc.Graph(figure=fig_passengers))
        ]), md=6),
        dbc.Col(dbc.Card([
            dbc.CardHeader(other_title),
            dbc.CardBody(dcc.Graph(figure=fig_other))
        ]), md=6),
    ], className="g-3"),
    html.Hr(),
    html.Footer("UIL · Business Intelligence meets Machine Learning", className="text-muted my-3")
], fluid=True)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8050, debug=True)
