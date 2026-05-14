# Decision Engine Documentation – CDSS

## Overview

The CDSS Decision Engine implements a Markov Decision Process (MDP) to evaluate and rank treatment actions for patients with diseases that evolve non-deterministically over time.

The engine uses value iteration to compute the optimal long-term expected utility of each action, balancing immediate benefits against future outcomes. It also produces the supporting information needed by the UI to explain the recommendation: risk score, risk level, a human-readable explanation, and the transition row from the current state under the modified model.

Architectural constraints:

- The engine operates only on domain objects (`MacroState`, `Action`, `DiseaseModel`)
- It does not access the database
- It does not import PyQt
- It does not compute raw clinical utility values (`benefit − risk − cost`)

---

## Core Mathematical Framework

### Markov Decision Process (MDP)

An MDP is defined by the tuple `(S, A, P, R, γ)`:

- S — disease states
- A — actions
- P — transition probabilities
- R — reward function
- γ — discount factor

### Bellman Optimality Equation

```
V(P, s) = max_α [ r(P, s, α) + γ * Σ_s' P_α(s'|s) * V(P_α, s') ]
```

Where:

- `V(P, s)` — long-term value of being in state s under model P
- `α` — action
- `r(P, s, α)` — immediate utility of α from state s
- `γ` — discount factor
- `P_α` — model after applying action α
- `V(P_α, s')` — value of next state s' under the modified model

---

## Immediate Utility Boundary

The immediate utility:

```
r(P, s, α) = benefit − risk − cost
```

is **not computed inside the engine**.

It is computed in:

```
src/infrastructure/database.py → load_actions()
```

The engine only consumes:

```python
action.immediate_utility
```

This boundary ensures:

- Separation of concerns
- Testability (no database needed to test scoring)
- No coupling to persistence representations

---

## Why Value Iteration Runs Per Action

Each action transforms the transition matrix:

```
P → P_α
```

The value function depends on the modified model, so:

```
V(P_α₁, s) ≠ V(P_α₂, s)
```

The engine therefore runs value iteration once per action, each time over the modified model `P_α`. Inside each VI run, the inner `max_α` sweep also considers all actions when computing each state's value — this lets a long-term plan involve different actions at different states.

The cost is computational redundancy (`N` VI runs for `N` actions). The benefit is that every action produces its own self-contained evaluation, including its own modified model row visible to the UI as the Transition Impact panel.

---

## Value Iteration Algorithm

### Purpose

Compute optimal long-term value under the modified model `P_α`.

### Pseudocode

```python
def _value_iteration(model, actions):
    V = {s: 0.0 for s in model.states}

    for _ in range(max_iterations):
        delta = 0.0

        for state in model.states:
            best = max(
                action.immediate_utility +
                gamma * sum(
                    action.apply(model).row(state)[i] * V[s_next]
                    for i, s_next in enumerate(model.states)
                )
                for action in actions
            )
            delta = max(delta, abs(best - V[state]))
            V[state] = best

        if delta < theta:
            break

    return V
```

Notes on this implementation:

- The inner `action.apply(model)` call inside `_action_value` applies each candidate action to the already-modified model passed into `_value_iteration`. This composition reflects the conceptual model: future decisions are made against the world produced by earlier ones.
- The `max` over actions for every state is what makes this a Bellman *optimality* iteration rather than policy evaluation.

### Convergence

- θ = 1e-6
- max_iterations = 1000
- Typical convergence: well under 200 iterations on the prototype's small state spaces

---

## Action Scoring

For each action α, the engine performs:

1. Apply α to the current model → `P_α`
2. Run value iteration on `P_α` with all actions → `V(P_α, ·)`
3. From the current state s, compute:

```
immediate       = action.immediate_utility
expected_future = Σ_s' P_α(s'|s) * V(P_α, s')
long_term_value = γ * expected_future
total_score     = immediate + long_term_value
```

4. Compute risk score from the modified model's transition row at the current state.
5. Build a human-readable explanation.
6. Return an `ActionScore`.

---

## ActionScore Structure

`ActionScore` is a `frozen=True` dataclass. Its fields are:

| Field | Type | Description |
|-------|------|-------------|
| `action` | `Action` | The action that was evaluated |
| `immediate_utility` | `float` | r(P, s, α) — short-term utility, taken from `action.immediate_utility` |
| `long_term_value` | `float` | γ * Σ P_α(s'\|s) * V(P_α, s') — discounted expected future value from the current state |
| `total_score` | `float` | `immediate_utility + long_term_value` — used for ranking |
| `risk_score` | `float` | 0–100 expected-severity score under the modified model |
| `risk_level` | `str` | "Low" (< 33), "Medium" (< 66), or "High" |
| `explanation` | `str` | Multi-line human-readable rationale for the UI |
| `transition_row` | `dict[str, float]` | `{state_name: probability}` from the current state under `P_α` |

