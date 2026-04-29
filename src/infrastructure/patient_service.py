from __future__ import annotations
from typing import List
from ..domain.patient import Patient
from ..domain.action import Action
from ..domain.macro_state import MacroState
from .database import init_db, seed_data, get_all_patients, load_disease_model, load_actions
from ..domain.patient_record import PatientRecord


def load_patients_with_actions() -> List[PatientRecord]:
    """
    Loads all patients with their available actions as domain objects.
    Queries the database fresh each time - no caching.
    This is the only function MainWindow needs to call.
    
    Note: This function does NOT re-initialize or re-seed the database
    on every call to preserve existing data. init_db and seed_data are
    only called if the database doesn't exist or is empty.
    """
    try:
        test_patients = get_all_patients()
        if not test_patients:
            print("Database is empty. Seeding initial data...")
            init_db()
            seed_data()
    except Exception as e:
        print(f"Database not initialized or error occurred: {e}")
        print("Initializing and seeding database...")
        init_db()
        seed_data()

    patients = []
    for patient_id, full_name, current_state, disease_name in get_all_patients():
        try:
            model = load_disease_model(patient_id)
            actions = load_actions(patient_id)
            
            patient = Patient(
                patient_id=patient_id,
                name=full_name,
                disease_name=disease_name,
                macro_state=MacroState(
                    model=model,
                    current_state=current_state
                ),
            )
            patients.append(PatientRecord(patient=patient, actions=actions))
        except Exception as e:
            print(f"Error loading patient {patient_id}: {e}")
            continue

    return patients


def refresh_patients() -> List[PatientRecord]:
    """
    Force a fresh reload of all patients from the database.
    Useful after adding/updating patients.
    This is an alias for load_patients_with_actions() to make the intent clear.
    """
    return load_patients_with_actions()
