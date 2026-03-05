#DISEASTE STATE
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, Tuple
import numpy as np


@dataclass(frozen=True)
class DiseaseModel:
    """
    Markov-chain disease model.

    states: ordered tuple of unique state names.
    P:      row-stochastic transition matrix where P[i, j] = P(state_i -> state_j).
    """

    states: Tuple[str, ...]
    P: np.ndarray
    _index: Dict[str, int] = field(default_factory=dict, init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        P = np.array(self.P, dtype=float)

        if not np.isfinite(P).all():
            raise ValueError("Transition matrix contains NaN or inf.")

        if len(set(self.states)) != len(self.states):
            raise ValueError(f"State names must be unique. Got: {self.states}")

        if P.ndim != 2 or P.shape[0] != P.shape[1]:
            raise ValueError(f"Transition matrix must be square, got shape {P.shape}.")

        n = P.shape[0]
        if len(self.states) != n:
            raise ValueError(
                f"Number of states ({len(self.states)}) must match matrix dimension ({n})."
            )

        # Reject meaningfully negative values, only clip tiny rounding errors near zero
        min_val = P.min()
        if min_val < -1e-8:
            raise ValueError(
                f"Transition matrix has negative probabilities (min={min_val:.6f})."
            )
        P = np.clip(P, 0.0, None)

        row_sums = P.sum(axis=1)
        if not np.allclose(row_sums, 1.0, atol=1e-6):
            raise ValueError(f"Every row must sum to 1.0. Current row sums: {row_sums}.")

        P.flags.writeable = False
        object.__setattr__(self, "P", P)
        object.__setattr__(self, "_index", {s: i for i, s in enumerate(self.states)})

    def index_of(self, state: str) -> int:
        try:
            return self._index[state]
        except KeyError:
            raise ValueError(f"Unknown state '{state}'. Known states: {list(self.states)}")

    def row(self, state: str) -> np.ndarray:
        """Return a copy of the transition row for the given state."""
        return self.P[self.index_of(state), :].copy()

    def as_dict(self) -> Dict[str, Dict[str, float]]:
        """Human-readable transition probabilities — used by the rationale panel."""
        return {
            s: {self.states[j]: float(self.P[i, j]) for j in range(len(self.states))}
            for i, s in enumerate(self.states)
        }


# Default models, used for development and demo purposes


def make_simple_progression() -> DiseaseModel:
    """Three-state linear disease: Healthy -> Mild -> Severe."""
    states = ("Healthy", "Mild", "Severe")
    P = np.array([
        [0.85, 0.10, 0.05],
        [0.10, 0.70, 0.20],
        [0.05, 0.15, 0.80],
    ])
    return DiseaseModel(states=states, P=P)


def make_recovery_model() -> DiseaseModel:
    """Four-state model with an absorbing Recovered state."""
    states = ("Healthy", "Mild", "Severe", "Recovered")
    P = np.array([
        [0.80, 0.15, 0.05, 0.00],
        [0.10, 0.55, 0.20, 0.15],
        [0.00, 0.10, 0.65, 0.25],
        [0.00, 0.00, 0.00, 1.00],  # absorbing state
    ])
    return DiseaseModel(states=states, P=P)


def make_chronic_model() -> DiseaseModel:
    """Five-state chronic disease model with Remission and Terminal absorbing state."""
    states = ("Remission", "Mild", "Moderate", "Severe", "Terminal")
    P = np.array([
        [0.70, 0.20, 0.07, 0.03, 0.00],
        [0.15, 0.55, 0.20, 0.08, 0.02],
        [0.05, 0.15, 0.50, 0.25, 0.05],
        [0.00, 0.05, 0.15, 0.60, 0.20],
        [0.00, 0.00, 0.00, 0.00, 1.00],  # absorbing state
    ])
    return DiseaseModel(states=states, P=P)