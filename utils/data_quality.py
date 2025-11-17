from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import logging
import numpy as np
import pandas as pd


# Try to reuse project logger if available, otherwise fall back to std logging
try:
    from .logger import get_logger  # type: ignore

    logger = get_logger(__name__)
except Exception:  # pragma: no cover - safe fallback
    logger = logging.getLogger(__name__)
    if not logger.handlers:
        logging.basicConfig(level=logging.INFO)


@dataclass
class DataQualityConfig:
    """
    Configuration object to describe the expected shape and rules
    for a given dataset.
    """

    name: str
    expected_columns: List[str]
    non_null_columns: List[str] = field(default_factory=list)
    date_columns: List[str] = field(default_factory=list)
    numeric_columns: List[str] = field(default_factory=list)
    allowed_values: Dict[str, List[Any]] = field(default_factory=dict)
    value_ranges: Dict[str, Tuple[Optional[float], Optional[float]]] = field(
        default_factory=dict
    )
    unique_keys: List[List[str]] = field(default_factory=list)
    min_rows: int = 1


@dataclass
class DataQualityResult:
    """
    Summary of data quality checks.
    """

    dataset_name: str
    n_rows_before: int
    n_rows_after: int
    n_columns: int
    issues: List[str] = field(default_factory=list)
    anomaly_columns: List[str] = field(default_factory=list)

    def is_acceptable(self) -> bool:
        return len(self.issues) == 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "dataset_name": self.dataset_name,
            "n_rows_before": self.n_rows_before,
            "n_rows_after": self.n_rows_after,
            "n_columns": self.n_columns,
            "issues": self.issues,
            "anomaly_columns": self.anomaly_columns,
            "is_acceptable": self.is_acceptable(),
        }


def load_csv(path: Path) -> pd.DataFrame:
    """
    Load a CSV file into a pandas DataFrame with basic logging.

    Tries UTF-8 first, then falls back to latin1 if needed.
    """
    path = Path(path)
    logger.info("Loading CSV file: %s", path)
    if not path.exists():
        raise FileNotFoundError(f"File does not exist: {path}")

    try:
        df = pd.read_csv(path)
        logger.info("Loaded %d rows and %d columns with utf-8", df.shape[0], df.shape[1])
        return df
    except UnicodeDecodeError:
        logger.warning("utf-8 decoding failed for %s, falling back to latin1", path)
        df = pd.read_csv(path, encoding="latin1")
        logger.info("Loaded %d rows and %d columns with latin1", df.shape[0], df.shape[1])
        return df


def standardize_column_names(df: pd.DataFrame) -> pd.DataFrame:
    """
    Standardize column names to snake_case and strip whitespace.
    """
    original_cols = list(df.columns)
    df = df.copy()
    df.columns = (
        df.columns.str.strip()
        .str.lower()
        .str.replace(" ", "_")
        .str.replace("-", "_")
    )
    logger.info("Standardized column names: %s -> %s", original_cols, list(df.columns))
    return df


def basic_cleaning(df: pd.DataFrame, config: DataQualityConfig) -> pd.DataFrame:
    """
    Apply basic cleaning steps:
    - standardize column names
    - drop fully duplicated rows
    - trim string columns
    """
    logger.info("Running basic cleaning for dataset '%s'", config.name)
    df = standardize_column_names(df)

    # Drop duplicate rows
    before = df.shape[0]
    df = df.drop_duplicates()
    after = df.shape[0]
    if after < before:
        logger.info("Dropped %d duplicate rows", before - after)

    # Trim strings
    for col in df.select_dtypes(include=["object", "string"]).columns:
        df[col] = df[col].astype("string").str.strip()

    return df


