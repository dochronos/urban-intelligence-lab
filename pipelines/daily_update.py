from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import json

import duckdb
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CLEAN_DATA_PATH = PROJECT_ROOT / "data" / "processed" / "subte_molinetes_ridership_clean.csv"
LOGS_DIR = PROJECT_ROOT / "data" / "logs"
DUCKDB_PATH = LOGS_DIR / "urban_intel_logs.duckdb"


@dataclass
class PipelineConfig:
    run_date: str  # YYYY-MM-DD
    limit_rows: int | None = 200_000  # keep it light by default
    model_tag: str = "phase3-week9"


def ensure_dirs() -> None:
    LOGS_DIR.mkdir(parents=True, exist_ok=True)


def connect_db() -> duckdb.DuckDBPyConnection:
    return duckdb.connect(str(DUCKDB_PATH))


def init_schema(con: duckdb.DuckDBPyConnection) -> None:
    con.execute("""
        CREATE TABLE IF NOT EXISTS ingestion_runs (
            run_id VARCHAR,
            run_date DATE,
            source_file VARCHAR,
            rows_loaded BIGINT,
            created_at TIMESTAMP,
            model_tag VARCHAR
        );
    """)

    con.execute("""
        CREATE TABLE IF NOT EXISTS incidents (
            incident_id VARCHAR,
            reported_at TIMESTAMP,
            source VARCHAR,
            description VARCHAR,
            category VARCHAR,
            severity VARCHAR,
            line VARCHAR,
            station VARCHAR,
            target_team VARCHAR,
            raw_llm_output VARCHAR
        );
    """)


def load_clean_data(limit_rows: int | None) -> pd.DataFrame:
    if not CLEAN_DATA_PATH.exists():
        raise FileNotFoundError(f"Clean dataset not found: {CLEAN_DATA_PATH}")

    # Keep memory safe: load only a slice for the demo pipeline
    df = pd.read_csv(CLEAN_DATA_PATH, low_memory=False)
    df.columns = df.columns.str.strip().str.lower()

    if limit_rows and len(df) > limit_rows:
        df = df.sample(n=limit_rows, random_state=42).reset_index(drop=True)

    return df


def register_ingestion_run(
    con: duckdb.DuckDBPyConnection,
    run_date: str,
    source_file: str,
    rows_loaded: int,
    model_tag: str
) -> None:
    run_id = f"run_{run_date}_{datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')}"
    con.execute(
        """
        INSERT INTO ingestion_runs
        VALUES (?, CAST(? AS DATE), ?, ?, ?, ?)
        """,
        [run_id, run_date, source_file, rows_loaded, datetime.utcnow(), model_tag],
    )


def ingest_daily_batch(config: PipelineConfig) -> None:
    ensure_dirs()

    df = load_clean_data(config.limit_rows)

    con = connect_db()
    try:
        init_schema(con)
        register_ingestion_run(
            con,
            run_date=config.run_date,
            source_file=str(CLEAN_DATA_PATH),
            rows_loaded=len(df),
            model_tag=config.model_tag,
        )
    finally:
        con.close()

    print("✅ Daily ingestion completed")
    print(f" - run_date: {config.run_date}")
    print(f" - rows_loaded: {len(df)}")
    print(f" - duckdb: {DUCKDB_PATH}")


def ingest_incident_example(config: PipelineConfig) -> None:
    """
    Inserts 1-2 demo incidents (placeholder) to validate the logging layer.
    Week 11 will enhance this by routing logic and real n8n outputs.
    """
    ensure_dirs()

    demo_incidents = [
        {
            "incident_id": f"INC-{config.run_date}-0001",
            "reported_at": datetime.utcnow().isoformat(),
            "source": "n8n_demo",
            "description": "15-minute delay on Line B at Carlos Pellegrini due to a mechanical issue.",
            "category": "infrastructure",
            "severity": "medium",
            "line": "B",
            "station": "Carlos Pellegrini",
            "target_team": "infrastructure_maintenance",
            "raw_llm_output": None,
        },
        {
            "incident_id": f"INC-{config.run_date}-0002",
            "reported_at": datetime.utcnow().isoformat(),
            "source": "n8n_demo",
            "description": "Overcrowding reported on Line D at 9 de Julio during peak hour.",
            "category": "overcrowding",
            "severity": "medium",
            "line": "D",
            "station": "9 de Julio",
            "target_team": "operations_control",
            "raw_llm_output": None,
        },
    ]

    con = connect_db()
    try:
        init_schema(con)
        for inc in demo_incidents:
            con.execute(
                """
                INSERT INTO incidents
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    inc["incident_id"],
                    inc["reported_at"],
                    inc["source"],
                    inc["description"],
                    inc["category"],
                    inc["severity"],
                    inc["line"],
                    inc["station"],
                    inc["target_team"],
                    inc["raw_llm_output"],
                ],
            )
    finally:
        con.close()

    print("✅ Inserted demo incidents into DuckDB")
    print(f" - count: {len(demo_incidents)}")
    print(f" - duckdb: {DUCKDB_PATH}")


def parse_args() -> PipelineConfig:
    parser = argparse.ArgumentParser(description="Week 9 - Daily pipeline & incident logging (Urban Intelligence Lab)")
    parser.add_argument("--run-date", required=True, help="Run date in YYYY-MM-DD format")
    parser.add_argument("--limit-rows", type=int, default=200000, help="Limit rows loaded from clean dataset")
    parser.add_argument("--model-tag", default="phase3-week9", help="Tag for the ingestion run metadata")
    parser.add_argument("--insert-demo-incidents", action="store_true", help="Insert demo incidents into DuckDB")

    args = parser.parse_args()
    cfg = PipelineConfig(run_date=args.run_date, limit_rows=args.limit_rows, model_tag=args.model_tag)

    # store a flag on the object (simple)
    cfg.insert_demo_incidents = args.insert_demo_incidents  # type: ignore[attr-defined]
    return cfg


if __name__ == "__main__":
    config = parse_args()
    ingest_daily_batch(config)
    if getattr(config, "insert_demo_incidents", False):
        ingest_incident_example(config)