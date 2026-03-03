import numpy as np


ACTIONS = ["Medication A", "Lifestyle Intervention", "Medication B"]
STATES = ["S1", "S2", "S3"]


# Placeholder transition matrices per action (toy example)
TRANSITIONS = {
    "Medication A": np.array([
        [0.70, 0.20, 0.10],
        [0.20, 0.60, 0.20],
        [0.10, 0.30, 0.60],
    ]),
    "Lifestyle Intervention": np.array([
        [0.65, 0.25, 0.10],
        [0.25, 0.55, 0.20],
        [0.15, 0.35, 0.50],
    ]),
    "Medication B": np.array([
        [0.60, 0.25, 0.15],
        [0.20, 0.55, 0.25],
        [0.10, 0.25, 0.65],
    ]),
}

IMMEDIATE_UTILITY = {
    "Medication A": 5.0,
    "Lifestyle Intervention": 3.5,
    "Medication B": 4.5,
}


def rank_actions(state: str, discount: float = 0.7):
    if state not in STATES:
        raise ValueError(f"Unknown state '{state}'. Use one of: {STATES}")

    s_idx = STATES.index(state)
    recs = []

    for action in ACTIONS:
        P = TRANSITIONS[action]
        # simple future proxy: probability of improving (S1) minus worsening (S3)
        future = float(P[s_idx, 0] - P[s_idx, 2])
        score = float(IMMEDIATE_UTILITY[action] + discount * future)

        row = P[s_idx, :]
        entropy = -float(np.sum(row * np.log(row + 1e-12)))
        confidence = max(0.0, 1.0 - (entropy / 1.2))

        recs.append({"action": action, "score": score, "confidence": confidence})

    recs.sort(key=lambda r: r["score"], reverse=True)
    return recs
