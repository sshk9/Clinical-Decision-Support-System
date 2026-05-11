from __future__ import annotations

from ..infrastructure.database import (
    get_state_distribution,
    get_action_utility_comparison,
    get_connection,
)
from ..analytics.analytics import compare_actions


def get_available_diseases() -> list[str]:
    """Return disease names for the trend filter."""
    with get_connection() as conn:
        cursor = conn.execute("SELECT DISTINCT name FROM disease ORDER BY name")
        return [row[0] for row in cursor.fetchall()]


def get_population_distribution() -> list[dict]:
    """Return current state distribution for all diseases."""
    return get_state_distribution()


def get_action_effectiveness_for_disease(disease_name: str):
    """Return action comparison results for one disease."""
    with get_connection() as conn:
        cursor = conn.execute("SELECT id FROM disease WHERE name = ?", (disease_name,))
        result = cursor.fetchone()

    if not result:
        return []

    disease_id = result[0]
    actions_data = get_action_utility_comparison(disease_id)
    return compare_actions(actions_data)