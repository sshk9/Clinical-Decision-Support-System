from __future__ import annotations

from ..infrastructure.database import get_connection, get_state_distribution
from ..analytics.analytics import state_success_rate


def get_dashboard_stats() -> dict:
    """Return dashboard summary statistics."""

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM patient")
    active = cursor.fetchone()[0] or 0

    cursor.execute("""
        SELECT COUNT(*)
        FROM patient_status ps
        JOIN disease_state ds ON ps.current_state_id = ds.id
        WHERE ds.severity_level >= 4
    """)
    high_risk = cursor.fetchone()[0] or 0

    cursor.execute("""
        SELECT COUNT(*)
        FROM patient_status ps
        JOIN disease_state ds ON ps.current_state_id = ds.id
        WHERE ds.severity_level = 5
    """)
    critical = cursor.fetchone()[0] or 0

    cursor.execute("""
        SELECT d.name, COUNT(ps.patient_id)
        FROM patient_status ps
        JOIN disease d ON ps.disease_id = d.id
        GROUP BY d.id, d.name
    """)

    diabetes_count = 0
    kidney_count = 0

    for disease_name, count in cursor.fetchall():
        if "Diabetes" in disease_name:
            diabetes_count = count
        elif "Kidney" in disease_name:
            kidney_count = count

    conn.close()

    distribution = get_state_distribution()
    stats_data = state_success_rate(distribution)

    overall = stats_data.get(
        "overall",
        {"success_rate": 0, "total_patients": 0, "success_count": 0},
    )

    return {
        "active": active,
        "high_risk": high_risk,
        "critical": critical,
        "diabetes_count": diabetes_count,
        "kidney_count": kidney_count,
        "success_rate": overall.get("success_rate", 0),
        "success_count": overall.get("success_count", 0),
        "total_patients": overall.get("total_patients", 0),
    }