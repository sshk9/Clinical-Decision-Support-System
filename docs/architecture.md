# System Architecture – CDSS

## Overview

The Clinical Decision Support System (CDSS) follows a layered architecture organised around Separation of Concerns, High Cohesion, and Low Coupling. The decision engine contains no UI code, domain objects contain no database access, and the UI communicates with persistence only through an application service layer.

## High-Level Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          PRESENTATION (src/ui/)                             │
│                                                                             │
│  main_window.py    ui_helpers.py                                            │
│  views/      Dashboard, PatientManagement, Patient, Analytics,              │
│              Trends, Audit, Login                                           │
│  widgets/    Sidebar, SensitivityAnalysisPanel                              │
│  charts/     RiskBenefitPlot                                                │
│  dialogs/    AddPatient, Login, etc.                                        │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      │ signals / slots / method calls
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                      APPLICATION (src/application/)                         │
│                                                                             │
│  audit_service.py             trend_service.py                              │
│  comparison_service.py        patient_management_service.py                 │
│  dashboard_service.py         decision_audit_service.py                     │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    DECISION ENGINE (src/decision_engine/)                   │
│                                                                             │
│             engine.py  →  DecisionEngine, ActionScore                       │
│             (Markov Decision Process, value iteration)                      │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         DOMAIN (src/domain/)                                │
│                                                                             │
│  DiseaseModel   Action   MacroState   Patient   PatientRecord               │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      │ queries / updates
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    INFRASTRUCTURE (src/infrastructure/)                     │
│                                                                             │
│  database.py    auth_service.py    patient_service.py    SQLite (cdss.db)   │
└─────────────────────────────────────────────────────────────────────────────┘

Sibling module (pure computation, no layer position):

  ANALYTICS (src/analytics/)
  Pure calculation functions consumed by analytics and comparison views.
