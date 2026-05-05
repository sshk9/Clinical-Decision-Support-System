# Technical Design Document (TDD)
## Clinical Decision Support System (CDSS)

**Version:** 1.0  
**Date:** May 2026 
**Authors:** Eva, Sara, Stuti

---

## 1. System Overview

The Clinical Decision Support System (CDSS) is a desktop application that assists General Practitioners in making optimal treatment decisions for patients with diseases that evolve non‑deterministically over time. The system models disease progression as a Markov Decision Process (MDP), evaluates treatment actions using value iteration, and presents ranked recommendations with fully transparent calculations.

**Technology Stack:**
- **Python 3.10+** – core language
- **PyQt5** – GUI framework (Fusion style)
- **SQLite** – embedded database (no external server)
- **NumPy** – matrix operations for Markov chains
- **Matplotlib** – charts (risk‑benefit plot, trends)
- **hashlib / secrets** – password hashing and salting

The system is packaged as a standalone executable, designed to run on Windows, macOS, and Linux without network dependencies.

---

## 2. Codebase Structure

```
Clinical-Decision-Support-System/
├── main.py                          # Entry point
├── requirements.txt                 # Dependencies
├── cdss.db                          # SQLite database (auto‑generated)
├── README.md                        # User‑facing documentation
├── docs/                            # Developer documentation
│   ├── tdd.md          # This file
│   ├── architecture.md
│   ├── database_schema.md
│   ├── decision_engine.md
│   └── code_style.md
├── src/
│   ├── ui/                          # Presentation layer
│   │   ├── main_window.py
│   │   ├── add_patient_dialog.py
│   │   ├── login_view.py
│   │   ├── patient_view.py (inside main_window)
│   │   ├── comparison_widget.py
│   │   ├── trend_widget.py
│   │   ├── audit_widget.py
│   │   ├── risk_benefit_plot.py
│   │   └── sensitivity_panel.py
│   ├── decision_engine/             # MDP calculation layer
│   │   └── engine.py
│   ├── domain/                      # Business objects
│   │   ├── disease_model.py
│   │   ├── action.py
│   │   ├── macro_state.py
│   │   ├── patient.py
│   │   └── patient_record.py
│   ├── infrastructure/              # External dependencies
│   │   ├── database.py
│   │   ├── auth_service.py
│   │   └── patient_service.py
│   └── analytics/                   # Pure computation
│       └── analytics.py
└── tests/                           # Unit tests
    └── test_basic.py
```

**Layer Responsibilities:**

| Layer | Contains | Responsibility | Must Not |
|-------|----------|----------------|----------|
| **Presentation** | `ui/` | Collect user input, display data, format output | Contain business logic or database queries |
| **Decision Engine** | `engine.py` | Rank actions using MDP value iteration | Touch UI or database |
| **Domain** | `domain/` | Pure business objects (Markov chains, actions, patients) | Have any persistence or UI code |
| **Infrastructure** | `infrastructure/` | Database queries, authentication, file I/O | Contain clinical logic |
| **Analytics** | `analytics/` | Population‑level computations (comparisons, success rates) | Write to database or know about UI |

This separation ensures testability, maintainability, and the ability to swap components (e.g., replace SQLite with PostgreSQL) without rewriting clinical logic.

---

## 3. Component Descriptions

### 3.1 `DiseaseModel` (`domain/disease_model.py`)

A Markov chain model representing disease progression. Stores:
- `states` – ordered tuple of state names (e.g., `("Normal", "Pre-diabetic", "Diabetic")`)
- `P` – row‑stochastic transition matrix where `P[i][j] = P(state_i → state_j)`

**Stochastic property:** Every row of the transition matrix must sum to 1.0. The constructor validates this with `np.allclose(row_sums, 1.0, atol=1e-6)`. This ensures probabilities are valid and model behaves correctly in simulation.

**Example:** For a three‑state diabetes model:
```
P = [[0.7, 0.2, 0.1],      # From Normal: 70% stay, 20% to Pre-diabetic, 10% to Diabetic
     [0.1, 0.6, 0.3],      # From Pre-diabetic: 10% improve, 60% stay, 30% worsen
     [0.0, 0.1, 0.9]]      # From Diabetic: 0% improve, 10% improve to Pre-diabetic, 90% stay
```