Why immutable: results are produced once during ranking and consumed unchanged by the UI (Decision Trace, Sensitivity Panel, Risk-Benefit Plot). Freezing prevents accidental modification and keeps the explanation, score, and transition row internally consistent.

---

## Risk Scoring

Computed in `_calculate_risk_score`:

1. Assign severity weights to states based on their order in `model.states`. The first state gets weight 0, the last gets 100, and the rest are evenly spaced between.
2. Compute the expected severity from the current state:

```
risk_score = Σ_s' P_α(s'|s) * severity_weight(s')
```

3. Round to one decimal place.

`risk_level` thresholds:

| risk_score | risk_level |
|------------|------------|
| < 33 | Low |
| < 66 | Medium |
| ≥ 66 | High |

Important: risk scoring is intentionally simplified for the prototype. It is **not** part of the Bellman update — it is computed alongside, as a separate clinical-interpretation metric. This keeps the optimisation criterion (total score) and the interpretation metric (risk) decoupled. The Sensitivity Panel can therefore apply a risk penalty *outside* the ranking math without re-running value iteration.

A future improvement is to use the `severity_level` column from `disease_state` instead of position-based weights.

---

## Explanation Generation

Computed in `_build_explanation`. Each explanation includes:

- Current patient state
- Risk score and level
- Most likely next state under the modified model (with probability)
- Immediate utility of the action
- Clinical rationale (the action's description text, if available)
- Count of previous interventions, if any

The explanation is built inside the engine so that the strings it references are guaranteed to come from the same evaluation that produced the score. The UI consumes the result as a string and does not perform any further reasoning over the model.

---

## Ranking

```python
DecisionEngine.rank_actions(macro_state, actions) → List[ActionScore]
```

Sorted by `total_score` descending. Returns an empty list if `actions` is empty.

---

## Discount Factor Interpretation

| γ | Meaning |
|---|---------|
| 0.95 | Long-term focus — future outcomes weigh heavily |
| 0.90 | Balanced (default) |
| 0.70 | Short-term focus — immediate utility dominates |

The engine validates that `0.0 ≤ γ < 1.0` at construction time. A value of 1.0 or above would break the contraction property of value iteration and would not converge.

---

## Sensitivity Panel — Important Limitation

The Sensitivity Panel projects how `total_score` would shift under different future-value weights and risk penalties:

```
Projected Score = Immediate Utility + γ * Expected Future Value − Risk Penalty
```

It does **not** rerun value iteration. The ranking shown in the Ranked Actions table is fixed at the time of computation; the Sensitivity Panel is a what-if exploration tool, not a recomputation.

A future enhancement could call `rank_actions(..., gamma=new_gamma)` on the fly to actually re-rank under different discount factors.

---

## Clinical Interpretation of the Three Numbers

| Field | Meaning for the clinician |
|-------|---------------------------|
| Immediate utility | Short-term outcome of taking this action right now |
| Long-term value | Expected impact on the disease trajectory under this action |
| Total score | Combined decision metric used for ranking |

The Decision Trace surfaces these separately so the clinician can see which side of the trade-off is driving a recommendation.

---

## Limitations

| Limitation | Description | Suggested Fix |
|------------|-------------|---------------|
| Fixed γ | Hardcoded default of 0.9 in `DecisionEngine.__init__` | Make per-disease configurable; store in `disease` table |
| Position-based risk weights | Uses state index instead of clinical severity | Use the `severity_level` column from `disease_state` |
| No calibration | Engine does not learn from clinician decisions | Add outcome table and update transition probabilities |
| No uncertainty estimates | Returns point estimates only | Add confidence intervals or distribution-based estimates |
| Sensitivity Panel | Projects scores, does not actually re-rank | Re-run `rank_actions` on parameter change |
| Computational redundancy | Runs VI once per action | Cache shared VI work when `P_α` differs from `P` only in one row |

---

## Key Design Principles

- Pure computation layer — no I/O, no UI dependencies
- Operates only on domain objects
- Deterministic given the same inputs
- Reproducible decisions across runs
- All intermediate values needed for explanation are co-produced with the score

---

## References

- Bellman, R. (1957). *Dynamic Programming.*
- Sutton, R. S., & Barto, A. G. (2018). *Reinforcement Learning: An Introduction* (2nd ed.).
