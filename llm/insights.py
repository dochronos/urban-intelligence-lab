import pandas as pd
import json
import subprocess
from pathlib import Path

DEFAULT_LLM_MODEL = "llama3.2:3b"


def run_ollama(prompt: str, model: str = DEFAULT_LLM_MODEL) -> str:
    """
    Calls Ollama using subprocess and returns raw LLM output.
    """
    result = subprocess.run(
        ["ollama", "run", model],
        input=prompt,
        text=True,
        capture_output=True
    )
    return result.stdout.strip()


def summarize_dataset(df: pd.DataFrame, n_top: int = 5) -> dict:
    """
    Extracts numeric and categorical summaries for the LLM prompt.
    Tries to be robust to column naming (station/estacion, line/linea, etc.).
    """
    summary = {}
    cols = df.columns

    # Detect station column
    station_candidates = [c for c in cols if "estacion" in c.lower() or "station" in c.lower()]
    station_col = station_candidates[0] if station_candidates else None

    # Detect line column
    line_candidates = [c for c in cols if "linea" in c.lower() or "line" in c.lower()]
    line_col = line_candidates[0] if line_candidates else None

    # Top stations
    if station_col:
        top_stations = (
            df.groupby(station_col)
            .size()
            .sort_values(ascending=False)
            .head(n_top)
            .to_dict()
        )
        summary["top_stations"] = top_stations

    # Top lines
    if line_col:
        top_lines = (
            df.groupby(line_col)
            .size()
            .sort_values(ascending=False)
            .head(n_top)
            .to_dict()
        )
        summary["top_lines"] = top_lines

    # Hour patterns
    time_candidates = [c for c in cols if "hora" in c.lower() or "time" in c.lower()]
    time_col = time_candidates[0] if time_candidates else None

    if time_col:
        tmp = df.copy()
        tmp["hour_num"] = tmp[time_col].astype(str).str.split(":").str[0].astype(int)
        hour_profile = (
            tmp.groupby("hour_num")
            .size()
            .sort_values(ascending=False)
            .head(10)
            .to_dict()
        )
        summary["hour_peaks"] = hour_profile

    return summary


def generate_insights(df: pd.DataFrame, model: str = DEFAULT_LLM_MODEL) -> str:
    """
    Generates narrative insights via Ollama given the dataset summary.
    """
    summary_dict = summarize_dataset(df)
    summary_json = json.dumps(summary_dict, indent=2, ensure_ascii=False)

    prompt_template_path = Path(__file__).parent / "prompts" / "insights_prompt.txt"
    template = prompt_template_path.read_text(encoding="utf-8")

    final_prompt = template.replace("{{DATA_SUMMARY}}", summary_json)

    llm_output = run_ollama(final_prompt, model=model)
    return llm_output
