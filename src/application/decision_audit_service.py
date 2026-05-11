from __future__ import annotations

from ..infrastructure.database import log_recommendation


def record_clinician_decision(
    patient_id: str,
    recommended_action: str,
    recommended_score: float,
    clinician_decision: str,
    override_action: str | None = None,
) -> None:
    log_recommendation(
        patient_id=patient_id,
        recommended_action=recommended_action,
        recommended_score=recommended_score,
        clinician_decision=clinician_decision,
        override_action=override_action,
    )