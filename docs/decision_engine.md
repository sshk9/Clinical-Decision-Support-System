# Decision Engine Documentation – CDSS

## Overview

The CDSS Decision Engine implements a Markov Decision Process (MDP) to evaluate and rank treatment actions for patients with diseases that evolve non-deterministically over time.

The engine uses value iteration to compute the optimal long-term expected utility of each action, balancing immediate benefits against future outcomes.

Important architectural constraint:

- The engine operates only on domain objects
- It does not access the database
- It does not compute raw clinical utility values (benefit, risk, cost)

---

## Core Mathematical Framework

### Markov Decision Process (MDP)

An MDP is defined by the tuple `(S, A, P, R, γ)`:

- S — disease states  
- A — actions  
- P — transition probabilities  
- R — reward function  
- γ — discount factor  

---

### Bellman Optimality Equation

```
V(P, s) = max_α [ r(P, s, α) + γ * Σ P_α(s'|s) * V(P_α, s') ]
```

Where:

- `V(P, s)` = long-term value of being in state s  
- `α` = action  
- `r(P, s, α)` = immediate utility  
- `γ` = discount factor  
- `P_α` = model after applying action  
- `V(P_α, s')` = value of next state  

---

### Important Clarification

The immediate utility:

```
r(P, s, α) = benefit − risk − cost
```

is **NOT computed inside the engine**.

It is computed in:

```
src/infrastructure/database.py → load_actions()
```

The engine only consumes:

```
action.immediate_utility
```

This ensures:
- separation of concerns
- testability
- no coupling to persistence

---

## Why Value Iteration Runs Per Action

Each action modifies the transition matrix:

```
P → P_α
```

Therefore:

```
V(P_α₁, s) ≠ V(P_α₂, s)
```

Implication:

- A single global value function is incorrect
- The engine must recompute value iteration for each action

---

## Value Iteration Algorithm

### Purpose

Compute optimal long-term value under a given model.

### Pseudocode

```python
V = {s: 0.0 for s in states}

for iteration in range(max_iterations):
    delta = 0.0
    
    for state in states:
        best = max(
            action.immediate_utility +
            gamma * sum(P[s][s2] * V[s2] for s2 in states)
            for action in actions
        )
        
        delta = max(delta, abs(best - V[state]))
        V[state] = best

    if delta < theta:
        break

return V
```

### Convergence

- θ = 1e-6  
- max_iterations = 1000  
- typical convergence: <200 iterations  

---

## Action Scoring

For each action α:

1. Apply α → get modified model `P_α`
2. Run value iteration on `P_α`
3. Compute:

```
expected_future = Σ P_α(s'|s) * V(P_α, s')
long_term_value = γ * expected_future
total_score = immediate_utility + long_term_value
```

4. Return `ActionScore`

---

## ActionScore Structure

| Field | Description |
|------|-------------|
| action | Action object |
| immediate_utility | Precomputed utility |
| long_term_value | Discounted expected value |
| total_score | Final ranking score |
| future_outcomes | Used for trace panel |
| gamma | Discount factor |

---

## Ranking

```
rank_actions(macro_state, actions) → sorted list
```

Sorted by:

```
total_score (descending)
```

---

## Discount Factor Interpretation

| γ | Meaning |
|--|--------|
| 0.95 | Long-term focus |
| 0.90 | Balanced (default) |
| 0.70 | Short-term focus |

---

## Sensitivity Panel (Important Limitation)

The sensitivity panel:

- does NOT recompute value iteration
- only projects score changes

Future fix:

```
rank_actions(..., gamma=new_gamma)
```

---

## Clinical Interpretation

- Immediate utility = short-term outcome  
- Long-term value = disease trajectory impact  
- Total score = combined decision metric  

---

## Limitations

| Limitation | Description | Fix |
|-----------|------------|-----|
| Fixed γ | Hardcoded | Store in disease table |
| Risk scoring | Uses state index, not severity_level | Use severity_level |
| No calibration | Does not learn | Add outcome table |
| No uncertainty | Point estimates only | Add confidence intervals |
| Sensitivity panel | Not recomputed | Re-run engine |

---

## Key Design Principles

- Pure computation layer  
- No database access  
- No UI dependencies  
- Deterministic output  
- Reproducible decisions  

---

## References

- Bellman (1957)
- Sutton & Barto (2018)