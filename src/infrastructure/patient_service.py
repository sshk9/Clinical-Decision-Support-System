from __future__ import annotations
from typing import List, Tuple
from ..domain.patient import Patient
from ..domain.action import Action
from ..domain.macro_state import MacroState
from .database import init_db, seed_data, get_all_patients, load_disease_model, load_actions


def load_patients_with_actions() -> List[Tuple[Patient, List[Action]]]:
    """
    Initialises the database, seeds demo data, and returns all patients
    with their available actions as domain objects.
    This is the only function MainWindow needs to call.
    """
    init_db()
    seed_data()

    patients = []
    for patient_id, full_name, current_state in get_all_patients():
        model = load_disease_model(patient_id)
        actions = load_actions(patient_id)
        patient = Patient(
            patient_id=patient_id,
            name=full_name,
            macro_state=MacroState(model=model, current_state=current_state),
        )
        patients.append((patient, actions))

    return patients