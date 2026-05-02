# Database Schema – CDSS

## Overview

The CDSS uses **SQLite** as its persistence layer. All tables are created by `init_db()` in `src/infrastructure/database.py`. The schema is designed to support Markov disease models, patient tracking, action utilities, and clinical decision logging.

## Entity Relationship Diagram (Conceptual)
```
┌─────────────┐     ┌─────────────────┐     ┌───────────────────┐
│   disease   │────<│  disease_state  │────<│ markov_transition │
│  - id       │     │  - id           │     │  - model_id       │
│  - name     │     │  - disease_id   │     │  - from_state_id  │
│  - desc     │     │  - state_name   │     │  - to_state_id    │
│             │     │  - severity_lvl │     │  - probability    │
└─────────────┘     └─────────────────┘     └───────────────────┘
│                    │                                  │
│                    │                                  │
▼                    ▼                                  │
┌─────────────┐     ┌─────────────────┐                 │
│   action    │────<│  action_utility │                 │
│  - id       │     │  - disease_id   │                 │
│  - disease_id│    │  - state_id     │                 │
│  - name     │     │  - action_id    │                 │
│  - desc     │     │  - benefit      │                 │
│  - improve  │     │  - risk         │                 │
│  - worsen   │     │  - cost         │                 │
│  - delta    │     └─────────────────┘                 │
└─────────────┘                                         │
│                                                       │
┌──────────────┐       ┌─────────────────────┐          │
│   patient    │──────<│  patient_status     │ ─────────┘
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
│    users          │
│  - id             │
│  - username       │
│  - hashed_password|
│  - salt           │
└───────────────────┘
```
## Table Definitions

### `disease`

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER | Primary key, auto‑increment |
| `name` | TEXT | Unique disease name (e.g., "Type 2 Diabetes") |
| `description` | TEXT | Human‑readable description |

**Foreign Keys:** None

**Used by queries:** `get_all_patients()`, `get_state_distribution()`, `seed_data()`

---

### `disease_state`

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER | Primary key, auto‑increment |
| `disease_id` | INTEGER | Foreign key → `disease(id)` |
| `state_name` | TEXT | e.g., "Normal", "Mild", "Severe" |
| `severity_level` | INTEGER | 1–5 (1 = best, 5 = worst) |

**Foreign Keys:** `disease_id` → `disease(id)`

**Used by queries:** `get_state_distribution()`, `get_model_for_patient()`, `seed_data()`

---

### `markov_model`

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER | Primary key, auto‑increment |
| `disease_id` | INTEGER | Foreign key → `disease(id)` |
| `model_name` | TEXT | Human‑readable name |
| `version` | TEXT | Version string (e.g., "1.0.0") |
| `is_active` | BOOLEAN | 1 if this is the current version, else 0 |

**Foreign Keys:** `disease_id` → `disease(id)`

**Used by queries:** `get_model_for_patient()`, `seed_data()`

---

### `markov_transition`

| Column | Type | Description |
|--------|------|-------------|
| `model_id` | INTEGER | Foreign key → `markov_model(id)` |
| `from_state_id` | INTEGER | Foreign key → `disease_state(id)` |
| `to_state_id` | INTEGER | Foreign key → `disease_state(id)` |
| `probability` | REAL | Transition probability (0–1) |

**Primary Key:** `(model_id, from_state_id, to_state_id)`

**Constraints:** For each `(model_id, from_state_id)`, probabilities must sum to 1.0

**Used by queries:** `get_model_for_patient()`, `seed_data()`

---

### `action`

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER | Primary key, auto‑increment |
| `disease_id` | INTEGER | Foreign key → `disease(id)` |
| `action_name` | TEXT | e.g., "Prescribe Metformin" |
| `description` | TEXT | Human‑readable description |
| `improve_state` | TEXT | State to shift probability toward (or NULL) |
| `worsen_state` | TEXT | State to shift probability away from (or NULL) |
| `delta` | REAL | Amount of probability to move (0–1) |

**Foreign Keys:** `disease_id` → `disease(id)`

**Used by queries:** `get_actions_for_patient()`, `get_action_utility_comparison()`, `seed_data()`

---

### `action_utility`

| Column | Type | Description |
|--------|------|-------------|
| `disease_id` | INTEGER | Foreign key → `disease(id)` |
| `state_id` | INTEGER | Foreign key → `disease_state(id)` |
| `action_id` | INTEGER | Foreign key → `action(id)` |
| `expected_benefit` | REAL | Clinical benefit (0–1, higher = better) |
| `complication_risk` | REAL | Risk of complications (0–1, higher = worse) |
| `side_effect_cost` | REAL | Side effect burden (0–1, higher = worse) |

**Primary Key:** `(disease_id, state_id, action_id)`

**Note:** Net utility = `expected_benefit - complication_risk - side_effect_cost`

**Used by queries:** `get_actions_for_patient()`, `get_action_utility_comparison()`, `get_benefit_risk_for_patient()`, `seed_data()`