### 3.2 `Action` (`domain/action.py`)

A treatment action that modifies the disease model. Fields:
- `name` – identifier shown in UI (e.g., "Prescribe Metformin")
- `immediate_utility` – short‑term benefit (benefit − risk − cost), stored in `action_utility` table
- `improve_state` – target state to shift probability toward (e.g., "Normal")
- `worsen_state` – state to shift probability away from (e.g., "Diabetic")
- `delta` – amount of probability to move (0–1), typically 0.05–0.20

**Key method:** `apply(model) → new_model`. It works as follows:
1. Copy the transition matrix row‑by‑row
2. For each row: subtract `delta` from the `worsen_state` column
3. Add `delta` to the `improve_state` column
4. Renormalise each row to sum to 1.0

The patient's current state `s` does not change – actions modify the **progression model** (the probabilities), not the immediate condition. This reflects clinical reality: giving a patient Metformin today doesn't instantly cure them, but changes their risk of future complications.

**Example:** Prescribing Metformin with delta=0.10:
```
Before:  [0.7, 0.2, 0.1]  (from Normal: 70% stay, 20% to Pre-diabetic, 10% to Diabetic)
After:   [0.7, 0.3, 0.0]  (shift 10% away from Diabetic to Pre-diabetic, then renormalise)
Result:  [0.7, 0.3, 0.0]  (actually: [0.77, 0.23, 0.0] after renormalisation, but in this case no renorm needed)
```

### 3.3 `MacroState` (`domain/macro_state.py`)

Represents the full patient state `(P, s)` as defined in the technical specification:
- `model` – current Markov chain (the disease progression model P)
- `current_state` – current disease state (s, e.g., "Normal")
- `history` – immutable tuple of `HistoryStep` records, each containing the action taken, timestamp, and resulting macro‑state

**Why immutable:** Every action creates a new `MacroState` with appended history rather than modifying the existing one. This enables:
- Time‑travel UI – scroll back to previous states (not yet implemented)
- Full audit trail – complete record of clinical pathway
- Prevents bugs – no accidental shared state between different branches of reasoning

**Key methods:**
- `apply_action(action)` – creates new `MacroState` with updated model and history
- `simulate_step()` – advances the micro‑state by sampling from the current row of the transition matrix (stochastic)
- `transition_impact_summary()` – returns before/after probabilities for the most recent action (used in the transition impact panel to show how the disease model changed)

### 3.4 `DecisionEngine` (`decision_engine/engine.py`)

The core MDP solver. Implements the Bellman optimality equation:

```
V(P, s) = max_α [ r(P, s, α) + γ * Σ_{s'} P_α(s'|s) * V(P_α, s') ]
```

**English translation:** The maximum expected value (utility) starting from macro‑state (P, s) is the maximum over all actions α of: the immediate benefit of that action plus (discount factor times the expected future value over all possible next states).

**Why per‑action value iteration:** Each action produces a different modified model `P_α`. The value function `V(P_α, *)` is different for each action because they change the transition matrix differently. Therefore, the engine must run value iteration separately for every action. This is computationally acceptable because state spaces are small (3–5 states) and convergence occurs in <200 iterations. A single global value iteration would be mathematically incorrect because it would ignore the fact that the model changes with each action.

**Key methods:**
- `rank_actions(macro_state, actions)` → `List[ActionScore]` sorted by total score (best first)
- `_value_iteration(model, actions)` → `Dict[str, float]` value function for all states
- `_score_action(macro_state, action, actions)` → `ActionScore` including `future_outcomes` for the trace panel

---

## 4. Database Schema (`infrastructure/database.py`)

Manages SQLite connection and all queries. 

**Key tables:**

