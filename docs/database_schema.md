# Database Schema – CDSS

## Overview

The CDSS uses SQLite as its persistence layer. All tables are created by `init_db()` in `src/infrastructure/database.py`.

The schema supports:

- disease models
- disease states
- Markov transition matrices
- treatment actions
- action utilities
- patient status
- user authentication
- recommendation audit logging

Important persistence boundary:

- Accept / Reject / Override decisions are persisted in `recommendation_run`
- Apply Action and Simulate Progression are currently in-memory only and are not written back to `patient_status`

---

## Entity Relationship Diagram (Conceptual)

```
┌─────────────┐     ┌─────────────────┐     ┌───────────────────┐
│   disease   │────<│  disease_state  │────<│ markov_transition │
│  - id       │     │  - id           │     │  - model_id       │
│  - name     │     │  - disease_id   │     │  - from_state_id  │
│  - desc     │     │  - state_name   │     │  - to_state_id    │
└─────────────┘     │  - severity_lvl │     │  - probability    │
                    └─────────────────┘     └───────────────────┘
                            ▲                         ▲
                            │                         │
┌─────────────┐             │                         │
│markov_model │─────────────┘                         │
│ - id        │                                       │
│ - disease_id│                                       │
│ - name      │                                       │
│ - version   │                                       │
│ - is_active │                                       │
└─────────────┘                                       │
                                                      │
┌─────────────┐     ┌─────────────────┐               │
│   action    │────<│  action_utility │               │
│  - id       │     │  - disease_id   │               │
│  - disease_id│    │  - state_id     │               │
│  - name     │     │  - action_id    │               │
│  - desc     │     │  - benefit      │               │
│  - improve  │     │  - risk         │               │
│  - worsen   │     │  - cost         │               │
│  - delta    │     └─────────────────┘               │
└─────────────┘                                       │
                                                      │
┌──────────────┐       ┌─────────────────────┐        │
│   patient    │──────<│  patient_status     │────────┘
│  - id        │       │  - patient_id       │
│  - first_name│       │  - disease_id       │
│  - last_name │       │  - current_state_id │
└──────────────┘       │  - active_model_id  │
                       └─────────────────────┘

┌──────────────────────┐
│ recommendation_run   │
│  - id                │
│  - patient_id        │
│  - recommended_action│
│  - recommended_score │
│  - clinician_decision│
│  - override_action   │
│  - timestamp         │
└──────────────────────┘

┌───────────────────┐
│ users             │
│  - id             │
│  - username       │
│  - hashed_password│
│  - salt           │
└───────────────────┘
```

---

## Table Definitions

### `disease`

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER | Primary key, auto-increment |
| `name` | TEXT | Unique disease name |
| `description` | TEXT | Human-readable description |

Used for:
- grouping states
- linking actions
- linking Markov models
- analytics summaries

---

### `disease_state`

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER | Primary key, auto-increment |
| `disease_id` | INTEGER | Foreign key to `disease(id)` |
| `state_name` | TEXT | Disease state name |
| `severity_level` | INTEGER | Clinical severity level, usually 1–5 |

Foreign key:
- `disease_id` → `disease(id)`

Important note:

`severity_level` exists in the schema, but the current engine risk score still uses state index ordering rather than this column. This is documented as a future improvement in the TDD.

---

### `markov_model`

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER | Primary key, auto-increment |
| `disease_id` | INTEGER | Foreign key to `disease(id)` |
| `model_name` | TEXT | Human-readable model name |
| `version` | TEXT | Version string |
| `is_active` | BOOLEAN | Indicates the active model for a disease |

Foreign key:
- `disease_id` → `disease(id)`

Important note:

The current system supports active model selection, but does not implement model calibration or model version lineage.

---

### `markov_transition`

| Column | Type | Description |
|--------|------|-------------|
| `model_id` | INTEGER | Foreign key to `markov_model(id)` |
| `from_state_id` | INTEGER | Foreign key to `disease_state(id)` |
| `to_state_id` | INTEGER | Foreign key to `disease_state(id)` |
| `probability` | REAL | Transition probability between 0 and 1 |

