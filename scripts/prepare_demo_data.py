# scripts/prepare_demo_data.py
from pathlib import Path
import pandas as pd

PROCESSED = Path("data/processed")
PROCESSED.mkdir(parents=True, exist_ok=True)

# Demo consistente con las métricas esperadas por el dashboard
df_passengers = pd.DataFrame({
    "line": ["A", "B", "C", "D", "E", "H"],
    "passengers": [120000, 95000, 87000, 110000, 76000, 64000]
})

df_freq = pd.DataFrame({
    "line": ["A", "B", "C", "D", "E", "H"],
    "avg_headway_min": [3.5, 4.0, 4.2, 3.8, 5.0, 4.6]
})

# Unimos en un solo dataset “amigable”
df_demo = pd.merge(df_passengers, df_freq, on="line")

# Guardamos en CSV y Parquet
df_demo.to_csv(PROCESSED / "uil_demo.csv", index=False)
try:
    df_demo.to_parquet(PROCESSED / "uil_demo.parquet", index=False)
except Exception as e:
    print(f"[WARN] No se pudo escribir parquet: {e}")

print("✅ Demo datasets listos en data/processed: uil_demo.csv / uil_demo.parquet")
