# scripts/forecast_passengers.py
from pathlib import Path
from datetime import datetime, timedelta
import re
import numpy as np
import pandas as pd

ROOT = Path(".")
PROCESSED = ROOT / "data" / "processed"
IN_PARQUET = PROCESSED / "molinetes_2024_clean.parquet"
IN_DISPATCH = PROCESSED / "freq_from_form_2024.csv"
OUT_CSV = PROCESSED / "passengers_forecast_weekly.csv"

SUBTE = {"A","B","C","D","E","H"}
PREMETRO = {"P"}

def normalize_line(val: str) -> str:
    if not isinstance(val, str):
        return str(val)
    s = val.strip()
    if re.search(r"premetro", s, re.IGNORECASE):
        return "P"
    m = re.search(r"[Ll][ií]ne?a\s*([A-Za-z])", s)
    if m:
        return m.group(1).upper()
    if len(s) == 1 and s.upper() in (SUBTE | PREMETRO):
        return s.upper()
    m = re.search(r"([A-Za-z])", s)
    if m and m.group(1).upper() in (SUBTE | PREMETRO):
        return m.group(1).upper()
    return s

def load_passengers() -> pd.DataFrame:
    if not IN_PARQUET.exists():
        raise FileNotFoundError(f"Missing {IN_PARQUET.as_posix()}")
    df = pd.read_parquet(IN_PARQUET)
    df["date"] = pd.to_datetime(df["date"])
    df["line"] = df["line"].astype(str).map(normalize_line)
    df = df[df["line"].isin(SUBTE | PREMETRO)]
    return df

def weekly_agg(df: pd.DataFrame) -> pd.DataFrame:
    df["week"] = df["date"].dt.to_period("W").apply(lambda r: r.start_time)
    wk = (df.groupby(["line","week"], observed=False)["passengers"]
            .sum().reset_index().sort_values(["line","week"]))
    return wk

def monthly_passengers(df: pd.DataFrame) -> pd.DataFrame:
    df["ym"] = df["date"].dt.to_period("M").astype(str)
    m = (df.groupby(["line","ym"], observed=False)["passengers"]
           .sum().reset_index().sort_values(["line","ym"]))
    return m

def load_dispatch_monthly() -> pd.DataFrame | None:
    if not IN_DISPATCH.exists():
        return None
    d = pd.read_csv(IN_DISPATCH)
    # columnas esperadas: year_month, line, dispatched_trains
    # normalizar línea
    d["line"] = d["line"].astype(str).map(normalize_line)
    d = d[d["line"].isin(SUBTE | PREMETRO)]
    # estandarizar year_month -> 'YYYY-MM'
    d["ym"] = d["year_month"].astype(str)
    return d[["ym","line","dispatched_trains"]].copy()

def distribute_month_to_weeks(year: int, month: int) -> list[datetime]:
    """Devuelve los Mondays de las semanas que caen dentro del mes (para repartir uniforme)."""
    # Primer Monday <= primer día del mes
    first_day = datetime(year, month, 1)
    first_monday = first_day - timedelta(days=(first_day.weekday()))  # lunes de esa semana
    weeks = []
    cur = first_monday
    while True:
        # semana [cur .. cur+6]
        week_end = cur + timedelta(days=6)
        # si toda la semana está después del mes y aún no entramos, seguimos
        if week_end.month < month and week_end.year == year:
            cur += timedelta(days=7)
            continue
        # si el inicio ya es después del mes, cortamos
        if cur.year > year or (cur.year == year and cur.month > month and cur.day >= 1):
            break
        # si la semana tiene al menos un día dentro del mes -> la contamos
        if cur.month == month or week_end.month == month:
            weeks.append(cur)
        # avanzar
        cur += timedelta(days=7)
        # fin cuando superamos el último día del mes
        if cur.month > month and cur.year == year and cur.day >= 1:
            # todavía puede quedar una semana que toca fin de mes
            pass
        if cur.year > year or (cur.year == year and cur.month > month and cur.day >= 7):
            break
    # filtrar duplicados y ordenar
    weeks = sorted(list(dict.fromkeys(weeks)))
    # mantener solo weeks que toquen el mes
    weeks = [w for w in weeks if (w.month == month) or ((w + timedelta(days=6)).month == month)]
    return weeks

