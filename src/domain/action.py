from __future__ import annotations
from dataclasses import dataclass
from typing import List, Optional
import numpy as np
from .disease_model import DiseaseModel


@dataclass(frozen=True)
class Action:
    """
    A treatment action that transforms a disease model P -> P'.

    name:              identifier shown in the UI.
    immediate_utility: short-term benefit score (encodes benefit, side-effect cost, etc.).
    description:       optional human-readable explanation shown in the rationale panel.
    improve_state:     state column to shift probability mass toward.
    worsen_state:      state column to shift probability mass away from.
    delta:             how much probability mass to move (must be in (0, 1]).
    """

    name: str
    immediate_utility: float
    description: str = ""
    improve_state: Optional[str] = None
    worsen_state: Optional[str] = None
    delta: float = 0.0

    def __post_init__(self) -> None:
        if self.delta < 0.0 or self.delta > 1.0:
            raise ValueError(f"delta must be in [0, 1]. Got {self.delta}.")
        if self.improve_state is not None and self.improve_state == self.worsen_state:
            raise ValueError("improve_state and worsen_state must be different states.")

    def apply(self, model: DiseaseModel) -> DiseaseModel:
        """
        Apply this action to a disease model and return the modified model.
        If no shift is defined, returns the original model unchanged.
        """
        if not self.improve_state or not self.worsen_state or self.delta == 0.0:
            return model

        improve_idx = model.index_of(self.improve_state)
        worsen_idx = model.index_of(self.worsen_state)

        P_new = model.P.copy()

        for i in range(P_new.shape[0]):
            move = min(self.delta, P_new[i, worsen_idx])
            P_new[i, worsen_idx] -= move
            P_new[i, improve_idx] += move

            row_sum = P_new[i, :].sum()
            if row_sum <= 0:
                raise ValueError(f"Row {i} sum became non-positive after applying action '{self.name}'.")
            P_new[i, :] /= row_sum

        return DiseaseModel(states=model.states, P=P_new)



# Default actions, used for development and demo purposes


def make_default_actions() -> List[Action]:
    """Basic set of actions for use with the simple three-state progression model."""
    return [
        Action(
            name="Watch and Wait",
            immediate_utility=0.2,
            description="No intervention. Monitor patient and reassess at next visit.",
        ),
        Action(
            name="Prescribe Medication",
            immediate_utility=0.6,
            description="Standard pharmacological treatment to slow disease progression.",
            improve_state="Healthy",
            worsen_state="Severe",
            delta=0.1,
        ),
        Action(
            name="Lifestyle Intervention",
            immediate_utility=0.4,
            description="Diet, exercise, and behavioural changes to support recovery.",
            improve_state="Mild",
            worsen_state="Severe",
            delta=0.05,
        ),
        Action(
            name="Refer to Specialist",
            immediate_utility=0.5,
            description="Escalate care to a specialist for advanced treatment options.",
            improve_state="Healthy",
            worsen_state="Severe",
            delta=0.15,
        ),
    ]