| Table | Purpose | Validates |
|-------|---------|-----------|
| `disease` | Disease names and descriptions | N/A |
| `disease_state` | States per disease with severity (1–5) | Severity in 1–5 range |
| `markov_model` | Versioned Markov models with active flag | Only one model active per disease |
| `markov_transition` | Transition probabilities (sum to 1 per state) | Row sums ≈ 1.0 (atol=1e-6) |
| `action` | Treatment actions with effect parameters | delta in 0–1 range |
| `action_utility` | Benefit, risk, cost per (disease, state, action) | All values in 0–1 range |
| `patient` | Patient demographics (ID, first name, last name) | Patient ID unique |
| `patient_status` | Current state and active model per patient | Foreign keys valid |
| `users` | Authentication (username, salted SHA256 hash, role) | Username unique, hash non‑empty |
| `recommendation_run` | Clinician decision log (audit trail) | Timestamps indexed, patient_id valid |

**Key queries:**
- `get_all_patients()` – returns `(id, full_name, current_state, disease_name)` for the patient list
- `get_model_for_patient(patient_id)` – returns `(state_names, transition_matrix)` for the decision engine
- `get_actions_for_patient(patient_id)` – returns raw action tuples with immediate utilities
- `log_clinician_decision(patient_id, recommended_action, recommended_score, clinician_decision, override_action)` – inserts decision record for audit

### UI Widgets (`src/ui/`)

| Widget | Purpose | Data Input | Output |
|--------|---------|------------|--------|
| `LoginView` | Authentication form | username, password → call `auth_service.verify_credentials()` | role (admin/clinician) |
| `Sidebar` | Navigation buttons | role → conditionally show admin items (Audit Log, Settings) | signal patient_selected when patient clicked |
| `PatientView` | Main clinical interface | `Patient`, `List[Action]` from database | None (updates UI only) |
| `PatientManagementView` | Patient list with add/edit buttons | `List[PatientRecord]` from `patient_service.load_patients_with_actions()` | signal patient_selected |
| `ComparisonWidget` | Side‑by‑side patient comparison | two `patient_id`s | comparison table + effectiveness chart |
| `TrendWidget` | Population health analytics | `get_state_distribution()` result | bar charts for severity distribution |
| `AuditWidget` | Decision log (admin only) | `get_audit_log()` result + CSV export | export button → save CSV to disk |
| `RiskBenefitPlot` | Scatter plot: benefit (X) vs risk (Y) | `get_benefit_risk_for_patient()` result | matplotlib figure embedded in QWidget |
| `SensitivityAnalysisPanel` | What‑if controls for γ and risk tolerance | current `ActionScore` | recomputed score without full value iteration |

---

## 5. Component Interactions

### Workflow 1: Patient Load → Recommendation → Clinician Decision

```
User selects patient from PatientManagementView
         │
         ▼ (signal: patient_selected)
MainWindow._on_patient_selected()
         │
         ├─► PatientView.load_patient(patient, actions)
         │         │
         │         └─► PatientView._refresh()
         │                   │
         │                   ├─► DecisionEngine.rank_actions(macro_state, actions)
         │                   │         │
         │                   │         ├─► For each action:
         │                   │         │     ├─► action.apply(model)
         │                   │         │     ├─► _value_iteration(P_α, actions)
         │                   │         │     └─► _score_action(macro_state, action)
         │                   │         │
         │                   │         └─► return List[ActionScore] sorted by total_score
         │                   │
         │                   ├─► Populate ranked actions table (Action name, Immediate, Long-term, Total)
         │                   ├─► Set risk score / progress bar from top action
         │                   ├─► Display explanation from top action
         │                   └─► Store self._current_scores for trace panel
         │
         ├─► Sidebar.set_active(1)  # Show PatientView
         └─► Stack.setCurrentIndex(1)

User clicks an action row in the ranked actions table
         │
         └─► PatientView._update_trace()
                   │
                   ├─► Populate trace_tree with Bellman decomposition
                   │   (for each future state: probability, state value, contribution)
                   │
                   ├─► sensitivity_panel.set_score(score)
                   │   (initialize sliders with current γ and risk)
                   │
                   └─► _update_risk_display()
                       (update progress bar color based on severity)

User adjusts γ slider in sensitivity_panel
         │
         └─► sensitivity_panel._on_gamma_changed(new_gamma)
                   │
                   ├─► Recompute long_term_value with new γ
                   └─► Update score display (no full value iteration, just reweight)

User clicks Accept / Reject / Override button
         │
         └─► PatientView._on_accept() / _on_reject() / _on_override()
                   │
                   ├─► Determine decision type and override action (if override)
                   │
                   └─► database.log_clinician_decision(
                            patient_id=self.patient.id,
                            recommended_action=top_action.name,
                            recommended_score=top_score,
                            clinician_decision='accept'/'reject'/'override',
                            override_action=chosen_action.name if override else None
                       )
                       │
                       └─► INSERT INTO recommendation_run
```

