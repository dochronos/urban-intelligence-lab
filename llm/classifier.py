import json
import subprocess
from pathlib import Path
from typing import Any, Dict

from llm.insights import DEFAULT_LLM_MODEL  # reuse same default model


# Path to prompt template
PROMPT_TEMPLATE_PATH = Path(__file__).parent / "prompts" / "incident_classifier_prompt.txt"


def run_ollama(prompt: str, model: str = DEFAULT_LLM_MODEL) -> str:
    """
    Calls Ollama via CLI and returns raw text output.
    """
    result = subprocess.run(
        ["ollama", "run", model],
        input=prompt,
        text=True,
        capture_output=True,
    )
    return result.stdout.strip()


def build_prompt(incident_text: str) -> str:
    """
    Loads classifier prompt and inserts the incident text.
    """
    template = PROMPT_TEMPLATE_PATH.read_text(encoding="utf-8")
    return template.replace("{{INCIDENT_TEXT}}", incident_text.strip())


def _extract_json(raw_output: str) -> Dict[str, Any]:
    """
    Extracts a JSON object from LLM output. Handles fallbacks.
    """
    try:
        start = raw_output.find("{")
        end = raw_output.rfind("}")
        if start != -1 and end != -1 and end > start:
            json_str = raw_output[start : end + 1]
            return json.loads(json_str)
    except Exception:
        pass

    # Fallback minimal structure
    return {
        "category": "unknown",
        "severity": "unknown",
        "line": None,
        "station": None,
        "target_team": "manual_review",
        "raw_output": raw_output.strip(),
    }


def classify_incident(incident_text: str, model: str = DEFAULT_LLM_MODEL) -> Dict[str, Any]:
    """
    Main API: classify an incident text into a structured JSON-like dict.
    """
    prompt = build_prompt(incident_text)
    raw_output = run_ollama(prompt, model=model)
    parsed = _extract_json(raw_output)

    # ensure keys exist
    parsed.setdefault("category", "unknown")
    parsed.setdefault("severity", "unknown")
    parsed.setdefault("line", None)
    parsed.setdefault("station", None)
    parsed.setdefault("target_team", "manual_review")

    return parsed
