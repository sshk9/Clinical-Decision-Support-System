from __future__ import annotations

from ..infrastructure.database import get_audit_log, get_all_patients


def get_audit_patients():
    """Return patients used by the audit patient filter."""
    return get_all_patients()


def get_audit_records(patient_id=None):
    """Return audit log records, optionally filtered by patient."""
    return get_audit_log(patient_id)