### Workflow 2: Patient Applied Action → State Change

```
User clicks "Apply Action" button in PatientView
         │
         └─► PatientView._on_apply_action()
                   │
                   ├─► Get selected action from table
                   │
                   ├─► new_macro_state = self.macro_state.apply_action(selected_action)
                   │   (creates new MacroState with updated model and history)
                   │
                   ├─► database.update_patient_status(
                            patient_id,
                            new_model_id,
                            current_state_id  # unchanged, still same state
                       )
                   │
                   └─► PatientView._refresh()  # Recompute recommendations with new model
```

### Workflow 3: Simulate Disease Progression

```
User clicks "Simulate Step" button
         │
         └─► PatientView._on_simulate_step()
                   │
                   ├─► new_macro_state = self.macro_state.simulate_step()
                   │   (samples next state from current row of transition matrix)
                   │
                   ├─► database.update_patient_status(
                            patient_id,
                            active_model_id,  # unchanged
                            new_state_id      # changed to sampled state
                       )
                   │
                   └─► PatientView._refresh()  # Recompute recommendations for new state
```

---

## 6. Key Algorithms

### 6.1 Value Iteration Pseudocode

```
Function value_iteration(model, actions, gamma=0.9, theta=1e-6, max_iterations=1000):
    """
    Compute optimal value function for a disease model.
    
    Args:
        model: DiseaseModel (transition matrix P)
        actions: List of Action objects available in this model
        gamma: Discount factor (lower = favour short-term)
        theta: Convergence threshold (smaller = more accurate but slower)
        max_iterations: Safety cap to prevent infinite loops
    
    Returns:
        Dict[state_name: float] mapping each state to its value V(s)
    """
    
    # Initialize value function to zero
    V = {state: 0.0 for state in model.states}
    
    for iteration in range(1, max_iterations + 1):
        delta = 0  # Track maximum value change this iteration
        
        for state in model.states:
            # Find the best action value for this state
            best_q_value = -infinity
            
            for action in actions:
                # Step 1: Apply action to get modified model
                P_modified = action.apply(model)
                
                # Step 2: Get transition probabilities from this state after action
                state_idx = model.states.index(state)
                transition_probs = P_modified.P[state_idx]  # row of matrix
                
                # Step 3: Compute expected future value
                expected_future = sum(
                    transition_probs[j] * V[model.states[j]]
                    for j in range(len(model.states))
                )
                
                # Step 4: Immediate utility + discounted future
                q_value = action.immediate_utility + gamma * expected_future
                
                # Step 5: Keep track of best
                best_q_value = max(best_q_value, q_value)
            
            # Track convergence: how much did this state's value change?
            delta = max(delta, abs(best_q_value - V[state]))
            
            # Update value for next iteration
            V[state] = best_q_value
        
        # Stop early if converged
        if delta < theta:
            print(f"Value iteration converged in {iteration} iterations")
            break
    
    return V
```

**Key variables:**
- `V[s]` – expected long‑term utility starting from state s
- `gamma` – discount factor (0.9 default). γ=0.95 favours long‑term outcomes (chronic disease); γ=0.70 favours short‑term relief (acute conditions)
- `theta` – convergence threshold (1e−6). Changes smaller than this are clinically irrelevant, so algorithm stops
- `max_iterations` – safety cap (1000 iterations)
- `P_modified` – transition matrix after action is applied
- `transition_probs` – single row of the matrix (probabilities from current state)
- `q_value` – action‑value function Q(s, a) for this state and action

### 6.2 Immediate Utility Formula

```
immediate_utility = expected_benefit - complication_risk - side_effect_cost
```

