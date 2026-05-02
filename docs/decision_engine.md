# Decision Engine Documentation – CDSS

## Overview

The CDSS Decision Engine implements a **Markov Decision Process (MDP)** to evaluate and rank treatment actions for patients with diseases that evolve non‑deterministically over time. The engine uses **value iteration** to compute the optimal long‑term expected utility of each action, balancing immediate benefits against future risks.

## Core Mathematical Framework

### Markov Decision Process (MDP) Definition

An MDP is defined by the tuple `(S, A, P, R, γ)` where:
- **S** = set of disease states (e.g., Normal, Pre‑diabetic, Diabetic)
- **A** = set of treatment actions (e.g., Prescribe Metformin, Lifestyle Intervention)
- **P** = transition probabilities between states (the Markov chain)
- **R** = immediate reward/utility function (benefit - risk - cost)
- **γ** = discount factor (0 ≤ γ < 1), controlling preference for short‑term vs long‑term outcomes

### The Bellman Optimality Equation

The core of the decision engine is the **Bellman optimality equation** for a Markov Decision Process:
V(P, s) = max_α [ r(P, s, α) + γ * Σ_{s'} P_α(s'|s) * V(P_α, s') ]
**Where:**
- `V(P, s)` – the maximum expected long‑term outcome (value) starting from macro‑state (P, s)
- `P` – the current disease model (Markov chain)
- `s` – the patient's current disease state (micro‑state)
- `α` – a treatment action
- `r(P, s, α)` – immediate utility of taking action α in state s under model P
- `γ` – discount factor (default 0.9)
- `P_α` – the modified disease model after applying action α
- `P_α(s'|s)` – probability of transitioning to state s' after taking action α
- `V(P_α, s')` – value of being in state s' under the modified model

### Why Run Value Iteration Per Action?

**Key design decision:** The engine runs a separate value iteration for each action's modified model `P_α` rather than once globally.

**Reason:** In our clinical setting, each treatment action modifies the transition probabilities (the disease model) in a different way. For example:
- Prescribing Metformin shifts probability away from progressing to Diabetic
- Lifestyle Intervention shifts probability toward Normal

Because each action creates a different `P_α`, the optimal value function `V(P_α, *)` is different for each action. Therefore, we cannot compute a single `V` function and reuse it – we must compute `V` per action.

**Proof:** If two actions α₁ and α₂ produce different transition matrices `P_α₁ ≠ P_α₂`, then `V(P_α₁, s) ≠ V(P_α₂, s)` in general. The Bellman equation for `max_α` requires comparing values under different transition dynamics, so each must be evaluated separately.

**Performance consideration:** With 4–6 actions and 3–5 states, value iteration converges in <200 iterations. The computational overhead is negligible (milliseconds).

### What This Equation Represents

The Bellman equation decomposes the decision into two components:

1. **Immediate Utility** (`r(P, s, α)`): The short‑term benefit of the action, factoring in symptom relief, side effects, and complication risk.
2. **Discounted Future Value** (`γ * Σ P_α(s'|s) * V(P_α, s')`): The expected long‑term benefit of the action, considering:
   - The probability of each possible future state
   - The value of being in that future state under the modified model
   - Future decisions will also be optimal (the `max_α` inside V)

### Why Actions Modify the Markov Chain

In our clinical setting, treatment actions do **not** directly change the patient's current state. Instead, they modify the **disease progression model** (`P → P_α`). For example:
- Prescribing Metformin changes transition probabilities so that the patient is less likely to progress from Pre‑diabetic to Diabetic
- A lifestyle intervention makes it more likely to move from Mild to Normal

This is clinically realistic: treatments modify the course of the disease, not the immediate condition.

## Value Iteration Algorithm

### Purpose

Value iteration finds the optimal value function `V(P, s)` for all states under a given model. The engine runs value iteration separately for each action's modified model to compute `V(P_α, s')`.

### Algorithm Pseudocode
def value_iteration(model, actions, gamma, theta, max_iterations):
Initialize V(s) = 0 for all states s
for iteration in 1..max_iterations:
    delta = 0
    for each state s:
        # Find the best action value for this state
        best_value = max over actions a of:
            immediate_utility(a) + gamma * Σ P_a(s'|s) * V(s')
        
        delta = max(delta, |best_value - V(s)|)
        V(s) = best_value
    
    if delta < theta:
        break  # converged

return V
### Convergence Criterion

The algorithm stops when the maximum change across all states (`delta`) is less than `θ` (theta). The default value is `1e-6`, ensuring numerical stability without excessive computation.

### Maximum Iterations

A safety cap of 1000 iterations prevents infinite loops in case of non‑convergence. For well‑behaved MDPs, convergence typically occurs within 100–200 iterations.

## Immediate Utility Computation

The immediate utility `r(P, s, α)` is defined as:
immediate_utility = expected_benefit - complication_risk - side_effect_cost
Values are stored in the `action_utility` table, keyed by disease, state, and action. This decomposition allows:
- Separate reporting of benefit vs risk
- Sensitivity analysis on risk tolerance
- Multi‑objective trade‑off visualisation (benefit vs risk scatter plot)

## Scoring an Action (`_score_action`)

When scoring a single action α from the current macro‑state (P, s):

1. **Apply α** to the current model to get modified model P_α
2. **Run value iteration** on P_α (with all actions) to get V(P_α, *)
3. **For the current state s**:
   - Get the transition row from P_α: row = P_α(s'|s) for all s'
   - Compute expected future value: `Σ row[i] * V(P_α, s')`
   - Apply discount factor: `γ * expected_future`
4. **Add immediate utility**: `r(P, s, α)`
5. **Return** total score and future outcomes (for the trace panel)

## ActionScore Data Structure

The `ActionScore` dataclass stores all evaluation results:

| Field | Type | Description |
|-------|------|-------------|
| `action` | Action | The evaluated action |
| `immediate_utility` | float | r(P, s, α) |
| `long_term_value` | float | γ * Σ P_α(s'\|s) V(P_α, s') |
| `total_score` | float | immediate_utility + long_term_value |
| `future_outcomes` | List[Tuple[str, float, float]] | (state, probability, state_value) for trace panel |
| `gamma` | float | Discount factor used in calculation |

The `future_outcomes` list enables the **Decision Trace (Why‑Panel)** without recomputing value iteration.

## Ranking Actions

The `rank_actions` method scores all available actions and returns them sorted by `total_score` (descending). The top‑ranked action is the one the engine recommends.

## Discount Factor (γ) Clinical Interpretation

| γ value | Clinical Meaning |
|---------|------------------|
| 0.95 | Strong preference for long‑term outcomes; suitable for chronic diseases (e.g., Type 2 Diabetes) |
| 0.90 | Balanced (default) |
| 0.70 | Preference for short‑term relief; suitable for acute conditions |

The sensitivity analysis panel allows clinicians to interactively change γ and see how recommendations would change.

## Convergence Threshold (θ) Clinical Interpretation

θ = 1e−6 means the algorithm stops when the value function changes by less than 0.000001. This ensures clinically irrelevant changes (e.g., 0.0001 utility points) don't waste computation time.

## Example: Diabetes Action Comparison

Using the seeded data for Type 2 Diabetes (Varshney et al., 2020), typical net utility values are:

| Action | Benefit | Risk | Cost | Net Utility |
|--------|---------|------|------|--------------|
| Prescribe Metformin | 0.75 | 0.10 | 0.12 | 0.53 |
| Refer to Endocrinologist | 0.70 | 0.08 | 0.10 | 0.52 |
| Lifestyle Intervention | 0.60 | 0.05 | 0.08 | 0.47 |
| Watch and Wait | 0.20 | 0.05 | 0.02 | 0.13 |

The engine correctly ranks Metformin highest because its net utility is largest, even though it has higher risk than Lifestyle Intervention – the larger benefit outweighs the risk.

## Limitations of Current Implementation

| Limitation | Reason | Future Work |
|------------|--------|-------------|
| No real‑time model calibration | Learning from outcomes requires outcome logging | Add `treatment_outcome` table + calibration module |
| Same discount factor for all diseases | Hardcoded in `DecisionEngine.__init__` | Make disease‑specific via `get_discount_factor(disease_name)` |
| No partial observability | Assumes perfect knowledge of current state | Extend to POMDP with belief states |
| Risk‑neutral | Optimises expected value, not worst‑case | Implement CVaR (Conditional Value at Risk) |

## References

- Bellman, R. (1957). "A Markovian Decision Process". *Journal of Mathematics and Mechanics*, 6(5), 679–684.
- Sutton, R. S., & Barto, A. G. (2018). *Reinforcement Learning: An Introduction*. MIT Press.
- Varshney, V., et al. (2020). "Estimation of transition probabilities for diabetic patients using HMM". [Transition data seeded in database]