def validate_schema(df: pd.DataFrame, config: DataQualityConfig) -> List[str]:
    """
    Validate schema: columns, non-null constraints, row count, allowed values, ranges.
    Returns a list of human-readable issues.
    """
    issues: List[str] = []

    # Columns presence
    missing = set(config.expected_columns) - set(df.columns)
    extra = set(df.columns) - set(config.expected_columns)
    if missing:
        issues.append(f"Missing columns: {sorted(missing)}")
    if extra:
        issues.append(f"Unexpected columns: {sorted(extra)}")

    # Non-null constraints
    for col in config.non_null_columns:
        if col in df.columns:
            null_count = df[col].isna().sum()
            if null_count > 0:
                issues.append(f"Column '{col}' has {null_count} null values")
        else:
            issues.append(f"Non-null column '{col}' is missing from dataframe")

    # Row count
    if df.shape[0] < config.min_rows:
        issues.append(
            f"Dataset has {df.shape[0]} rows, less than required minimum {config.min_rows}"
        )

    # Allowed values
    for col, allowed in config.allowed_values.items():
        if col in df.columns:
            invalid = df[~df[col].isin(allowed)][col].unique()
            if len(invalid) > 0:
                issues.append(
                    f"Column '{col}' contains values outside allowed set: {invalid}"
                )

    # Value ranges for numeric columns
    for col, (min_val, max_val) in config.value_ranges.items():
        if col in df.columns:
            if min_val is not None and (df[col] < min_val).any():
                issues.append(
                    f"Column '{col}' has values below minimum {min_val}"
                )
            if max_val is not None and (df[col] > max_val).any():
                issues.append(
                    f"Column '{col}' has values above maximum {max_val}"
                )

    # Uniqueness constraints
    for key in config.unique_keys:
        if all(k in df.columns for k in key):
            duplicated = df.duplicated(subset=key).sum()
            if duplicated > 0:
                issues.append(
                    f"Composite key {key} has {duplicated} duplicated rows"
                )

    return issues


def detect_numeric_anomalies(
    df: pd.DataFrame, numeric_columns: Optional[List[str]] = None, z_threshold: float = 4.0
) -> Dict[str, pd.DataFrame]:
    """
    Detect numeric anomalies using a simple z-score threshold.

    Returns a dict mapping column -> rows flagged as anomalous.
    """
    if numeric_columns is None:
        numeric_columns = df.select_dtypes(include=[np.number]).columns.tolist()

    anomalies: Dict[str, pd.DataFrame] = {}

    for col in numeric_columns:
        if col not in df.columns:
            continue
        series = df[col].astype(float)
        mean = series.mean()
        std = series.std()

        if std == 0 or np.isnan(std):
            continue

        z_scores = (series - mean) / std
        mask = z_scores.abs() >= z_threshold
        if mask.any():
            anomalies[col] = df.loc[mask].copy()

    return anomalies


def save_dataset(df: pd.DataFrame, base_path: Path, dataset_name: str) -> None:
    """
    Save cleaned dataset to CSV and Parquet under data/processed.
    """
    base_path = Path(base_path)
    base_path.mkdir(parents=True, exist_ok=True)

    csv_path = base_path / f"{dataset_name}_clean.csv"
    parquet_path = base_path / f"{dataset_name}_clean.parquet"

    logger.info("Saving cleaned dataset to %s and %s", csv_path, parquet_path)
    df.to_csv(csv_path, index=False)
    try:
        df.to_parquet(parquet_path, index=False)
    except Exception as exc:  # pragma: no cover - optional dependency
        logger.warning("Could not save Parquet file: %s", exc)


def run_data_quality_pipeline(
    raw_path: Path,
    processed_dir: Path,
    config: DataQualityConfig,
) -> DataQualityResult:
    """
    High-level pipeline:

    1. Load raw CSV
    2. Basic cleaning
    3. Validate schema
    4. Detect anomalies
    5. Save cleaned dataset
    6. Return summary object
    """
    df_raw = load_csv(raw_path)
    n_rows_before = df_raw.shape[0]

    df_clean = basic_cleaning(df_raw, config)
    issues = validate_schema(df_clean, config)

    anomalies = detect_numeric_anomalies(df_clean, config.numeric_columns)
    anomaly_cols = list(anomalies.keys())

    # For now we do NOT automatically drop anomalies, just log them.
    if anomaly_cols:
        logger.info(
            "Detected anomalies in numeric columns: %s",
            anomaly_cols,
        )

    save_dataset(df_clean, processed_dir, config.name)

    result = DataQualityResult(
        dataset_name=config.name,
        n_rows_before=n_rows_before,
        n_rows_after=df_clean.shape[0],
        n_columns=df_clean.shape[1],
        issues=issues,
        anomaly_columns=anomaly_cols,
    )

    if result.is_acceptable():
        logger.info("Data quality checks passed for dataset '%s'", config.name)
    else:
        logger.warning(
            "Data quality checks found issues for dataset '%s': %s",
            config.name,
            issues,
        )

    return result