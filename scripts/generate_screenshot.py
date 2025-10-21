# scripts/generate_screenshot.py
from pathlib import Path
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

APP_TITLE = "Urban Intelligence Lab — Week 1 · Unified Foundations"
ROOT = Path(".")
PROCESSED = ROOT / "data" / "processed"
OUT_DIR = ROOT / "assets" / "screenshots"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# ---------- Helpers ----------
def read_parquet_or_none(p: Path):
    try:
        return pd.read_parquet(p) if p.exists() else None
    except Exception as e:
        print(f"[WARN] Unable to read {p.name}: {e}")
        return None

def read_csv_or_none(p: Path):
    try:
        return pd.read_csv(p) if p.exists() else None
    except Exception as e:
        print(f"[WARN] Unable to read {p.name}: {e}")
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

# ---------- Load passengers (sum by line) ----------
def load_passengers():
    src = PROCESSED / "molinetes_2024_clean.parquet"
    df = read_parquet_or_none(src)
    if df is not None and not df.empty and "line" in df.columns and "passengers" in df.columns:
        agg = group_sum_by_line(df, "line", "passengers")
        agg = agg.rename(columns={"value": "passengers"})
        return agg, src.name
    # DEMO fallback
    agg = pd.DataFrame({
        "line": ["A", "B", "C", "D", "E", "H"],
        "passengers": [120_000, 95_000, 87_000, 110_000, 76_000, 64_000]
    })
    return agg, "DEMO"

# ---------- Load headway/service (prefer headway_estimates) ----------
def load_other_metric():
    """
    Priority:
      a) headway_estimates_2024.csv (avg_headway_min)
      b) freq_from_form_2024.csv (service: dispatched_trains)
      c) formaciones_2024.parquet (service: trains)
      d) DEMO headway
    """
    # a) headway estimates
    src_h = PROCESSED / "headway_estimates_2024.csv"
    dfh = read_csv_or_none(src_h)
    if dfh is not None and not dfh.empty and "line" in dfh.columns and "avg_headway_min" in dfh.columns:
        if "year_month" in dfh.columns:
            agg = (dfh.groupby("line", as_index=False, observed=False)[["avg_headway_min"]]
                     .mean()
                     .rename(columns={"avg_headway_min": "value"})
                     .sort_values("line"))
        else:
            agg = dfh.rename(columns={"avg_headway_min": "value"})[["line", "value"]].sort_values("line")
        return agg, "headway", src_h.name, "Average Headway (min)", "avg_headway_min"

    # b) service monthly
    src_a = PROCESSED / "freq_from_form_2024.csv"
    dfa = read_csv_or_none(src_a)
    if dfa is not None and not dfa.empty and "line" in dfa.columns and "dispatched_trains" in dfa.columns:
        agg = group_mean_by_line(dfa, "line", "dispatched_trains").rename(columns={"value": "service_level"})
        agg = agg.rename(columns={"service_level": "value"})
        return agg, "service", src_a.name, "Service Level (trains dispatched)", "service_level"

    # c) service daily
    src_b = PROCESSED / "formaciones_2024.parquet"
    dfb = read_parquet_or_none(src_b)
    if dfb is not None and not dfb.empty and "line" in dfb.columns and "trains" in dfb.columns:
        agg = group_mean_by_line(dfb, "line", "trains").rename(columns={"value": "service_level"})
        agg = agg.rename(columns={"service_level": "value"})
        return agg, "service", src_b.name, "Service Level (trains dispatched)", "service_level"

    # d) DEMO headway
    demo = pd.DataFrame({
        "line": ["A", "B", "C", "D", "E", "H"],
        "value": [3.5, 4.0, 4.2, 3.8, 5.0, 4.6]
    })
    return demo, "headway", "DEMO", "Average Headway (min)", "avg_headway_min"

def main():
    df_passengers, src_pass = load_passengers()
    df_other, kind, src_other, other_title, other_y = load_other_metric()

    # --- Build subplots ---
    fig = make_subplots(
        rows=1, cols=2,
        subplot_titles=("Passengers by Line", other_title),
        horizontal_spacing=0.12
    )

    # Bar - passengers
    fig.add_trace(
        go.Bar(x=df_passengers["line"], y=df_passengers["passengers"], name="Passengers"),
        row=1, col=1
    )

    # Line - headway/service
    fig.add_trace(
        go.Scatter(x=df_other["line"], y=df_other["value"], mode="lines+markers", name=other_y),
        row=1, col=2
    )

    # Layout
    fig.update_layout(
        title=APP_TITLE,
        margin=dict(l=50, r=50, t=80, b=50),
        showlegend=False,
        height=900, width=1600,
        annotations=[
            # Data Source annotation (bottom-left)
            dict(
                text=f"Data Source → passengers: {src_pass} | {('headway' if kind=='headway' else 'service')}: {src_other}",
                xref="paper", yref="paper",
                x=0, y=-0.08, showarrow=False, align="left"
            )
        ]
    )

    # Ejes
    fig.update_xaxes(title_text="Line", row=1, col=1)
    fig.update_yaxes(title_text="Passengers (sum)", row=1, col=1)

    if kind == "headway":
        fig.update_xaxes(title_text="Line", row=1, col=2)
        fig.update_yaxes(title_text="Average Headway (min)", row=1, col=2)
    else:
        fig.update_xaxes(title_text="Line", row=1, col=2)
        fig.update_yaxes(title_text="Trains (mean)", row=1, col=2)

    # Export
    out_png = OUT_DIR / "week1_dashboard.png"
    fig.write_image(out_png.as_posix(), format="png", scale=2)  # 3200x1800
    print(f"✅ Saved: {out_png.as_posix()}")

    # Alt text helper (opcional)
    alt_text = (
        "Urban Intelligence Lab – Week 1 dashboard showing passengers by line and "
        f"{'average headway (min)' if kind=='headway' else 'service level (trains dispatched)'} "
        "for Buenos Aires Subte. Data sources indicated in caption."
    )
    with open((OUT_DIR / "week1_dashboard_alt.txt"), "w", encoding="utf-8") as f:
        f.write(alt_text)
    print("📝 Alt text saved to assets/screenshots/week1_dashboard_alt.txt")

if __name__ == "__main__":
    main()
