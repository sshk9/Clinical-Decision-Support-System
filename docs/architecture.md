# System Architecture – CDSS

## Overview

The Clinical Decision Support System (CDSS) follows a **clean layered architecture** (also known as Hexagonal or Onion architecture). This design enforces **Separation of Concerns**, **High Cohesion**, and **Low Coupling** – ensuring that no UI code exists inside the decision engine, and no database logic lives inside domain objects.

## High-Level Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           PRESENTATION LAYER                                │
│  ┌──────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────┐ ┌───────────┐ │
│  │MainWindow│ │ PatientView  │ │ComparisonWid.│ │TrendWid. │ │AuditWid.  │ │
│  │Sidebar   │ │LoginView     │ │RiskBenefitPlot│ │Dashboard│ │Sensitivity│ │
│  └──────────┘ └──────────────┘ └──────────────┘ └──────────┘ └───────────┘ │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      │ Signals / Slots / Method calls
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         APPLICATION / ORCHESTRATION                         │
│                            patient_service.py                               │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           DECISION ENGINE LAYER                             │
│                              engine.py                                      │
│                         (Markov Decision Process)                           │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                             DOMAIN MODEL LAYER                              │
│  ┌────────────┐ ┌────────────┐ ┌──────────────┐ ┌────────────┐ ┌─────────┐ │
│  │DiseaseModel│ │   Action   │ │ MacroState   │ │  Patient   │ │History  │ │
│  │(Markov     │ │            │ │ (P, s)       │ │            │ │Step     │ │
│  │ Chain)     │ │            │ │              │ │            │ │         │ │
│  └────────────┘ └────────────┘ └──────────────┘ └────────────┘ └─────────┘ │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      │ Queries / Updates
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          INFRASTRUCTURE LAYER                               │
│  ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌───────────┐ │
│  │ database.py│ │auth_service│ │patient_    │ │ SQLite     │ │   CSV     │ │
│  │(queries)   │ │ (login)    │ │service.py  │ │ cdss.db    │ │ exports   │ │
│  └────────────┘ └────────────┘ └────────────┘ └────────────┘ └───────────┘ │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Note on `analytics.py`:** Analytics functions (`compare_actions`, `state_success_rate`) are located in `src/analytics/analytics.py` – a separate module for pure computation. There is no duplicate `analytics.py` in `src/infrastructure/`.

## Layer Descriptions

### Presentation Layer (`src/ui/`)

**Purpose:** Handles all user interaction, visualisation, and input collection.

**Contents:**
- `main_window.py` – main application shell with sidebar and stacked views
- `login_view.py` – authentication dialog
- `patient_view.py` – main clinical interface (state, actions, trace, sensitivity)
- `comparison_widget.py` – side‑by‑side patient comparison
- `trend_widget.py` – population health analytics
- `audit_widget.py` – clinician decision log viewer
- `risk_benefit_plot.py` – matplotlib scatter plot for action analysis
- `sensitivity_panel.py` – what‑if controls for gamma and risk tolerance

**Key Design Principles:**
- No business logic – UI only formats and displays data
- No database queries – all data comes via service functions
- Communication via signals/slots and method calls to lower layers

### Application/Orchestration Layer (`src/infrastructure/patient_service.py`)

**Purpose:** Coordinates the loading of domain objects from the database.

**Contents:**
- `load_patients_with_actions()` – calls database functions, constructs domain objects, returns `PatientRecord` objects

This layer ensures the UI never calls database queries directly.

### Decision Engine Layer (`src/decision_engine/`)

**Purpose:** Implements the Markov Decision Process (MDP) that powers clinical recommendations.

**Contents:**
- `engine.py` – `DecisionEngine` class with value iteration, action ranking
- `ActionScore` dataclass – stores evaluation results including `future_outcomes` for the trace panel

