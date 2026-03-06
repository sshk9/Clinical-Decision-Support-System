from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Tuple
from .disease_model import DiseaseModel
from .action import Action


@dataclass(frozen=True)
class HistoryStep:
    """
    Records a single action applied to a macro-state.

    action:       the action that was applied.
    model_before: the disease model before the action.
    model_after:  the disease model after the action.
    state:        the patient's micro-state at the time the action was applied.
    """

    action: Action
    model_before: DiseaseModel
    model_after: DiseaseModel
    state: str


@dataclass(frozen=True)
class MacroState:
    """
    Full patient state as defined in the BRD: (P, s).

    model:         current disease model P.
    current_state: current micro-state s.
    history:       ordered record of all actions applied so far.
    """

    model: DiseaseModel
    current_state: str
    history: Tuple[HistoryStep, ...] = field(default_factory=tuple, compare=False)

    def __post_init__(self) -> None:
        # Validate that current_state is actually in the model.
        self.model.index_of(self.current_state)

    def apply_action(self, action: Action) -> MacroState:
        """
        Apply an action and return a new MacroState with the updated model and history.
        The current micro-state s is unchanged — actions modify P, not s.
        """
        model_after = action.apply(self.model)

        step = HistoryStep(
            action=action,
            model_before=self.model,
            model_after=model_after,
            state=self.current_state,
        )

        return MacroState(
            model=model_after,
            current_state=self.current_state,
            history=self.history + (step,),
        )

    def summary(self) -> List[str]:
        """
        Human-readable action history — used by the rationale panel.
        Returns one line per step.
        """
        if not self.history:
            return ["No actions applied yet."]
        return [
            f"Step {i + 1}: '{step.action.name}' applied in state '{step.state}'"
            for i, step in enumerate(self.history)
        ]