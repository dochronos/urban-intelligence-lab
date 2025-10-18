# scripts/validate_datasets.py
from pathlib import Path
import pandas as pd

ROOT = Path(".")
TARGETS = [
    ROOT / "data" / "processed" / "molinetes_2024_clean.parquet",
    ROOT / "data" / "processed" / "freq_from_form_2024.csv",
    ROOT / "data" / "processed" / "formaciones_2024.parquet",
]

LINE_CANDS = {"line", "línea", "linea", "line_name", "linea_nombre", "linea_id", "line_id"}
HEADWAY_CANDS_EXACT = {"avg_headway_min", "headway_min", "avg_headway"}
HEADWAY_KEYWORDS = ["headway", "frecuencia", "intervalo", "tiempo", "min"]

def read_any(p: Path):
    if not p.exists():
        print(f"⚠️ No existe: {p.name}")
        return None
    try:
        if p.suffix == ".csv":
            return pd.read_csv(p)
        elif p.suffix == ".parquet":
            return pd.read_parquet(p)
    except Exception as e:
        print(f"❌ No se pudo leer {p.name}: {e}")
    return None

def print_info(name, df: pd.DataFrame):
    print(f"\n📄 {name}")
    print(f"   filas={len(df):,}, columnas={len(df.columns)}")
    print("   columnas (tipo):")
    for c in df.columns:
        print(f"     - {c}  [{df[c].dtype}]")
    print("\n   primeras filas:")
    with pd.option_context("display.max_columns", 40, "display.width", 160):
        print(df.head(5))

    lowers = {c.lower(): c for c in df.columns}
    line_col = next((lowers[c] for c in LINE_CANDS if c in lowers), None)
    headway_exact = next((lowers[c] for c in HEADWAY_CANDS_EXACT if c in lowers), None)

    headway_kw = None
    for c in df.columns:
        cl = c.lower()
        if any(kw in cl for kw in HEADWAY_KEYWORDS) and pd.api.types.is_numeric_dtype(df[c]):
            headway_kw = c
            break

    print("\n   ▶️ Detección:")
    print(f"     - line_col: {line_col}")
    print(f"     - headway (exact): {headway_exact}")
    print(f"     - headway (keyword numérica): {headway_kw}")

def main():
    print("🔎 Validando datasets clave en data/processed ...")
    for p in TARGETS:
        df = read_any(p)
        if df is not None and not df.empty:
            print_info(p.name, df)
        else:
            print(f"   (vacío o no legible) {p.name}")

if __name__ == "__main__":
    main()
