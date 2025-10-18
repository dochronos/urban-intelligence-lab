# scripts/etl_headway_from_formaciones.py
from pathlib import Path
import pandas as pd

PROCESSED = Path("data/processed")
PROCESSED.mkdir(parents=True, exist_ok=True)

# ===== Supuestos (ajustables) =====
# Tiempo operativo por día (minutos): p.ej. 05:30–23:30 => 18 h => 1080 minutos
OPERATING_MIN_PER_DAY = 1080

# ===== Entradas =====
SRC_MONTHLY = PROCESSED / "freq_from_form_2024.csv"        # columns: year_month, line, dispatched_trains
SRC_DAILY   = PROCESSED / "formaciones_2024.parquet"       # columns: date (datetime), line, trains

# ===== Salida =====
OUT_HEADWAY = PROCESSED / "headway_estimates_2024.csv"     # columns: year_month, line, avg_headway_min, source

def headway_from_monthly(df_m):
    """
    df_m: columns [year_month, line, dispatched_trains]
    Fórmula (proxy):
        avg_headway_min = OPERATING_MIN_PER_DAY * days_in_month / dispatched_trains_month
    """
    # asegurar tipos
    df = df_m.copy()
    if "year_month" not in df.columns or "line" not in df.columns or "dispatched_trains" not in df.columns:
        raise ValueError("freq_from_form_2024.csv debe tener columnas: year_month, line, dispatched_trains")

    # days_in_month: inferimos desde year_month=YYYY-MM
    ym = pd.to_datetime(df["year_month"] + "-01")
    days = ym.dt.days_in_month
    df["days_in_month"] = days

    # evitar div/0
    df["dispatched_trains"] = pd.to_numeric(df["dispatched_trains"], errors="coerce").fillna(0)
    df = df[df["dispatched_trains"] > 0]

    df["avg_headway_min"] = (OPERATING_MIN_PER_DAY * df["days_in_month"]) / df["dispatched_trains"]
    df["source"] = "monthly_dispatched_trains"
    return df[["year_month", "line", "avg_headway_min", "source"]]

def headway_from_daily(df_d):
    """
    df_d: columns [date (datetime), line, trains]
    Agregamos por (year_month, line) => sum(trains)
    Luego aplicamos la misma fórmula de arriba.
    """
    df = df_d.copy()
    if "date" not in df.columns or "line" not in df.columns or "trains" not in df.columns:
        raise ValueError("formaciones_2024.parquet debe tener columnas: date, line, trains")

    df["date"] = pd.to_datetime(df["date"])
    df["year_month"] = df["date"].dt.strftime("%Y-%m")
    g = (df.groupby(["year_month", "line"], observed=False, as_index=False)["trains"]
           .sum()
           .rename(columns={"trains": "dispatched_trains"}))

    # days_in_month para cada year_month
    ym = pd.to_datetime(g["year_month"] + "-01")
    g["days_in_month"] = ym.dt.days_in_month
    g = g[g["dispatched_trains"] > 0]

    g["avg_headway_min"] = (OPERATING_MIN_PER_DAY * g["days_in_month"]) / g["dispatched_trains"]
    g["source"] = "daily_trains_aggregated"
    return g[["year_month", "line", "avg_headway_min", "source"]]

def main():
    out = []

    if SRC_MONTHLY.exists():
        try:
            dfm = pd.read_csv(SRC_MONTHLY)
            out.append(headway_from_monthly(dfm))
            print(f"✅ Headway desde {SRC_MONTHLY.name}")
        except Exception as e:
            print(f"[WARN] No se pudo procesar {SRC_MONTHLY.name}: {e}")

    if not out and SRC_DAILY.exists():
        try:
            dfd = pd.read_parquet(SRC_DAILY)
            out.append(headway_from_daily(dfd))
            print(f"✅ Headway desde {SRC_DAILY.name}")
        except Exception as e:
            print(f"[WARN] No se pudo procesar {SRC_DAILY.name}: {e}")

    if not out:
        print("⚠️ No se encontraron entradas válidas. Necesitas freq_from_form_2024.csv o formaciones_2024.parquet.")
        return

    df_out = pd.concat(out, ignore_index=True)
    # Si existen ambas fuentes, preferimos la mensual (más estable) y eliminamos duplicados
    df_out = (df_out.sort_values(["year_month", "line", "source"])
                    .drop_duplicates(subset=["year_month", "line"], keep="first"))

    df_out.to_csv(OUT_HEADWAY, index=False)
    print(f"💾 Guardado: {OUT_HEADWAY.as_posix()}")
    print(df_out.head(10).to_string(index=False))

if __name__ == "__main__":
    main()