**Example for Metformin in Pre-diabetic state:**
- `expected_benefit` = 0.75 (high probability of preventing progression to Diabetic)
- `complication_risk` = 0.10 (small risk of lactic acidosis or hypoglycaemia)
- `side_effect_cost` = 0.12 (GI upset, minor inconvenience)
- `immediate_utility` = 0.75 − 0.10 − 0.12 = **0.53**

Values are stored in the `action_utility` table and retrieved by state and patient disease. This decomposition enables:
- Separate reporting of benefit vs risk in the UI
- Sensitivity analysis: adjust risk tolerance to recompute immediate utility
- Multi‑objective trade‑off visualisation: scatter plot of benefit (X‑axis) vs risk (Y‑axis)

### 6.3 Action Matrix Modification Algorithm

For a model with states `["Normal", "Mild", "Severe"]`:

Action: `Prescribe Metformin` with:
- `improve_state` = "Mild"
- `worsen_state` = "Severe"
- `delta` = 0.10

**For each row of the transition matrix:**

```
Original row: [0.30, 0.40, 0.30]  (Normal, Mild, Severe)
              indices: [0,   1,    2]

1. Subtract delta from worsen_state column:
   row[2] -= 0.10
   row = [0.30, 0.40, 0.20]

2. Add delta to improve_state column:
   row[1] += 0.10
   row = [0.30, 0.50, 0.20]

3. Renormalise (divide by row sum):
   row_sum = 0.30 + 0.50 + 0.20 = 1.00
   row = row / 1.00 = [0.30, 0.50, 0.20]

Final row: [0.30, 0.50, 0.20]
```

**Clinical meaning:** Under Metformin, the patient is now less likely to progress to Severe (30% → 20%) and more likely to remain in Mild or improve to Mild (40% → 50%).

### 6.4 Scoring a Single Action

**Input:** `macro_state`, `action`, `all_actions`  
**Output:** `ActionScore` with total_score, immediate_utility, long_term_value, future_outcomes

```
1. Apply action to current model:
   P_modified = action.apply(macro_state.model)

2. Run value iteration on modified model:
   V = value_iteration(P_modified, all_actions, gamma=0.9)

3. Get current state index:
   s_idx = macro_state.model.states.index(macro_state.current_state)

4. Extract immediate utility:
   immediate = action.immediate_utility

5. Compute expected future value:
   transition_row = P_modified.P[s_idx]
   expected_future = sum(
       transition_row[j] * V[macro_state.model.states[j]]
       for j in range(len(macro_state.model.states))
   )

6. Apply discount factor:
   long_term_value = 0.9 * expected_future

7. Compute total:
   total_score = immediate + long_term_value

8. Build future_outcomes list (for trace panel):
   future_outcomes = [
       (state_name, probability, V[state_name])
       for each state with probability > 0
   ]

9. Return ActionScore(
       action=action,
       immediate_utility=immediate,
       long_term_value=long_term_value,
       total_score=total_score,
       future_outcomes=future_outcomes,
       gamma=0.9
   )
```

---

## 7. Data Flow – "Run Recommendation" Click (Complete Trace)

```
User clicks "Run Analysis" button in PatientView
         │
         ├─► Signal fires: recommend_requested
         │
         ▼
MainWindow._on_recommend_requested()
         │
         ├─► Load current patient and actions from self.patient, self.actions
         │
         ├─► Create MacroState(model=model, current_state=state, history=[])
         │
         ├─► Call DecisionEngine.rank_actions(macro_state, actions)
         │         │
         │         ├─► For each action in actions:
         │         │     │
         │         │     ├─► Call _score_action(macro_state, action, actions)
         │         │     │     │
         │         │     │     ├─► modified_model = action.apply(macro_state.model)
         │         │     │     │
         │         │     │     ├─► V = _value_iteration(modified_model, actions)
         │         │     │     │     [runs 50-200 iterations until convergence]
         │         │     │     │
         │         │     │     ├─► Compute immediate_utility from action
         │         │     │     │
         │         │     │     ├─► Get transition row from modified P
         │         │     │     │
         │         │     │     ├─► expected_future = Σ P_modified[s,:] * V[:]
         │         │     │     │
         │         │     │     ├─► long_term = 0.9 * expected_future
         │         │     │     │
         │         │     │     ├─► total = immediate + long_term
         │         │     │     │
         │         │     │     └─► return ActionScore(...)
         │         │     │
         │         │     └─► Append ActionScore to results list
         │         │
         │         └─► Sort results by total_score descending
         │
         ├─► Return ranked List[ActionScore]
         │
         ├─► PatientView._refresh()
         │     │
         │     ├─► _update_ranked_table()
         │     │     ├─► Clear table
         │     │     └─► For each ActionScore:
         │     │         Insert row (action name, immediate, long_term, total)
         │     │         Highlight top row in green
         │     │
         │     ├─► _update_risk_display()
         │     │     ├─► Get top action score
         │     │     ├─► Set progress bar to total_score
         │     │     ├─► Colour bar: green (good), yellow (medium), red (poor)
         │     │     └─► Display explanation text
         │     │
         │     └─► Store self._current_scores = results
         │
         └─► UI displays results (no database write yet)
                [User can now click Accept/Reject/Override to log decision]
```

