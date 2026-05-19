# Technical Design Document (TDD) – Clinical Decision Support System (CDSS)

**Date:** May 2026
**Authors:** Eva, Sara, Stuti

*Academic prototype.*

---

## 1. System Overview

### 1.1 Purpose of the System

The Clinical Decision Support System is a desktop-based academic prototype designed to support General Practitioners when reviewing possible treatment actions for patients whose disease state can change probabilistically over time. The system is intended to demonstrate how a structured decision model can make recommendations more transparent, rather than replacing clinical judgement.

The current implementation uses a Markov-chain-based disease model and value iteration to rank treatment actions according to their expected long-term outcome. The interface then presents the ranking together with explanations, sensitivity analysis, risk-benefit visualisation, transition impact, and an audit log of clinician decisions.

The system is not clinically validated. It is a university software engineering prototype and must not be used for real medical diagnosis, treatment, or patient care.

### 1.2 Conceptual Model

Each patient is represented as a macro-state:

```
(P, s)
```

Where:

- `P` = the disease transition model / transition probability matrix
- `s` = the patient's current disease state

Disease progression is probabilistic, so the patient does not move through states in a fixed deterministic order. Instead, the transition matrix stores the probability of moving from the current state to each possible next state.

A treatment action modifies the transition matrix:

```
P -> P_alpha
```

The important modelling assumption is that treatment actions do not immediately change the patient's current state. Instead, they change the probabilities of future disease progression. The current state changes only when progression is simulated according to the active transition probabilities.

### 1.3 Decision Process

The recommendation process works as follows:

1. The current patient macro-state is loaded.
2. Available treatment actions are retrieved.
3. For each action, the disease transition model is modified.
4. Value iteration is applied to estimate long-term state values.
5. Immediate utility is combined with expected future value.
6. Actions are ranked by total score.
7. The UI displays ranked actions, decision trace, sensitivity analysis, risk-benefit plot, transition impact, and audit logging.

### 1.4 Technology Stack

| Component | Technology | Rationale |
|-----------|------------|-----------|
| Language | Python 3.10+ | Rapid development and strong scientific ecosystem |
| GUI | PyQt5 | Desktop GUI framework suitable for the academic prototype |
| Numerical Computation | NumPy | Efficient matrix and probability calculations |
| Database | SQLite | Lightweight local persistence with no server setup |
| Visualisation | matplotlib | Embedded charts and plots |
| Authentication | hashlib + secrets | Simple salted password hashing for prototype login |
| Version Control | Git + GitHub | Collaboration and version history |

### 1.5 Intended Audience

This document is intended for future developers or another student team who need to understand, maintain, and extend the CDSS without having the original team explain the code manually. It describes the structure of the codebase, how the main components interact, the decision logic, data flow, assumptions, limitations, and developer setup steps.

---

## 2. Codebase Structure

### 2.1 Overview

The project uses a layered architecture. The main goal is to keep clinical/domain logic, decision logic, database access, application services, analytics, and user interface code separate from each other.

```
src/
│
├── domain/
│     Core clinical concepts such as Patient, Action, MacroState, and DiseaseModel.
│
├── decision_engine/
│     Value iteration, expected utility computation, action scoring, and ranking.
│
├── application/
│     Service layer that coordinates data access for the UI and hides direct database calls.
│
├── infrastructure/
│     SQLite database access, authentication, persistence, and patient loading.
│
├── analytics/
│     Population-level statistics and action comparison calculations.
│
└── ui/
      PyQt presentation layer, organised into views, widgets, charts, and dialogs.
```

### 2.2 Layer Responsibilities

#### Domain Layer — `src/domain/`

The domain layer contains the core clinical model used by the rest of the system.

- DiseaseModel
- Action
- MacroState
- Patient
- PatientRecord

**Responsibilities:**

- Represent disease states and transition matrices.
- Represent the patient macro-state (P, s).
- Apply treatment actions to disease models.
- Store patient-related domain information.
- Keep action history for runtime explanation and transition impact.

**Important constraints:**

- No PyQt code.
- No SQL/database access.
- No direct UI responsibility.

#### Decision Engine Layer — `src/decision_engine/`

The decision engine contains the recommendation logic. It works on domain objects and returns ActionScore objects for the UI to display.

