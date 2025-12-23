from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
import pandas as pd
import numpy as np


@dataclass
class AnomalyConfig:
    date_col: str = "fecha"
    value_col: str = "pax_total"
    station_col: Optional[str] = "estacion"
    freq: str = "D"               # daily aggregation
    window: int = 14              # rolling window
    z_threshold: float = 3.0      # anomaly threshold
    min_periods: int = 7          # minimum points for rolling stats


def prepare_daily_series(df: pd.DataFrame, cfg: AnomalyConfig) -> pd.DataFrame:
    """
    Convert raw turnstile data into a daily time series.
    If station_col exists -> aggregated by date and station.
    Else -> aggregated only by date.
    """
    dfx = df.copy()
    dfx.columns = dfx.columns.str.strip().str.lower()

    if cfg.date_col not in dfx.columns or cfg.value_col not in dfx.columns:
        raise ValueError(f"Missing required columns: {cfg.date_col}, {cfg.value_col}")

    # parse date safely (dayfirst for Argentina-like formats)
    dfx[cfg.date_col] = pd.to_datetime(dfx[cfg.date_col], dayfirst=True, errors="coerce")
    dfx = dfx.dropna(subset=[cfg.date_col])

    # numeric value
    dfx[cfg.value_col] = pd.to_numeric(dfx[cfg.value_col], errors="coerce").fillna(0)

    # daily bucket
    dfx["date_bucket"] = dfx[cfg.date_col].dt.floor(cfg.freq)

    group_cols = ["date_bucket"]
    if cfg.station_col and cfg.station_col in dfx.columns:
        group_cols.append(cfg.station_col)

    out = (
        dfx.groupby(group_cols, as_index=False)[cfg.value_col]
        .sum()
        .rename(columns={"date_bucket": "date"})
    )

    return out


def detect_anomalies(series_df: pd.DataFrame, cfg: AnomalyConfig) -> pd.DataFrame:
    """
    Adds rolling mean/std and z-score, then flags anomalies.
    Expects 'date' and value col present, optionally station.
    """
    dfx = series_df.copy()

    # sort
    sort_cols = ["date"]
    if cfg.station_col and cfg.station_col in dfx.columns:
        sort_cols = [cfg.station_col, "date"]
    dfx = dfx.sort_values(sort_cols).reset_index(drop=True)

    # apply rolling stats per station (if available) else global
    if cfg.station_col and cfg.station_col in dfx.columns:
        g = dfx.groupby(cfg.station_col, group_keys=False)
        dfx["rolling_mean"] = g[cfg.value_col].apply(
            lambda s: s.rolling(cfg.window, min_periods=cfg.min_periods).mean()
        )
        dfx["rolling_std"] = g[cfg.value_col].apply(
            lambda s: s.rolling(cfg.window, min_periods=cfg.min_periods).std(ddof=0)
        )
    else:
        dfx["rolling_mean"] = dfx[cfg.value_col].rolling(cfg.window, min_periods=cfg.min_periods).mean()
        dfx["rolling_std"] = dfx[cfg.value_col].rolling(cfg.window, min_periods=cfg.min_periods).std(ddof=0)

    # z-score
    dfx["rolling_std"] = dfx["rolling_std"].replace(0, np.nan)
    dfx["z_score"] = (dfx[cfg.value_col] - dfx["rolling_mean"]) / dfx["rolling_std"]

    # flag anomalies
    dfx["is_anomaly"] = dfx["z_score"].abs() >= cfg.z_threshold

    # simple direction label
    dfx["anomaly_type"] = np.where(dfx["z_score"] >= cfg.z_threshold, "spike",
                          np.where(dfx["z_score"] <= -cfg.z_threshold, "drop", "normal"))

    return dfx