**Total time: 200-500ms** (depends on number of actions and iteration count).

---

## 8. Design Decisions and Assumptions

| Decision | Rationale | Alternative Considered | Trade‑off |
|----------|-----------|------------------------|-----------|
| **SQLite not PostgreSQL** | No network/server required; single‑file deployment; sufficient for <1000 patients | PostgreSQL (rejected – overkill, adds complexity) | No concurrent users, not suitable for hospital‑wide deployment |
| **PyQt5 not web** | Desktop app matches GP workflows; rapid UI responsiveness; no browser compatibility overhead | Flask + React (rejected – complexity, deployment overhead) | Not accessible remotely; single‑user per machine |
| **Immutable domain objects** | Prevents side effects; enables full history tracking; simplifies debugging | Mutable objects with deep copy (rejected – error‑prone) | Slightly higher memory use for large histories |
| **Per‑action value iteration** | Each action changes transition matrix differently; value function V(P_α) is action‑dependent | Single global value iteration (invalid – ignores model change) | Higher computation cost (negligible for small state spaces) |
| **Seeded data from literature** | No real patient data available for academic project; published probabilities are defensible | Real patient data (rejected – not available; privacy concerns) | Not representative of specific GP population |
| **"Success" = severity ≤ 2** | Clinical judgement: severity levels 1–5, where 1=best, 5=worst; threshold 2 is reasonable | Composite outcome (rejected – requires calibration) | Simplistic; real outcomes are multidimensional |
| **Role‑based access control** | Admin users see audit log; clinicians see only clinical features | Single user (rejected – required by spec; needed for transparency) | Admin UI not fully implemented |
| **SHA256 hashing with salt** | Industry standard; resistant to rainbow tables | MD5 (rejected – broken), plain text (rejected – security risk) | Slower login (acceptable for desktop, <100ms) |

**Key assumptions:**
- GPs will accurately input the patient's current disease state.
- Disease models and utility values are pre‑defined by clinical experts and do not change during a clinical session.
- The discount factor γ = 0.9 is clinically appropriate for chronic diseases (diabetes, CKD).
- SQLite concurrency is sufficient for single‑user desktop use (not suitable for multi‑user hospital system).
- Stochastic simulation (randomly sampling next states) is acceptable for demonstration; real system would need empirical data.
- Immediate utilities are independent of time (no learning or model update from outcomes).

---

## 9. Known Limitations and Future Work

### 9.1 Not Implemented (Documented Gaps)

