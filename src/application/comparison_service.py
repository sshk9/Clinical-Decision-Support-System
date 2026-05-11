from __future__ import annotations

from ..infrastructure.database import (
    get_all_patients,
    get_actions_for_patient,
    get_action_utility_comparison,
    get_state_distribution,
    get_connection,
)
from ..analytics.analytics import compare_actions, state_success_rate


def get_comparison_patients():
    return get_all_patients()


def get_patient_actions(patient_id: str):
    return get_actions_for_patient(patient_id)


def get_disease_id_by_name(disease_name: str) -> int | None:
    with get_connection() as conn:
        cursor = conn.execute("SELECT id FROM disease WHERE name = ?", (disease_name,))
        result = cursor.fetchone()
        if result:
            return result[0]
    return None


def get_action_effectiveness_for_disease(disease_name: str):
    disease_id = get_disease_id_by_name(disease_name)

    if not disease_id:
        return []

    actions_data = get_action_utility_comparison(disease_id)
    return compare_actions(actions_data)


def get_population_success_rates():
    distribution = get_state_distribution()
    return state_success_rate(distribution)