# scripts/etl_headway_from_formaciones.py
from pathlib import Path
import pandas as pd

PROCESSED = Path("data/processed")
PROCESSED.mkdir(parents=True, exist_ok=True)

# ===================== Supuestos (ajustables) =====================
# Minutos operativos por día: ej. 05:30–23:30 => 18h => 1080 min
OPERATING_MIN_PER_DAY = 1080

# Algunos conteos de "trenes despachados" pueden estar sobredimensionados
# para estimar headway; incluimos una calibración opcional:
CALIBRATION_FACTOR = 1.0        # multiplicador fijo (1.0 = sin calibración)
AUTO_CALIBRATE = True           # si True, ajusta a una mediana objetivo
TARGET_MEDIAN_HEADWAY = 3.5     # minutos (p.ej. 3.5 min como benchmark)

# ===================== Entradas/Salida =====================
SRC_MONTHLY = PROCESSED / "freq_from_form_2024.csv"     # cols: year_month, line, dispatched_trains
SRC_DAILY   = PROCESSED / "formaciones_2024.parquet"    # cols: date (datetime), line, trains

OUT_HEADWAY = PROCESSED / "headway_estimates_2024.csv"  # cols: year_month, line, avg_headway_min, source


# ===================== Helpers =====================
def canonical_line(s):
    """Normaliza etiquetas de línea a una sola letra A–H (e.g., 'LineaB' -> 'B')."""
    if pd.isna(s):
        return s
    import re
    text = str(s).strip()
    # 1) Ya es una sola letra
    if re.fullmatch(r"[A-H]", text, flags=re.IGNORECASE):
        return text.upper()
    # 2) 'Linea X' / 'Línea X' (con o sin espacio)
    m = re.match(r"^\s*l[ií]nea\s*([a-h])\s*$", text, flags=re.IGNORECASE)
    if m:
        return m.group(1).upper()
    # 3) 'LineaX' / 'LíneaX'
    m = re.match(r"^\s*l[ií]nea([a-h])\s*$", text, flags=re.IGNORECASE)
    if m:
        return m.group(1).upper()
    # 4) Última letra A–H encontrada
    matches = re.findall(r"([A-H])", text, flags=re.IGNORECASE)
    if matches:
        return matches[-1].upper()
    return text


def headway_from_monthly(df_m: pd.DataFrame) -> pd.DataFrame:
    """
    df_m con columnas: year_month (YYYY-MM), line, dispatched_trains (int)
    Fórmula (proxy):
        avg_headway_min = (OPERATING_MIN_PER_DAY * days_in_month) / dispatched_trains_month
    """
    req_cols = {"year_month", "line", "dispatched_trains"}
    if not req_cols.issubset(df_m.columns):
        raise ValueError("freq_from_form_2024.csv debe tener columnas: year_month, line, dispatched_trains")

    df = df_m.copy()
    df["line"] = df["line"].apply(canonical_line)

    # days_in_month desde year_month=YYYY-MM
    ym = pd.to_datetime(df["year_month"] + "-01", errors="coerce")
    df["days_in_month"] = ym.dt.days_in_month

    # sanity
    df["dispatched_trains"] = pd.to_numeric(df["dispatched_trains"], errors="coerce").fillna(0)
    df = df[(df["dispatched_trains"] > 0) & df["days_in_month"].notna()]

    df["avg_headway_min"] = (OPERATING_MIN_PER_DAY * df["days_in_month"]) / df["dispatched_trains"]
    df["source"] = "monthly_dispatched_trains"

    return df[["year_month", "line", "avg_headway_min", "source"]]


def headway_from_daily(df_d: pd.DataFrame) -> pd.DataFrame:
    """
    df_d con columnas: date (datetime-like), line, trains (int)
    Agregamos por (year_month, line) => sum(trains) y aplicamos la misma fórmula.
    """
    req_cols = {"date", "line", "trains"}
    if not req_cols.issubset(df_d.columns):
        raise ValueError("formaciones_2024.parquet debe tener columnas: date, line, trains")

    df = df_d.copy()
    df["line"] = df["line"].apply(canonical_line)

    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df[df["date"].notna()]

    df["year_month"] = df["date"].dt.strftime("%Y-%m")
    g = (df.groupby(["year_month", "line"], observed=False, as_index=False)["trains"]
           .sum()
           .rename(columns={"trains": "dispatched_trains"}))

    ym = pd.to_datetime(g["year_month"] + "-01", errors="coerce")
    g["days_in_month"] = ym.dt.days_in_month
    g = g[(g["dispatched_trains"] > 0) & g["days_in_month"].notna()]

    g["avg_headway_min"] = (OPERATING_MIN_PER_DAY * g["days_in_month"]) / g["dispatched_trains"]
    g["source"] = "daily_trains_aggregated"

    return g[["year_month", "line", "avg_headway_min", "source"]]


def apply_calibration(df_out: pd.DataFrame) -> pd.DataFrame:
    """Aplica calibración global para llevar la mediana a un rango plausible."""
    if df_out.empty or "avg_headway_min" not in df_out.columns:
        return df_out

    df = df_out.copy()
    if AUTO_CALIBRATE:
        med = df["avg_headway_min"].median()
        if pd.notna(med) and med > 0:
            factor = TARGET_MEDIAN_HEADWAY / med
            df["avg_headway_min"] = df["avg_headway_min"] * factor
    elif CALIBRATION_FACTOR != 1.0:
        df["avg_headway_min"] = df["avg_headway_min"] * CALIBRATION_FACTOR

    return df


# ===================== Main =====================
def main():
    out_frames = []

    # Preferimos mensual si existe
    if SRC_MONTHLY.exists():
        try:
            dfm = pd.read_csv(SRC_MONTHLY)
            out_frames.append(headway_from_monthly(dfm))
            print(f"✅ Headway desde {SRC_MONTHLY.name}")
        except Exception as e:
            print(f"[WARN] No se pudo procesar {SRC_MONTHLY.name}: {e}")

    # Si no hubo mensual válido, probamos diario → mensualizado
    if not out_frames and SRC_DAILY.exists():
        try:
            dfd = pd.read_parquet(SRC_DAILY)
            out_frames.append(headway_from_daily(dfd))
            print(f"✅ Headway desde {SRC_DAILY.name}")
        except Exception as e:
            print(f"[WARN] No se pudo procesar {SRC_DAILY.name}: {e}")

    if not out_frames:
        print("⚠️ No se encontraron entradas válidas. Necesitás freq_from_form_2024.csv o formaciones_2024.parquet.")
        return

    df_out = pd.concat(out_frames, ignore_index=True)
    # Si existen ambas fuentes, por orden de preferencia ya quedó primero mensual;
    # eliminamos duplicados por (year_month, line)
    df_out = (df_out.sort_values(["year_month", "line", "source"])
                    .drop_duplicates(subset=["year_month", "line"], keep="first"))

    # ▶️ Calibración
    before = df_out["avg_headway_min"].median() if not df_out.empty else None
    df_out = apply_calibration(df_out)
    after = df_out["avg_headway_min"].median() if not df_out.empty else None
    if before is not None and after is not None:
        print(f"Calibrated median headway: {before:.2f} → {after:.2f} min")

    df_out.to_csv(OUT_HEADWAY, index=False)
    print(f"💾 Guardado: {OUT_HEADWAY.as_posix()}")
    with pd.option_context("display.max_rows", 10):
        print(df_out.head(10).to_string(index=False))


if __name__ == "__main__":
    main()