Primary key:
- `(model_id, from_state_id, to_state_id)`

Foreign keys:
- `model_id` → `markov_model(id)`
- `from_state_id` → `disease_state(id)`
- `to_state_id` → `disease_state(id)`

Constraint expectation:

For each `(model_id, from_state_id)`, transition probabilities should sum to 1.0. This is validated when constructing the `DiseaseModel`.

---

### `action`

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER | Primary key, auto-increment |
| `disease_id` | INTEGER | Foreign key to `disease(id)` |
| `action_name` | TEXT | Treatment action name |
| `description` | TEXT | Human-readable explanation |
| `improve_state` | TEXT | State to shift probability toward |
| `worsen_state` | TEXT | State to shift probability away from |
| `delta` | REAL | Probability mass to shift |

Foreign key:
- `disease_id` → `disease(id)`

Important note:

Treatment actions modify the transition matrix, not the patient’s current state directly.

---

### `action_utility`

| Column | Type | Description |
|--------|------|-------------|
| `disease_id` | INTEGER | Foreign key to `disease(id)` |
| `state_id` | INTEGER | Foreign key to `disease_state(id)` |
| `action_id` | INTEGER | Foreign key to `action(id)` |
| `expected_benefit` | REAL | Expected clinical benefit |
| `complication_risk` | REAL | Complication risk |
| `side_effect_cost` | REAL | Side-effect or inconvenience cost |

Primary key:
- `(disease_id, state_id, action_id)`

Foreign keys:
- `disease_id` → `disease(id)`
- `state_id` → `disease_state(id)`
- `action_id` → `action(id)`

Immediate utility:

```python
immediate_utility = round(expected_benefit - complication_risk - side_effect_cost, 6)
```

Important note:

This value is computed in `load_actions()` in the infrastructure layer. The decision engine does not compute benefit − risk − cost itself; it consumes the precomputed `Action.immediate_utility`.

---

### `patient`

| Column | Type | Description |
|--------|------|-------------|
| `id` | TEXT | Primary key, e.g. `P001` |
| `first_name` | TEXT | Patient first name |
| `last_name` | TEXT | Patient last name |

Used for:
- patient listing
- audit log joins
- patient status lookup

---

### `patient_status`

| Column | Type | Description |
|--------|------|-------------|
| `patient_id` | TEXT | Primary key, foreign key to `patient(id)` |
| `disease_id` | INTEGER | Foreign key to `disease(id)` |
| `current_state_id` | INTEGER | Foreign key to `disease_state(id)` |
| `active_model_id` | INTEGER | Foreign key to `markov_model(id)` |

Foreign keys:
- `patient_id` → `patient(id)`
- `disease_id` → `disease(id)`
- `current_state_id` → `disease_state(id)`
- `active_model_id` → `markov_model(id)`

Important persistence note:

The current implementation reads from `patient_status`, but Apply Action and Simulate Progression do not write updates back to this table. Therefore, patient model changes and simulated state changes are session-only.

---

### `recommendation_run`

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER | Primary key, auto-increment |
| `patient_id` | TEXT | Foreign key to `patient(id)` |
| `recommended_action` | TEXT | Action recommended by the engine |
| `recommended_score` | REAL | Score of the recommended action |
| `clinician_decision` | TEXT | `accept`, `reject`, or `override` |
| `override_action` | TEXT | Alternative action selected by clinician, if any |
| `timestamp` | TIMESTAMP | Defaults to current timestamp |

Foreign key:
- `patient_id` → `patient(id)`

Used by:
- `log_clinician_decision()`
- `get_audit_log()`
- `AuditWidget`

Important note:

This is the only normal clinical workflow table that receives writes during application use.

---

### `users`

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER | Primary key, auto-increment |
| `username` | TEXT | Unique username |
| `hashed_password` | TEXT | SHA-256 hash of salt + password |
| `salt` | TEXT | Per-user random salt |

