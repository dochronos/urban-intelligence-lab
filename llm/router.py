from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Any
from datetime import datetime


@dataclass
class RoutingConfig:
    high_severity_threshold: str = "high"
    default_team: str = "manual_review"


def rule_based_overrides(llm_result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Apply lightweight domain rules to improve routing consistency.
    """
    category = (llm_result.get("category") or "").lower()
    severity = (llm_result.get("severity") or "").lower()

    # Default
    target_team = llm_result.get("target_team") or "manual_review"

    # Rule examples
    if category in {"infrastructure", "mechanical"}:
        target_team = "infrastructure_maintenance"

    if category in {"overcrowding", "capacity"}:
        target_team = "operations_control"

    if severity == "high":
        target_team = "operations_control"

    llm_result["target_team"] = target_team
    return llm_result


def build_ticket(
    description: str,
    llm_result: Dict[str, Any],
    source: str = "llm_router",
) -> Dict[str, Any]:
    """
    Build a standardized ticket object for downstream systems.
    """
    llm_result = rule_based_overrides(llm_result)

    ticket = {
        "ticket_id": f"TCK-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}",
        "created_at": datetime.utcnow().isoformat(),
        "source": source,
        "description": description,
        "category": llm_result.get("category"),
        "severity": llm_result.get("severity"),
        "line": llm_result.get("line"),
        "station": llm_result.get("station"),
        "target_team": llm_result.get("target_team"),
        "confidence": llm_result.get("confidence", None),
        "raw_llm_output": llm_result,
    }

    return ticket