- Value iteration.
- Expected future value calculation.
- Action scoring.
- Risk score and risk level calculation.
- Human-readable explanation generation.
- Ranking of treatment actions.

**Important constraints:**

- Works on domain objects.
- Does not access the database directly.
- Does not contain UI code.

#### Application Layer — `src/application/`

The application layer is a service layer added to reduce coupling between the UI and database access. UI views call services instead of directly calling database functions.

```
DashboardView           -> dashboard_service.py            -> database.py
AuditWidget             -> audit_service.py                -> database.py
TrendWidget             -> trend_service.py                -> database.py
ComparisonWidget        -> comparison_service.py           -> database.py
PatientManagementView   -> patient_management_service.py   -> database.py
PatientView             -> decision_audit_service.py       -> database.py
```

This keeps database-specific logic away from UI files and makes future changes safer.

#### Infrastructure Layer — `src/infrastructure/`

The infrastructure layer is responsible for persistence and authentication.

- SQLite database connection and schema setup.
- Seed data for diseases, states, actions, patients, and demo user.
- Authentication service.
- Loading patient records from the database.
- Converting database rows into domain objects.

The file `database.py` currently contains several database-related functions. This is acceptable for a prototype, but a future version could split it into repository files such as `patient_repository.py`, `audit_repository.py`, `action_repository.py`, `disease_repository.py`, and `auth_repository.py`.

#### Analytics Layer — `src/analytics/`

The analytics layer contains pure calculation functions used by the analytics and comparison screens.

- Population-level statistics.
- Action comparison calculations.
- Success-rate calculations.
- Data preparation for analytics views.

#### UI Layer — `src/ui/`

The UI layer is responsible for presentation and user interaction. It displays results but delegates calculations to the decision engine and database-related work to services.

```
ui/
│
├── main_window.py
│     Application shell and navigation between screens.
│
├── views/
│     Full application screens such as Dashboard, Patient Management, Analytics,
│     Trends, Audit Log, and Patient View.
│
├── widgets/
│     Reusable UI components such as Sidebar and Sensitivity Panel.
│
├── charts/
│     Visualisation components such as Risk-Benefit Plot.
│
├── dialogs/
│     Pop-up windows such as Login and Add Patient.
│
└── ui_helpers.py
      Shared UI colours, labels, cards, and badge helpers.
```

---

## 3. Interactions Between Components

### 3.1 Startup Flow

```
main.py
  -> database initialisation
  -> seed data if needed
  -> LoginView
  -> MainWindow
  -> patient data loaded
  -> user navigates through sidebar
```

When the application starts, `main.py` creates the QApplication, initialises the SQLite database, seeds the demo data if the admin account does not exist, opens the login dialog, and then opens the main window after successful authentication.

### 3.2 Login Flow

1. The user enters username and password.
2. LoginView calls auth_service.
3. auth_service retrieves the stored password hash and salt.
4. The entered password is salted and hashed.
5. If the hash matches, MainWindow opens.
6. If invalid, an error message is shown.

### 3.3 Patient Selection Flow

1. PatientManagementView displays patients.
2. User double-clicks a patient.
3. A signal emits the selected patient and available actions.
4. MainWindow receives the signal.
5. MainWindow loads PatientView.
6. PatientView calls DecisionEngine to rank actions.
7. Ranked actions are displayed.

### 3.4 Recommendation Flow

```
PatientView
  -> DecisionEngine.rank_actions()
  -> ActionScore objects returned
  -> Ranked Actions table updated
  -> Decision Trace updated
  -> Sensitivity Analysis updated
  -> Risk-Benefit Plot shown
```

PatientView is the main clinical screen for a selected patient. It is responsible for displaying the recommendation output, but the scoring is performed by DecisionEngine.

### 3.5 Data Access Flow

```
UI View
  -> application service
  -> infrastructure/database.py
  -> SQLite database
```

This flow is important because database access is no longer directly embedded inside the UI. It makes the UI easier to modify and keeps persistence logic more centralised.

---

## 4. Algorithms and Decision Logic

### 4.1 Markov Chain Disease Model

Disease progression is represented using discrete disease states and transition probabilities. A row in the transition matrix represents the probabilities of moving from one state to all possible next states.

