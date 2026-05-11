from __future__ import annotations

from ..infrastructure.database import (
    get_all_patients_detailed,
    get_patient_summary_export,
)
from ..infrastructure.patient_service import load_patients_with_actions


def get_detailed_patients():
    return get_all_patients_detailed()


def get_patient_export_rows():
    return get_patient_summary_export()


def reload_patients_with_actions():
    return load_patients_with_actions()