from __future__ import annotations
from dataclasses import dataclass
from .macro_state import MacroState
from .action import Action


@dataclass(frozen=True)
class Patient:
    """
    Represents a patient in the system.

    patient_id:  unique identifier for the patient.
    name:        optional display name shown in the UI.
    macro_state: the patient's current clinical state (P, s) including full history.
    """

    patient_id: str
    macro_state: MacroState
    name: str = ""

    def __post_init__(self) -> None:
        if not self.patient_id.strip():
            raise ValueError("patient_id must not be empty.")

    def apply_action(self, action: Action) -> Patient:
        """Apply an action and return a new Patient with the updated macro-state."""
        return Patient(
            patient_id=self.patient_id,
            name=self.name,
            macro_state=self.macro_state.apply_action(action),
        )

    def current_state_label(self) -> str:
        """Returns display string for current state and model size."""
        return self.current_state

    def model_size_label(self) -> str:
        """Returns human readable model size for display."""
        return f"{len(self.macro_state.model.states)} states"

    @property
    def current_state(self) -> str:
        """Easy access for the current state s."""
        return self.macro_state.current_state