Example disease states:

```
Normal -> Mild
Mild -> Moderate
Moderate -> Severe
```

Each row in the transition matrix must sum to 1.0. The DiseaseModel class validates that the matrix is square, contains valid probabilities, has unique state names, and matches the number of states.

### 4.2 Treatment Actions

A treatment action modifies transition probabilities. A useful treatment may increase the probability of moving to an improved state and decrease the probability of moving to a worse state.

- increase probability of improving
- decrease probability of worsening
- keep some probability of staying in the same state

A treatment action does not immediately move the patient to a new state. It changes the probability of future transitions. The current disease state changes only when Simulate Progression samples the next state from the current transition row.

### 4.3 Value Iteration

The system uses value iteration to estimate the long-term value of disease states under a modified transition model. The core Bellman-style formula is:

```
V(s) = max_a [ r(s,a) + gamma * sum P(s'|s,a) V(s') ]
```

In simple terms, V(s) is the long-term value of being in state s, r(s,a) is the immediate utility of taking action a, gamma is the discount factor, and P(s'|s,a) is the probability of moving to a next state after the action has modified the transition model.

The implementation uses `gamma = 0.9` by default, `theta = 1e-6` as the convergence threshold, and `max_iterations = 1000` as a safety cap.

### 4.4 Action Score

For each action, the engine returns an ActionScore object. It includes:

- Immediate Utility
- Long-Term Value
- Total Score
- Risk Score
- Risk Level
- Explanation
- Future Outcomes

The ranked table mainly displays Immediate Utility, Long-Term Value, and Total Score, while the other values support the decision trace, explanation panel, risk indicators, and visualisations.

### 4.5 Immediate Utility

Immediate utility represents the short-term usefulness of an action. Conceptually, it is:

```
Immediate Utility = benefit - risk - cost
```

In the current implementation, the decision engine consumes `action.immediate_utility`. This keeps the engine independent from database-specific calculation details.

**Simplification.** Immediate utility is presently defined per action and is therefore independent of the patient's current disease state `s`. The same action α is assigned the same immediate utility regardless of whether the patient is in a Normal, Mild, or Severe state. This is a deliberate prototype simplification and does not fully reflect clinical reality, in which the short-term usefulness of a treatment typically depends on the patient's current condition. For example, prescribing metformin would be expected to yield substantially different immediate utility for a patient in a Normal state compared with a patient in a Prediabetic or Diabetic state. A clinically faithful formulation would compute immediate utility as `r(s, α)` rather than `r(α)`. This limitation is restated in §8.1 and revisited in §8.2.

### 4.6 Total Score

The total score combines immediate utility with discounted expected future value:

```
Total Score = Immediate Utility + Long-Term Value
```

The ranked recommendations are sorted by Total Score from highest to lowest.

### 4.7 Risk Score

The risk score is a simplified prototype metric based on expected disease severity after applying an action. The engine assigns severity weights according to the order of disease states, calculates the expected next-state severity, and scales the result to 0 – 100.

The categorical risk level is Low, Medium, or High. This is useful for the interface, but it is not a clinically validated risk model.

### 4.8 Decision Trace

The Decision Trace explains how the score for the selected action was calculated. It is included so that the recommendation is not presented as a black box.

- immediate benefit
- possible future outcomes
- probability of each future state
- value of each future state
- discounted future value
- net utility / total score

### 4.9 Sensitivity Analysis

The Sensitivity Analysis panel allows the user to explore how projected score changes when future value weight and risk tolerance are adjusted.

```
Projected Score = Immediate Utility + gamma * Expected Future Value - Risk Penalty
```

Future value weight controls how much expected future outcomes matter. Risk penalty reduces the projected score based on the action's risk score. Where risk penalty is calculated as `risk score / 100 * risk penalty weight`.

**Important distinction:** the ranked table's Total Score does not include the sensitivity risk penalty. The Sensitivity Analysis Projected Score does include the risk penalty. This means sensitivity analysis is a what-if explanation tool, not the primary ranking formula.

### 4.10 Transition Impact

The Transition Impact panel shows how the last applied action changed transition probabilities from the patient state at the time of action.

The panel is patient-state specific. It shows only transitions from the state the patient was in when the action was applied.

Example:

```
Mild CKD -> Normal:      0.100 -> 0.220  up
Mild CKD -> Severe CKD:  0.200 -> 0.080  down
```

---

### 4.11 Apply Action and Simulate Progression

The system distinguishes between two distinct runtime operations, reflecting the conceptual two-player formulation introduced in the Business Requirements Document, in which the disease evolves under the influence of two actors: *Nature* and the *Decision Maker*.

#### Apply Action — the Decision Maker's move

`Apply Action` represents the action of the General Practitioner. It corresponds to the macro-level move of the Decision Maker, who selects a treatment in order to influence the patient's prospective disease trajectory.

Formally, applying an action α to the patient macro-state (P, s) yields:

```
α : (P, s) -> (P_α, s)
```

That is, the action modifies the disease transition matrix `P -> P_α`, while the current disease state `s` remains unchanged. The operation therefore alters the *probabilities* of future transitions, but does not in itself move the patient to a new state. This reflects the clinical interpretation that prescribing a treatment changes the likelihood of future health outcomes, rather than producing an immediate transition.

Within the implementation, `Apply Action` updates the in-memory transition matrix held by the patient's domain object and records the applied action in the runtime action history, where it is subsequently consumed by the Transition Impact panel.

#### Simulate Progression — Nature's move

`Simulate Progression` represents the move of Nature. It models the non-deterministic evolution of the disease over time, in accordance with the Markov-chain formulation of disease progression.

Formally, given the current macro-state (P, s), Nature samples the next state `s'` from the probability distribution defined by the row of P corresponding to s:

```
s' ~ P(· | s)
```

The sampled state `s'` then replaces `s` as the patient's current disease state. The transition matrix P itself remains unchanged by this operation, as it represents the underlying disease dynamics rather than an immediate outcome.

The implementation draws the next state using a weighted random selection over the candidate next states, with weights given by the corresponding transition probabilities. As a result, repeated invocations of `Simulate Progression` from the same starting state may yield different outcomes, in accordance with the intended probabilistic semantics.

#### Rationale for non-deterministic progression

The decision to sample the next state stochastically, rather than selecting the most probable state deterministically, is deliberate and reflects the project's underlying modelling assumptions:

- Disease progression in real patients is inherently uncertain. A deterministic "most likely next state" would obscure the variability that the Markov model is intended to capture.
- The two-player framing requires Nature to behave as a genuine source of uncertainty. Were Nature to select outcomes deterministically, the Decision Maker would be operating against a predictable adversary, which would undermine the purpose of value iteration and expected-utility ranking.
- Stochastic sampling enables the system to demonstrate, over repeated simulations, that aggregate outcomes converge toward the real-world distributions encoded in the transition matrix — a property aligned with the success criteria stated in the BRD.

#### Summary of the distinction

| Operation | Modifies | Leaves unchanged | Conceptual role |
|-----------|----------|------------------|-----------------|
| Apply Action | Transition matrix P | Current state s | Decision Maker's move |
| Simulate Progression | Current state s | Transition matrix P | Nature's move |

This separation ensures that the effect of clinical decisions and the effect of disease evolution remain analytically distinct within the system, even though both operations contribute to the patient's overall trajectory.

## 5. Data Flow Within the System

### 5.1 Database Initialisation

The SQLite database is initialised automatically when the application starts. The `init_db()` function creates required tables if they do not already exist. The `seed_data()` function adds demo diseases, states, Markov transitions, actions, patients, and the demo user if needed.

### 5.2 Patient Loading

```
database rows
  -> infrastructure/patient_service.py
  -> domain objects
  -> UI views
```

Patient records are converted into domain objects before they are passed to the decision engine. This prevents the decision engine from depending on database rows or SQL logic.

### 5.3 Clinician Decision Logging

The patient screen includes three decision buttons:

- **Accept:** Records that the clinician accepted the top recommendation.
- **Reject:** Records that the clinician rejected the recommendation.
- **Override:** Records that the clinician selected a lower-ranked action instead of the top recommendation.

These decisions are saved in the audit log through the application service layer:

```
PatientView -> decision_audit_service.py -> database.py
```

### 5.4 Runtime Simulation

Apply Action and Simulate Progression currently update the in-memory patient object during runtime.

- Apply Action
- Simulate Progression

**Important limitation:** these changes are not permanently persisted to the database. After restarting the application, simulated or applied runtime state changes are reset. The audit log can record clinician decisions, but the current patient macro-state changes from runtime simulation are not written back as persistent patient status updates.

---

## 6. Architecture and Design for Change

### 6.1 Design Motivation

The CDSS is designed with maintainability and future change in mind. Since software systems often evolve after the first implementation, the codebase is organised so that future changes remain as localised as possible.

The main architectural goal is to avoid a monolithic design where UI code, database access, decision logic, and domain logic are mixed together. Instead, the system is structured into separate layers and UI submodules, each with a clear responsibility.

This improves readability, maintainability, testability, extensibility, and reduces unintended side effects.

### 6.2 Separation of Concerns

```
domain/           -> clinical concepts and state representation
decision_engine/  -> value iteration and recommendation ranking
application/      -> service coordination between UI and infrastructure
infrastructure/   -> database and persistence operations
analytics/        -> population-level calculations
ui/               -> presentation and user interaction
```

The decision engine does not contain PyQt code. Domain objects do not contain SQL queries. The UI displays data and handles user actions, but the actual decision calculations are delegated to the decision engine.

This means that changing the visual layout of the system should not require changing the recommendation algorithm, and changing the algorithm should not require rewriting the UI.

### 6.3 Cohesion

Cohesion means that responsibilities inside a module should be closely related. The project improves cohesion by keeping related functionality together.

```
DashboardView              -> dashboard statistics and population status
PatientManagementView      -> patient list, search, add patient, export
PatientView                -> clinical overview for one selected patient
AuditWidget                -> clinician decision audit records
TrendWidget                -> population health trends
ComparisonWidget           -> patient comparison and analytics
SensitivityAnalysisPanel   -> what-if projected score analysis
RiskBenefitPlot            -> benefit/risk visualisation
```

Previously, several UI responsibilities were combined inside `main_window.py`. After refactoring, the UI is split into focused files. This makes each module easier to understand and reduces the chance that a change in one screen accidentally affects another screen.

### 6.4 Coupling

Coupling describes how dependent modules are on each other. The system reduces coupling by introducing an application service layer between the UI and infrastructure.

Before:

```
UI View -> database.py
```

After:

```
UI View -> application service -> infrastructure/database.py
```

```
DashboardView           -> dashboard_service.py            -> database.py
AuditWidget             -> audit_service.py                -> database.py
TrendWidget             -> trend_service.py                -> database.py
ComparisonWidget        -> comparison_service.py           -> database.py
PatientManagementView   -> patient_management_service.py   -> database.py
PatientView             -> decision_audit_service.py       -> database.py
```

The UI no longer needs to know the details of database access. If database queries change in the future, most changes can be handled inside the service or infrastructure layer instead of being spread across multiple UI files.

### 6.5 Orthogonality

Orthogonality means that components are independent enough that changing one part does not unexpectedly affect unrelated parts.

- Changing the dashboard layout does not affect the decision engine.
- Changing value iteration does not affect login or patient management.
- Changing audit log display does not affect disease model transitions.
- Changing database access can be isolated mostly inside infrastructure and application services.
- Changing the risk-benefit plot does not affect authentication or patient creation.

### 6.6 Design for Future Change

The architecture supports future extension. Examples include:

- A new UI screen can be added under `ui/views/` and connected in `main_window.py`.
- A new reusable UI component can be added under `ui/widgets/`.
- A new chart can be added under `ui/charts/`.
- A new dialog can be added under `ui/dialogs/`.
- A new decision scoring rule can be added in `decision_engine/`.
- A new database query can be hidden behind an application service.
- A future migration from SQLite to another database would mostly affect infrastructure and service code, not the UI.

This means the system is not only implemented to work now, but also organised so that future improvements can be added with less risk.

---

## 7. Important Design Decisions and Assumptions

### 7.1 Desktop Application

The system is implemented as a desktop application using PyQt5 because the project requirements focus on a standalone prototype. This keeps setup simple and avoids the extra complexity of a web server, API layer, or hospital integration.

### 7.2 SQLite Database

SQLite is used because it is lightweight, requires no separate database server, and is suitable for a local academic prototype.

### 7.3 Markov Chain Disease Model

Disease progression is modelled using a discrete-state Markov chain. This fits the project goal because it allows disease progression to be represented with clear states and transition probabilities.

### 7.4 Single Disease Per Patient

Each patient is currently associated with one disease model. This keeps the prototype manageable and makes the recommendation process easier to trace.

### 7.5 Fixed Discount Factor

The engine uses a fixed discount factor by default, currently `gamma = 0.9`. This means future outcomes matter strongly, but are still discounted compared with immediate utility.

### 7.6 Simplified Risk Scoring

Risk scoring is simplified and based on expected severity. It is useful for demonstrating the concept but is not clinically validated.

### 7.7 Runtime Simulation Is Not Persistent

Apply Action and Simulate Progression are used for runtime demonstration and do not permanently update the database.

### 7.8 Prototype Status

The system is an academic prototype and should not be used for real clinical decision-making.

---

## 8. Limitations and Future Work

### 8.1 Current Limitations

1. Apply Action is not persisted to the database.
2. Simulate Progression is not persisted to the database.
3. Risk scoring is simplified and not clinically validated.
4. The system does not yet implement learning/calibration from real outcomes.
5. The system currently supports one disease per patient.
6. `database.py` could later be split into repository modules.
7. PatientView could later be split into smaller widgets.
8. Authentication is simple and does not include full role-based access control.
9. The system is a desktop prototype, not a web or hospital-integrated system.
10. More automated tests should be added.
11. Immediate utility is defined per action and is therefore independent of the patient's current disease state. The same action returns the same immediate utility regardless of whether the patient is currently in a healthy or an advanced state. This does not fully reflect clinical reality, in which the short-term usefulness of a treatment typically depends on the patient's condition (for instance, the utility of prescribing metformin differs substantially between a Normal, Prediabetic, and Diabetic patient).

### 8.2 Recommended Future Improvements

12. Persist applied actions and simulated progression.
13. Improve risk scoring with clinically meaningful parameters.
14. Add learning/calibration from observed patient outcomes.
15. Split `database.py` into repository modules.
16. Add more automated tests for the decision engine and services.
17. Add role-based access control.
18. Add export/reporting functionality for recommendations.
19. Prepare the architecture for possible web migration.
20. Extend immediate utility to be state-dependent — that is, compute `r(s, α)` in place of `r(α)` — so that the short-term usefulness of an action reflects the patient's current disease state. This would also require extending the action data model and seed data to carry per-state utility values rather than a single scalar.

---

## 9. Developer Setup / How to Run

Recommended setup from the project root:

```
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

Alternative explicit database setup, if needed:

```
python -m src.infrastructure.database
python main.py
```

The SQLite database is initialised automatically when the application starts. Demo seed data is created when the admin user is not found.

Default login credentials:

- **Username:** admin
- **Password:** admin123

---

## 10. Testing Checklist

This checklist can be used by the professor or a future developer team to verify the main system behaviours.

- Login works.
- Dashboard loads.
- Dashboard refreshes after adding a patient.
- Patient Management opens.
- Search works.
- Add Patient works.
- Open patient by double-clicking.
- Ranked actions display.
- Decision Trace updates when selecting a ranked action.
- Sensitivity Analysis updates when selecting a ranked action.
- Risk-Benefit Plot displays.
- Apply Action works.
- Transition Impact updates after applying an action.
- Accept decision is logged.
- Reject decision is logged.
- Override decision is logged.
- Audit Log refreshes and shows records.
- Analytics view loads patients.
- Analytics comparison works.
- Trends view updates population statistics.
- CSV export works.
- Application restarts successfully.

---

## 11. Conclusion

The CDSS is a working academic prototype that demonstrates probabilistic disease modelling, treatment action ranking, value iteration, decision explanation, sensitivity analysis, transition impact, risk-benefit visualisation, and clinician decision auditing.

The system is organised using a layered architecture with clear separation between domain logic, decision engine, application services, infrastructure, analytics, and UI. This structure improves maintainability and makes the project easier for a future team to understand and extend.

Although some limitations remain, especially around persistence of simulated state changes, clinical validation, and repository-level database separation, the current implementation provides a solid foundation for future development.