def estimate_p_from_dispatch(pax_monthly: pd.DataFrame, disp_monthly: pd.DataFrame) -> pd.DataFrame:
    """Estimación de pasajeros de P por mes usando ratio pax/train de A..H."""
    if disp_monthly is None or disp_monthly.empty:
        return pd.DataFrame(columns=["line","week","passengers"])
    # Ratio por mes usando A..H
    pax_ah = pax_monthly[pax_monthly["line"].isin(SUBTE)].groupby("ym", observed=False)["passengers"].sum()
    tr_ah = disp_monthly[disp_monthly["line"].isin(SUBTE)].groupby("ym", observed=False)["dispatched_trains"].sum()
    ratio = (pax_ah / tr_ah).replace([np.inf, -np.inf], np.nan).dropna()
    if ratio.empty:
        return pd.DataFrame(columns=["line","week","passengers"])
    # Para P: estimar pax_m = trains_P_m * ratio_m (o ratio global si falta ese mes)
    disp_p = disp_monthly[disp_monthly["line"] == "P"].copy()
    if disp_p.empty:
        return pd.DataFrame(columns=["line","week","passengers"])
    # ratio global fallback
    fallback = ratio.median()
    disp_p["est_pax_month"] = disp_p.apply(
        lambda r: r["dispatched_trains"] * (ratio.get(r["ym"], fallback)), axis=1
    )
    # repartir cada mes en semanas del mes
    rows = []
    for _, row in disp_p.iterrows():
        ym = row["ym"]
        y, m = map(int, ym.split("-"))
        weeks = distribute_month_to_weeks(y, m)
        if not weeks:
            continue
        each = float(row["est_pax_month"]) / len(weeks)
        for w in weeks:
            rows.append({"line": "P", "week": w, "passengers": each})
    wk_p = pd.DataFrame(rows)
    if wk_p.empty:
        return wk_p
    # agrupar por week (por si un mes trae 5 semanas)
    wk_p = wk_p.groupby(["line","week"], observed=False)["passengers"].sum().reset_index()
    return wk_p

def trend_forecast_one(series: pd.Series, n_future=4, min_points=6):
    s = series.dropna()
    if len(s) == 0:
        return (pd.Series(dtype=float),)*3
    if len(s) < min_points:
        last = float(s.iloc[-1])
        idx = pd.date_range(s.index[-1] + timedelta(days=7), periods=n_future, freq="W-MON")
        yhat = pd.Series([last]*n_future, index=idx)
        return yhat, yhat.copy(), yhat.copy()
    x = np.arange(len(s))
    y = s.values.astype(float)
    slope, intercept = np.polyfit(x, y, 1)
    y_hat_hist = intercept + slope * x
    resid = y - y_hat_hist
    sigma = np.std(resid) if len(resid) > 1 else 0.0
    x_f = np.arange(len(s), len(s)+n_future)
    y_f = intercept + slope * x_f
    idx = pd.date_range(s.index[-1] + timedelta(days=7), periods=n_future, freq="W-MON")
    yhat = pd.Series(y_f, index=idx)
    lo = pd.Series(y_f - 1.64*sigma, index=idx)
    hi = pd.Series(y_f + 1.64*sigma, index=idx)
    return yhat, lo, hi

def build_forecast(wk_all: pd.DataFrame, horizon=4) -> pd.DataFrame:
    out = []
    for line, g in wk_all.groupby("line"):
        s = g.set_index("week")["passengers"].asfreq("W-MON")
        yhat, lo, hi = trend_forecast_one(s, n_future=horizon)
        if len(yhat) == 0:
            continue
        out.append(pd.DataFrame({
            "line": line,
            "week": yhat.index,
            "yhat": yhat.values,
            "yhat_low": lo.values,
            "yhat_high": hi.values
        }))
    return pd.concat(out, ignore_index=True).sort_values(["line","week"]) if out else pd.DataFrame(
        columns=["line","week","yhat","yhat_low","yhat_high"]
    )

def main():
    PROCESSED.mkdir(parents=True, exist_ok=True)

    # Reales A..H
    df = load_passengers()
    wk_real = weekly_agg(df[df["line"].isin(SUBTE)])

    # Estimar P desde despachos si está disponible
    disp = load_dispatch_monthly()
    pax_m = monthly_passengers(df[df["line"].isin(SUBTE)])  # monthly reales A..H
    wk_p = estimate_p_from_dispatch(pax_m, disp)

    # Unir
    wk_all = wk_real.copy()
    if wk_p is not None and not wk_p.empty:
        wk_all = pd.concat([wk_all, wk_p], ignore_index=True)

    # Pronóstico
    fc = build_forecast(wk_all, horizon=4)
    fc.to_csv(OUT_CSV, index=False)
    print(f"✅ Forecast saved: {OUT_CSV.as_posix()}")
    print(fc.head(12).to_string(index=False))

if __name__ == "__main__":
    main()