```

**Note on PatientView:** PatientView is not directly accessible via the sidebar. It is only shown when a patient is selected from PatientManagementView.

**Note on `analytics/`:** The analytics module is a sibling utility — not part of the main request-response data flow. Its functions (`compare_actions`, `state_success_rate`, etc.) are called directly by UI widgets that need population-level statistics.

---

## Layer Descriptions

### Presentation Layer (`src/ui/`)

**Purpose:** Handles user interaction and visualisation.

**Structure:**
- `main_window.py` — application shell and navigation between screens
- `ui_helpers.py` — shared colours, labels, cards, and helper widgets
- `views/` — full application screens (Dashboard, PatientManagement, PatientView, AnalyticsView, TrendView, AuditView, LoginView)
- `widgets/` — reusable UI components (Sidebar, SensitivityAnalysisPanel)
- `charts/` — visualisation components (RiskBenefitPlot)
- `dialogs/` — pop-up dialogs (AddPatient, Login)

**Key Design Principles:**
- No business logic in UI files
- Data access goes through the application service layer
- Decision logic is delegated to the decision engine
- Communication via Qt signals and slots

---

### Application Layer (`src/application/`)

**Purpose:** Coordinates the UI's data needs and hides direct database calls.

**Services:**
- `dashboard_service.py` — dashboard statistics
- `patient_management_service.py` — patient listing, search, add
- `decision_audit_service.py` — clinician decision logging
- `audit_service.py` — audit log retrieval
- `trend_service.py` — population trend statistics
- `comparison_service.py` — patient comparison and action analytics

**Why this layer exists:**
Before this refactor, UI views called `database.py` directly. The service layer means UI views never depend on SQL or schema details — they call domain-shaped service functions instead.

---

### Decision Engine Layer (`src/decision_engine/`)

**Purpose:** Implements the Markov Decision Process logic and produces ranked recommendations.

**Components:**
- `DecisionEngine` — computes value iteration and ranks actions
- `ActionScore` — frozen dataclass holding the full result of evaluating one action

**Core Equation:**
```
V(P, s) = max_α [ r(P, s, α) + γ * Σ_s' P_α(s'|s) * V(P_α, s') ]
```

**Engine responsibilities (all delivered inside `ActionScore`):**
- Value iteration under each modified model `P_α`
- Immediate utility consumption (does not compute benefit − risk − cost itself)
- Risk score and risk level calculation
- Human-readable explanation generation
- Per-action ranking by total score

**Architectural constraints:**
- Operates only on domain objects (`MacroState`, `Action`, `DiseaseModel`)
- No database access
- No PyQt imports
- No coupling to persistence representations

**Important:** Immediate utility (`benefit − risk − cost`) is precomputed in the infrastructure layer when patient records are loaded. The engine consumes `action.immediate_utility` directly. This keeps the engine independent of how utility values are stored.

---

### Domain Layer (`src/domain/`)

**Purpose:** Encapsulates clinical and decision concepts as pure Python objects.

**Classes:**
- `DiseaseModel` — disease states and the transition probability matrix
- `Action` — treatment action with its application logic
- `MacroState` — patient macro-state `(P, s)` plus action history
- `Patient` — patient identity and current macro-state
- `PatientRecord` — patient record metadata used by management views

**Design Principles:**
- Immutable data structures where practical (frozen dataclasses)
- No external dependencies (no PyQt, no SQL)
- No knowledge of how data is loaded or displayed

---

### Infrastructure Layer (`src/infrastructure/`)

**Purpose:** Handles persistence, authentication, and the conversion of database rows into domain objects.

**Files:**
- `database.py` — schema setup, seeding, SQLite queries, and row-to-domain-object conversion (`load_disease_model`, `load_actions`)
- `patient_service.py` — orchestrates higher-level loading (`load_patients_with_actions`) using the lower-level functions from `database.py`
- `auth_service.py` — salted password hashing and credential verification

**Responsibilities:**
- Database schema initialisation
- Seed data on first run
- Authentication
- Row-to-domain-object conversion (the boundary that protects the engine from SQL)

---

## Data Flow – Recommendation Process

1. User logs in via `LoginView` (`auth_service.py`)
2. User opens Patient Management; a patient is selected → signal emitted
3. `MainWindow` loads the patient into `PatientView`
4. `PatientView._refresh()` calls:
   ```
   DecisionEngine.rank_actions(macro_state, actions)
   ```
5. Engine:
   - For each action, applies it to get the modified model `P_α`
   - Runs value iteration under `P_α`
   - Computes immediate utility, long-term value, risk score, risk level, explanation, and transition row
6. UI displays:
   - Ranked actions table
   - Risk score and risk level
   - Decision Trace for the selected action
   - Sensitivity Analysis (what-if exploration)
   - Risk-Benefit Plot
   - Transition Impact (after Apply Action)
7. Clinician decisions:
   - Accept / Reject / Override → persisted via `decision_audit_service.py`
   - Apply Action / Simulate Progression → in-memory only

**Important persistence note:** Apply Action and Simulate Progression update the in-memory `MacroState` only. These changes are not written back to `patient_status` and are lost on restart.

---

## Why This Architecture

| Benefit | Explanation |
|---------|-------------|
| Testability | The engine and domain are pure and testable without a database or UI |
| Maintainability | UI and persistence changes stay isolated within their layers |
| Extensibility | New views, services, or scoring rules can be added without cross-layer impact |
| Transparency | Decision Trace exposes the same intermediate values the engine used to rank |

---

## Folder Structure

```
Clinical-Decision-Support-System/
├── main.py
├── requirements.txt
├── cdss.db
├── README.md
├── .gitignore
├── docs/
│   ├── architecture.md
│   ├── code_style.md
│   ├── database_schema.md
│   ├── decision_engine.md
│   └── tdd.md
├── src/
│   ├── __init__.py
│   ├── analytics/
│   ├── application/
│   │   ├── __init__.py
│   │   ├── audit_service.py
│   │   ├── comparison_service.py
│   │   ├── dashboard_service.py
│   │   ├── decision_audit_service.py
│   │   ├── patient_management_service.py
│   │   └── trend_service.py
│   ├── decision_engine/
│   │   ├── __init__.py
│   │   └── engine.py
│   ├── domain/
│   │   ├── __init__.py
│   │   ├── action.py
│   │   ├── disease_model.py
│   │   ├── macro_state.py
│   │   ├── patient.py
│   │   └── patient_record.py
│   ├── infrastructure/
│   │   ├── __init__.py
│   │   ├── auth_service.py
│   │   ├── database.py
│   │   └── patient_service.py
│   └── ui/
│       ├── __init__.py
│       ├── main_window.py
│       ├── ui_helpers.py
│       ├── charts/
│       ├── dialogs/
│       ├── views/
│       └── widgets/
└── tests/
```
