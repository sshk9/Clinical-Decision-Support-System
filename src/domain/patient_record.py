from __future__ import annotations
from dataclasses import dataclass
from typing import List
from .patient import Patient
from .action import Action


@dataclass(frozen=True)
class PatientRecord:
    """
    Packages a Patient with their available actions for display in the UI.
    Replaces the raw tuple (Patient, list[Action]) used previously.
    """
    patient: Patient
    actions: List[Action]