| Gap | Reason | Impact | Future Work |
|-----|--------|--------|-------------|
| **Real‑time model calibration** | Would require outcome logging and Bayesian update algorithm | Transition probabilities fixed after seeding | Add `treatment_outcome` table + EM or Bayesian inference function |
| **Admin UI for user management** | Role column exists in `users` table but no UI to create/delete users | Can only use seeded credentials | Add `AdminView` with user CRUD and role assignment |
| **Confidence intervals on scores** | Value iteration produces point estimates only | Clinicians cannot assess uncertainty | Bootstrap resampling of utility values or Bayesian posterior inference |
| **Browser / web deployment** | PyQt5 is desktop‑only framework | Not accessible remotely or from mobile | Port decision engine to REST API; build React frontend |
| **HL7/FHIR export** | No integration with hospital EHR systems | Manual data entry for external use | Add JSON export in FHIR format with HL7-compliant identifiers |
| **Concurrent users** | SQLite is single‑writer; locks during updates | Only one GP can use system at a time | Migrate to PostgreSQL with proper connection pooling |
| **Time-travel UI** | History is stored in `MacroState.history` but no UI to browse back | Cannot revert to previous state | Add timeline slider and "revert to checkpoint" button |
| **Outcome prediction** | No way to forecast patient state after N steps | Cannot do "what-if" on disease progression | Extend engine to run Markov chain simulation with confidence intervals |

### 9.2 What a New Team Would Build Next (Priority Order)

**Phase 1 (High Priority):**
1. **Calibration Module** – After logging clinician decisions and patient outcomes, update Markov transition probabilities using Expectation‑Maximisation (EM) or Bayesian inference. This transforms the static system into one that learns from real clinical data.
2. **Admin Dashboard** – User management (CRUD), role assignment, model version control, audit log export.
3. **Time-Travel UI** – Use the immutable `MacroState.history` to allow clinicians to scroll back through previous states and "undo" actions.

**Phase 2 (Medium Priority):**
4. **Patient Timeline Scrubbing** – Interactive timeline showing when each action was taken and how the model changed.
5. **Outcome Recording** – Form to log actual patient outcomes (e.g., "patient progressed to Diabetic after 6 months") for model calibration.
6. **REST API Wrapper** – Decouple decision engine from PyQt5; expose `rank_actions()` as `/api/recommendations` endpoint.

**Phase 3 (Lower Priority):**
7. **Web Frontend** – React/Vue frontend consuming REST API; accessible from browser and mobile.
8. **Confidence Intervals** – Bootstrap resampling of action utilities to compute credible intervals on scores.
9. **Multi‑disease workflows** – Support patients with comorbidities (two simultaneous diseases).

---

## 10. Setup Guide for New Developers

### 10.1 Prerequisites

- Python 3.10 or higher (check with `python --version`)
- pip package manager (included with Python)
- Git (optional, for cloning repository)
- ~500 MB disk space (Python + dependencies + database)

### 10.2 Installation Steps (Windows)

```bash
# 1. Clone the repository (or download and extract .zip)
git clone https://github.com/sshk9/Clinical-Decision-Support-System.git
cd Clinical-Decision-Support-System

# 2. Create virtual environment
python -m venv venv

# 3. Activate virtual environment
venv\Scripts\activate
# You should see (venv) prefix in terminal

# 4. Upgrade pip
python -m pip install --upgrade pip

# 5. Install dependencies
pip install -r requirements.txt
# Should see: Successfully installed PyQt5, numpy, matplotlib, pytest

# 6. Initialise and seed the database
python -m src.infrastructure.database
# Should create cdss.db and seed with demo data

# 7. Run tests
pytest tests/test_basic.py -v
# Should pass all tests (10+)

# 8. Start the application
python main.py
# PyQt5 window should open
```

### 10.3 Installation Steps (macOS / Linux)

```bash
git clone https://github.com/sshk9/Clinical-Decision-Support-System.git
cd Clinical-Decision-Support-System

python3 -m venv venv
source venv/bin/activate

python3 -m pip install --upgrade pip
pip install -r requirements.txt

python3 -m src.infrastructure.database

pytest tests/test_basic.py -v

python3 main.py
```

### 10.4 Database Initialisation Output (Expected)

When you run `python -m src.infrastructure.database`, you should see:

```
Creating database tables...
Database tables initialized successfully

Seeding database...
  Inserted 2 diseases
  Inserted 6 disease states
  Inserted 2 Markov models
  Inserted 15 transitions
  Inserted 8 actions
  Inserted 24 action utilities
  Inserted 6 patients
  Inserted 6 patient statuses
  Inserted 2 users (admin, doctor)

Database seeded: 2 diseases, 6 patients, 2 users

Verification:
Found 6 patients:
  - P001: John Smith - Normal (Type 2 Diabetes)
  - P002: Maria Klein - Diabetic (Type 2 Diabetes)
  - P003: Lucas Mitchell - Pre-diabetic (Type 2 Diabetes)
  - P004: Anna Fischer - Mild CKD (Chronic Kidney Disease)
  - P005: James Patel - Severe CKD (Chronic Kidney Disease)
  - P006: Sophie Müller - Normal (Chronic Kidney Disease)

Database ready!
File size: 48 KB
```