---

### `patient`

| Column | Type | Description |
|--------|------|-------------|
| `id` | TEXT | Primary key (e.g., "P001") |
| `first_name` | TEXT | Patient's first name |
| `last_name` | TEXT | Patient's last name |

**Foreign Keys:** None

**Used by queries:** `get_all_patients()`, `get_audit_log()`, `seed_data()`

---

### `patient_status`

| Column | Type | Description |
|--------|------|-------------|
| `patient_id` | TEXT | Primary key, foreign key → `patient(id)` |
| `disease_id` | INTEGER | Foreign key → `disease(id)` |
| `current_state_id` | INTEGER | Foreign key → `disease_state(id)` |
| `active_model_id` | INTEGER | Foreign key → `markov_model(id)` |

**Foreign Keys:**
- `patient_id` → `patient(id)`
- `disease_id` → `disease(id)`
- `current_state_id` → `disease_state(id)`
- `active_model_id` → `markov_model(id)`

**Used by queries:** `get_all_patients()`, `get_model_for_patient()`, `get_actions_for_patient()`, `get_state_distribution()`, `get_benefit_risk_for_patient()`, `seed_data()`

---

### `recommendation_run`

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER | Primary key, auto‑increment |
| `patient_id` | TEXT | Foreign key → `patient(id)` |
| `recommended_action` | TEXT | Name of action the engine recommended |
| `recommended_score` | REAL | Total score of recommended action |
| `clinician_decision` | TEXT | One of: 'accept', 'reject', 'override' |
| `override_action` | TEXT | If 'override', the action chosen instead |
| `timestamp` | TIMESTAMP | Default CURRENT_TIMESTAMP |

**Foreign Keys:** `patient_id` → `patient(id)`

**Used by queries:** `get_audit_log()`, `log_clinician_decision()`

---

### `users`

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER | Primary key, auto‑increment |
| `username` | TEXT | Unique login username |
| `hashed_password` | TEXT | SHA256 of (salt + password) |
| `salt` | TEXT | Random salt for password hashing |

**Foreign Keys:** None

**Used by queries:** `get_user_by_username()`, `create_user()`

## Key Query Functions

| Function | Tables Used | Purpose |
|----------|-------------|---------|
| `get_all_patients()` | patient, patient_status, disease_state, disease | List patients with current state |
| `get_model_for_patient()` | patient_status, disease_state, markov_transition | Get transition matrix for a patient |
| `get_actions_for_patient()` | patient_status, action, action_utility | Get actions for current disease+state |
| `get_action_utility_comparison()` | action, action_utility | Avg benefit/risk/cost per action (global) |
| `get_state_distribution()` | disease, disease_state, patient_status | Patient counts per state per disease |
| `get_benefit_risk_for_patient()` | patient_status, action, action_utility | Data for scatter plot |
| `get_audit_log()` | recommendation_run, patient | Clinician decision history |
| `log_clinician_decision()` | recommendation_run | Insert a new decision record |

## Gaps vs Original Database Specification

The original Business Requirements Document specified several tables that were not implemented due to time constraints and project scope. This section is an honest acknowledgment of those gaps.

### Not Implemented Tables

| Table | Purpose | Reason Not Implemented |
|-------|---------|------------------------|
| `CLINICIAN` | Store clinician metadata (specialty, contact) | User authentication simplified to single `users` table; clinician‑specific fields not needed for demo |
| `ENCOUNTER` | Track patient visits | Not required for the MDP recommendation engine; state changes are modelled directly |
| `RECOMMENDATION_SCORE` | Store per‑action scores for each recommendation run | Merged into `recommendation_run` table (stores only top score, not all actions) |
| `ACTION_EFFECT` | Store per‑state, per‑action transition modifications | Merged into `action` table (improve_state, worsen_state, delta) |
| `MODEL_CALIBRATION_LOG` | Track model version updates | Calibration not implemented in current version |
| `MARKOV_MODEL.parent_model_id` | Support model versioning chain | Simplified – each model is independent; no parent tracking |

### Implemented Alternatives

| Original Requirement | Implemented Alternative |
|---------------------|------------------------|
| Full recommendation scoring per action | `recommendation_run` stores only the top recommendation (sufficient for audit logging) |
| Separate `CLINICIAN` table | `users` table with simplified authentication |
| `ENCOUNTER` tracking | State history stored in `MacroState.history` (domain object, not database) |
| Complex action effects | Simplified `improve_state`/`worsen_state`/`delta` model |

### Why These Gaps Are Acceptable

- The implemented schema supports **all core CDSS functionality**: patient management, Markov models, action utilities, and audit logging
- The missing tables are **orthogonal** to the MDP engine – they would not change how recommendations are computed
- `parent_model_id` and calibration logging are **future work** that would extend, not replace, the current schema
- The `MacroState.history` (domain object) provides a richer action history than a simple `ENCOUNTER` table could, because it stores the entire model state before and after each action