Used by:
- `get_user_by_username()`
- `create_user()`
- `verify_credentials()`

Important note:

There is no `role` column in the current schema. Authentication returns only a boolean result, so role-based access control is not implemented.

---

## Key Query and Conversion Functions

| Function | Tables Used | Purpose |
|----------|-------------|---------|
| `init_db()` | all tables | Creates schema if missing |
| `seed_data()` | all core tables | Seeds demo diseases, patients, actions, utilities, and admin user |
| `get_user_by_username()` | `users` | Fetches login hash and salt |
| `create_user()` | `users` | Creates a user with salted password hash |
| `load_disease_model()` | `patient_status`, `markov_model`, `disease_state`, `markov_transition` | Builds a `DiseaseModel` domain object |
| `load_actions()` | `patient_status`, `action`, `action_utility` | Builds `Action` domain objects and computes immediate utility |
| `load_patients_with_actions()` | patient-related tables via service calls | Builds `PatientRecord` objects for the UI |
| `get_state_distribution()` | `disease`, `disease_state`, `patient_status` | Provides data for population trend charts |
| `get_benefit_risk_for_patient()` | `patient_status`, `action`, `action_utility` | Provides data for risk-benefit scatter plot |
| `get_action_utility_comparison()` | `action`, `action_utility` | Provides aggregate action utility comparison |
| `log_clinician_decision()` | `recommendation_run` | Inserts clinician decision into audit log |
| `get_audit_log()` | `recommendation_run`, `patient` | Reads clinician decision history |

---

## Persistence Boundary

The schema supports both persistent and non-persistent workflows.

### Persisted

| Workflow | Table |
|---------|-------|
| User authentication | `users` |
| Seeded diseases, states, actions, utilities | `disease`, `disease_state`, `action`, `action_utility` |
| Current seeded patient state | `patient_status` |
| Clinician decision logging | `recommendation_run` |

### Not Persisted

| Workflow | Current Behaviour |
|---------|------------------|
| Apply Action | Updates `MacroState` in memory only |
| Simulate Progression | Updates current state in memory only |
| MacroState history | Stored only in domain object during runtime |

Recommended future improvement:

- Persist simulated state changes using `UPDATE patient_status`
- Persist applied action effects via either:
  - per-patient model override table
  - new `markov_model` row per applied action
  - event-sourced history table

---

## Gaps Compared to a Full Clinical Database

The current schema intentionally omits several tables that would be expected in a production clinical system.

### Not Implemented

| Table / Concept | Purpose | Reason Not Implemented |
|----------------|---------|------------------------|
| `clinician` | Store clinician metadata | Simplified to `users` table |
| `encounter` | Track patient visits | Out of scope for prototype |
| per-action recommendation scores | Store all action scores per run | Only top recommendation is logged |
| action-effect table | Store complex action transition effects | Simplified to `improve_state`, `worsen_state`, `delta` |
| model calibration log | Track learned model updates | Calibration not implemented |
| model lineage / parent model | Track model version ancestry | Each model treated independently |
| treatment outcomes | Record patient outcomes after decisions | Required for learning, not implemented |

---

## Why These Gaps Are Acceptable for the Prototype

The implemented schema supports the core academic goals of the project:

- representing disease progression as Markov models
- storing patient disease state
- storing treatment actions and utility values
- running recommendations through the decision engine
- logging clinician decisions for audit

The missing tables are important for production use, but they are not required for the prototype decision engine to function.

Most missing features would extend the current schema rather than replace it.

---

## Recommended Future Schema Extensions

| Extension | Purpose |
|----------|---------|
| `treatment_outcome` | Store observed outcomes for calibration |
| `patient_model_override` | Persist patient-specific transition matrices |
| `patient_state_history` | Persist simulated or real disease progression |
| `recommendation_score` | Store all action scores per recommendation run |
| `role` column on `users` | Enable role-based access control |
| `patient_disease` | Support comorbidities |
| `model_calibration_log` | Track transition-probability updates over time |