If you see errors like "no such table: users", run the database initialisation again.

### 10.5 First Login

After starting the app (`python main.py`), you'll see a login screen. Use one of these credentials:

- **Admin user:** `admin` / `admin123` – sees Audit Log tab + Admin features
- **Clinician user:** `doctor` / `doctor123` – sees only clinical features (not yet implemented)

### 10.6 Running Tests

```bash
# All tests
pytest tests/test_basic.py -v

# Specific test class
pytest tests/test_basic.py::TestDiseaseModel -v

# Specific test method
pytest tests/test_basic.py::TestDiseaseModel::test_row_sums_to_one -v

# With coverage report (requires pytest-cov)
pip install pytest-cov
pytest --cov=src tests/test_basic.py --cov-report=html
# Opens htmlcov/index.html in browser
```

### 10.7 Project Dependencies

```
PyQt5==5.15.10              # GUI framework
numpy==1.24.3               # Numerical operations
matplotlib==3.7.1           # Charting
pytest==7.4.0               # Testing
```

No additional packages required. System runs offline after initial setup.

### 10.8 Common Issues and Solutions

| Issue | Symptom | Solution |
|-------|---------|----------|
| **Module not found: PyQt5** | `ImportError: No module named PyQt5` | Ensure `venv` is activated (`venv\Scripts\activate`), then `pip install PyQt5` |
| **No such table: users** | `sqlite3.OperationalError: no such table: users` | Run `python -m src.infrastructure.database` to create tables |
| **Invalid credentials** | Login fails with correct username/password | Check that database was seeded with `python -m src.infrastructure.database` |
| **matplotlib backend error** | `ImportError: cannot import name '_c_internal_utils'` | Reinstall matplotlib: `pip uninstall matplotlib && pip install matplotlib==3.7.1` |
| **Port 5000 already in use** | N/A (desktop, no port) | – |
| **Relative import error** | `ImportError: attempted relative import with no known parent package` | Run with `python -m main`, not `python main.py` |

### 10.9 Directory Structure After Setup

```
Clinical-Decision-Support-System/
├── venv/                    # Virtual environment (created by you)
├── cdss.db                  # SQLite database (auto-generated)
├── main.py
├── requirements.txt
├── src/
│   ├── ui/
│   ├── decision_engine/
│   ├── domain/
│   ├── infrastructure/
│   └── analytics/
├── tests/
├── docs/
│   ├── technical_design.md  # You are here
│   ├── architecture.md
│   ├── database_schema.md
│   ├── decision_engine.md
│   └── code_style.md
└── README.md
```

### 10.10 Debugging Tips

**Enable logging:**
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

**Test database connection:**
```python
from src.infrastructure.database import get_connection
conn = get_connection()
cursor = conn.execute("SELECT COUNT(*) FROM patient")
print(cursor.fetchone()[0], "patients in database")
```

**Test decision engine:**
```python
from src.decision_engine.engine import DecisionEngine
from src.infrastructure.database import get_model_for_patient, get_actions_for_patient

model = get_model_for_patient("P001")
actions = get_actions_for_patient("P001")
engine = DecisionEngine()
scores = engine.rank_actions(model, actions)
print(f"Top action: {scores[0].action.name}, score: {scores[0].total_score}")
```

---

## 11. Conclusion

The CDSS implements a complete Markov Decision Process framework for clinical decision support. The architecture separates concerns cleanly: UI (`src/ui/`), MDP engine (`engine.py`), domain objects (`domain/`), and infrastructure (`database.py`, `auth_service.py`). Key algorithms (value iteration, action matrix modification) are documented with pseudocode and variable definitions. Limitations are acknowledged transparently. A new developer can clone, install dependencies, seed the database, and run the application in under five minutes. 
