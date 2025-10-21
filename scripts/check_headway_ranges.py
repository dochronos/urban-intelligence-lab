# scripts/check_headway_ranges.py
from pathlib import Path
import pandas as pd

p = Path("data/processed/headway_estimates_2024.csv")
df = pd.read_csv(p)
bad = df[(df["avg_headway_min"] < 1) | (df["avg_headway_min"] > 20)]
print("Rows outside [1, 20] min:\n", bad if not bad.empty else "✅ None")
