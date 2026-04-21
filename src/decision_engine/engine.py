from __future__ import annotations
from dataclasses import dataclass
from typing import List, Dict
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
    """

    action: Action
    immediate_utility: float
    long_term_value: float
    total_score: float
    risk_score: float
    risk_level: str
    explanation: str


class DecisionEngine:
    """
    Computes and ranks actions for a given macro-state using value iteration.

    For each action α, a separate value table V(P_α, s) is computed under
    the modified model P_α. At each future state, the best available action
    is chosen, consistent with the BRD formula:

        V(P, s) = max_α [ r(P, s, α) + γ * Σ_s' P_α(s'|s) * V(P_α, s') ]

    gamma:          discount factor in [0, 1). Lower values favour short-term gains.
    theta:          convergence threshold for value iteration.
    max_iterations: safety cap on value iteration loop.
    """

    def __init__(
        self,
        gamma: float = 0.9,
        theta: float = 1e-6,
        max_iterations: int = 1000,
    ) -> None:
        if not 0.0 <= gamma < 1.0:
            raise ValueError(f"gamma must be in [0, 1). Got {gamma}.")
        if theta <= 0.0:
            raise ValueError(f"theta must be positive. Got {theta}.")

        self.gamma = gamma
        self.theta = theta
        self.max_iterations = max_iterations

    def rank_actions(self, macro_state: MacroState, actions: List[Action]) -> List[ActionScore]:
        """
        Rank all available actions for the given macro-state.
        Returns a list of ActionScore sorted best-first.
        """
        if not actions:
            return []

        scores = [self._score_action(macro_state, action, actions) for action in actions]
        return sorted(scores, key=lambda s: s.total_score, reverse=True)



    # Private methods

    def _immediate_utility(self, macro_state: MacroState, action: Action) -> float:
        """
        r(P, s, α) — immediate utility of applying action in the current state.
        Currently uses action.immediate_utility directly as a placeholder.
        This method is the single place to extend reward computation later.
        """
        return action.immediate_utility
    
    def _severity_weights(self, states: list[str]) -> dict[str, float]:
        """
        Assign increasing severity weights to states based on their order.
        First state = least severe, last state = most severe.
        Returns values scaled to 0-100.
        """
        if len(states) == 1:
            return {states[0]: 100.0}

        weights = {}
        for i, state in enumerate(states):
            weights[state] = (i / (len(states) - 1)) * 100.0
        return weights

    def _calculate_risk_score(self, current_state: str, model: DiseaseModel) -> float:
        """
        Risk score based on expected severity of next-state probabilities.
        """
        row = model.row(current_state)
        weights = self._severity_weights(list(model.states))

        score = 0.0
        for i, state in enumerate(model.states):
            score += row[i] * weights[state]

        return round(score, 1)

    def _risk_level(self, risk_score: float) -> str:
        if risk_score < 33:
            return "Low"
        elif risk_score < 66:
            return "Medium"
        return "High"

    def _build_explanation(
        self,
        macro_state: MacroState,
        action: Action,
        modified_model: DiseaseModel,
        risk_score: float,
        risk_level: str,
    ) -> str:
        """
        Build a human-readable explanation for the recommendation.
        """
        current = macro_state.current_state
        row = modified_model.row(current)

        most_likely_index = max(range(len(row)), key=lambda i: row[i])
        most_likely_state = modified_model.states[most_likely_index]
        most_likely_prob = row[most_likely_index]

        history_count = len(macro_state.history)

        lines = [
            f"Current state: {current}.",
            f"Estimated risk score: {risk_score:.1f}/100 ({risk_level}).",
            f"Most likely next state after '{action.name}': {most_likely_state} ({most_likely_prob:.2f}).",
            f"Immediate utility of this action: {action.immediate_utility:.2f}.",
        ]

        if action.description:
            lines.append(f"Clinical rationale: {action.description}")

        if history_count > 0:
            lines.append(f"Previous interventions recorded: {history_count}.")

        return "\n".join(lines)

    def _value_iteration(self, model: DiseaseModel, actions: List[Action]) -> Dict[str, float]:
        """
        Compute V(P_α, s) for all states under the modified model P_α.

        At each future state the best available action is selected (max_α),
        consistent with the BRD formula:

            V(P_α, s) = max_α [ r(α) + γ * Σ_s' P_α(s'|s) * V(P_α, s') ]
        """
        states = model.states
        V: Dict[str, float] = {s: 0.0 for s in states}

        for _ in range(self.max_iterations):
            delta = 0.0 # Reset delta to track change in each iteration

            for state in states:
                # Find the best action value for this state (max_α)
                best = max(
                    self._action_value(state, action, model, V)
                    for action in actions
                )
                delta = max(delta, abs(best - V[state]))
                V[state] = best

            if delta < self.theta:
                break

        return V

    def _action_value(
        self,
        state: str,
        action: Action,
        model: DiseaseModel,
        V: Dict[str, float],
    ) -> float:
        """
        Compute the value of taking action α in state s under model P_α:

            r(α) + γ * Σ_s' P_α(s'|s) * V(s')
        """
        modified_model = action.apply(model)
        row = modified_model.row(state)
        future = sum(row[i] * V[s] for i, s in enumerate(modified_model.states))
        return action.immediate_utility + self.gamma * future

    def _score_action(
        self,
        macro_state: MacroState,
        action: Action,
        actions: List[Action],
    ) -> ActionScore:
        """
        Score a single action from the current macro-state.

        1. Apply α to get the modified model P_α.
        2. Run value iteration under P_α with all actions to get V(P_α, s).
        3. Compute the full score from the current state s:
               score = r(P, s, α) + γ * Σ_s' P_α(s'|s) * V(P_α, s')
        """
        modified_model = action.apply(macro_state.model)
        value_table = self._value_iteration(modified_model, actions)

        current = macro_state.current_state
        row = modified_model.row(current)

        immediate = self._immediate_utility(macro_state, action)
        future = self.gamma * sum(
            row[i] * value_table[s] for i, s in enumerate(modified_model.states)
        )

        risk_score = self._calculate_risk_score(current, modified_model)
        risk_level = self._risk_level(risk_score)
        explanation = self._build_explanation(
        macro_state=macro_state,
        action=action,
        modified_model=modified_model,
        risk_score=risk_score,
        risk_level=risk_level,
        )
    
        return ActionScore(
            action=action,
            immediate_utility=immediate,
            long_term_value=future,
            total_score=immediate + future,
            risk_score=risk_score,
            risk_level=risk_level,
            explanation=explanation,
        )
    