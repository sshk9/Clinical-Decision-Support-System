from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Dict, Tuple
from ..domain.disease_model import DiseaseModel
from ..domain.macro_state import MacroState
from ..domain.action import Action


@dataclass(frozen=True)
class ActionScore:
    """
    Result of evaluating a single action from the current macro-state.

    action:            the action that was evaluated.
    immediate_utility: r(P, s, α) — short-term benefit of this action.
    long_term_value:   γ * Σ_s' P_α(s'|s) * V(P_α, s') — expected future value.
    total_score:       immediate_utility + long_term_value — used for ranking.
    future_outcomes:   list of (next_state, probability, state_value) for the current state.
    gamma:             discount factor used in calculation.
    """
    action: Action
    immediate_utility: float
    long_term_value: float
    total_score: float
    future_outcomes: List[Tuple[str, float, float]] = field(default_factory=list)
    gamma: float = 0.9


class DecisionEngine:
    """
    Computes and ranks actions for a given macro‑state using value iteration.
    """
    def __init__(self, gamma: float = 0.9, theta: float = 1e-6, max_iterations: int = 1000):
        if not 0.0 <= gamma < 1.0:
            raise ValueError(f"gamma must be in [0, 1). Got {gamma}.")
        if theta <= 0.0:
            raise ValueError(f"theta must be positive. Got {theta}.")
        self.gamma = gamma
        self.theta = theta
        self.max_iterations = max_iterations

    def rank_actions(self, macro_state: MacroState, actions: List[Action]) -> List[ActionScore]:
        if not actions:
            return []
        scores = [self._score_action(macro_state, action, actions) for action in actions]
        return sorted(scores, key=lambda s: s.total_score, reverse=True)

    def _immediate_utility(self, macro_state: MacroState, action: Action) -> float:
        return action.immediate_utility

    def _value_iteration(self, model: DiseaseModel, actions: List[Action]) -> Dict[str, float]:
        states = model.states
        V = {s: 0.0 for s in states}
        for _ in range(self.max_iterations):
            delta = 0.0
            for state in states:
                best = max(self._action_value(state, action, model, V) for action in actions)
                delta = max(delta, abs(best - V[state]))
                V[state] = best
            if delta < self.theta:
                break
        return V

    def _action_value(self, state: str, action: Action, model: DiseaseModel, V: Dict[str, float]) -> float:
        modified_model = action.apply(model)
        row = modified_model.row(state)
        future = sum(row[i] * V[s] for i, s in enumerate(modified_model.states))
        return action.immediate_utility + self.gamma * future

    def _score_action(self, macro_state: MacroState, action: Action, actions: List[Action]) -> ActionScore:
        modified_model = action.apply(macro_state.model)
        value_table = self._value_iteration(modified_model, actions)

        current = macro_state.current_state
        row = modified_model.row(current)
        states = modified_model.states

        immediate = self._immediate_utility(macro_state, action)

        # Build future outcomes list for trace panel
        future_outcomes = []
        future_sum = 0.0
        for i, state in enumerate(states):
            prob = row[i]
            state_value = value_table[state]
            future_outcomes.append((state, prob, state_value))
            future_sum += prob * state_value

        future = self.gamma * future_sum

        return ActionScore(
            action=action,
            immediate_utility=immediate,
            long_term_value=future,
            total_score=immediate + future,
            future_outcomes=future_outcomes,
            gamma=self.gamma,
        )