**Key Algorithm – Value Iteration:**
V(P, s) = max_α [ r(P, s, α) + γ * Σ_s' P_α(s'|s) * V(P_α, s') ]
- `r(P, s, α)` – immediate utility (benefit - risk - cost)
- `γ` – discount factor (default 0.9)
- `P_α` – model after applying action α
- `V(P_α, s')` – value of future state under modified model

**Design Principle:** The engine receives pure domain objects and returns pure domain objects. It knows nothing about databases, UI, or file systems.

### Domain Model Layer (`src/domain/`)

**Purpose:** Pure business logic and data structures that represent the clinical domain.

**Contents:**
- `disease_model.py` – Markov chain (states + transition probabilities)
- `action.py` – treatment action with effect on transitions (improve_state, worsen_state, delta)
- `macro_state.py` – **(P, s)** current model + current state, immutable, stores full history
- `patient.py` – patient ID, name, disease name, macro_state (immutable)
- `patient_record.py` – wrapper for (Patient, actions) for the management view

**Key Design Principles:**
- **Immutability** – all domain classes are frozen dataclasses; every action creates a new object
- **No dependencies** – domain classes import nothing from outside `src/domain/`
- **No persistence logic** – no knowledge of SQLite or file storage

### Infrastructure Layer (`src/infrastructure/`)

**Purpose:** Handles all external concerns – database, authentication, file I/O.

**Contents:**
- `database.py` – SQLite connection, table creation, all query functions, seeding, `log_clinician_decision`
- `auth_service.py` – password hashing (SHA256 with salt), credential verification
- `patient_service.py` – orchestrates loading of domain objects from database

**Note on Analytics:** The `src/analytics/analytics.py` module (separate from infrastructure) contains pure computation functions (`compare_actions`, `state_success_rate`). These are not infrastructure concerns, so they live in their own module.

## Data Flow – How a Recommendation Is Made

1. **User logs in** → `LoginView` authenticates via `auth_service`
2. **Patient selected** → `PatientManagementView` emits `patient_selected` signal
3. **MainWindow** calls `PatientView.load_patient(patient, actions)`
4. **PatientView._refresh()** calls:
   - `DecisionEngine.rank_actions(macro_state, actions)`
     - For each action α:
       - Apply α → modified model P_α
       - Value iteration on P_α → V(P_α, *)
       - For current state s:
         - Immediate utility r(P,s,α)
         - Future value = γ * Σ P_α(s'|s) V(P_α, s')
       - Return ActionScore
     - Return list sorted by total_score (best first)
5. **PatientView** populates:
   - Ranked actions table (Action, Immediate, Long‑term, Total)
   - Risk score / progress bar (from top action)
   - Explanation box (from top action)
   - Action history table (from macro_state.history)
6. **User clicks an action row** → `_update_trace()`:
   - Populates trace_tree with Bellman decomposition
   - Sets sensitivity_panel with current score
7. **User clicks Accept/Reject/Override** → `log_clinician_decision()`
8. **User clicks Apply Action** → `macro_state.apply_action(action)` → new immutable MacroState
9. **User clicks Simulate Progression** → `macro_state.simulate_step()` → random next state

## Why This Architecture

| Benefit | How It's Achieved |
|---------|-------------------|
| **Testability** | Domain and engine have no external dependencies – can be unit tested in isolation |
| **Maintainability** | Changes to UI or database don't ripple into clinical logic |
| **Extensibility** | New features (web API, different UI frameworks) can be added without rewriting core logic |
| **Transparency** | The decision trace tree shows clinicians exactly how the engine arrived at a recommendation |

## Folder Structure
Clinical-Decision-Support-System/
├── main.py                          # Application entry point
├── requirements.txt                 # Python dependencies
├── cdss.db                          # SQLite database (auto-generated)
├── README.md                        # Project documentation
├── docs/                            # Documentation
│   ├── code_style.md
│   ├── architecture.md
│   ├── database_schema.md
│   └── decision_engine.md
├── src/
│   ├── init.py
│   ├── ui/                          # Presentation layer
│   │   ├── main_window.py
│   │   ├── login_view.py
│   │   ├── add_patient_dialog.py
│   │   ├── comparison_widget.py
│   │   ├── trend_widget.py
│   │   ├── audit_widget.py
│   │   ├── risk_benefit_plot.py
│   │   └── sensitivity_panel.py
│   ├── decision_engine/    # Decision engine layer
│   │   └── engine.py
│   ├── domain/                      # Domain model layer
│   │   ├── disease_model.py
│   │   ├── action.py
│   │   ├── macro_state.py
│   │   ├── patient.py
│   │   └── patient_record.py
│   ├── infrastructure/              # Infrastructure layer
│   │   ├── database.py
│   │   ├── auth_service.py
│   │   └── patient_service.py
│   └── analytics/                   # Pure analytics (not infrastructure)
│       └── analytics.py
└── tests/                           # Unit tests
└── test_basic.py
