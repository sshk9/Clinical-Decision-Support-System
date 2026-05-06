# System Architecture – CDSS

## Overview

The Clinical Decision Support System (CDSS) follows a clean layered architecture. This design enforces Separation of Concerns, High Cohesion, and Low Coupling — ensuring that no UI code exists inside the decision engine, and no database logic lives inside domain objects.

## High-Level Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           PRESENTATION LAYER                                │
│  ┌──────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────┐ ┌───────────┐  │
│  │MainWindow│ │ PatientView  │ │ComparisonWid.│ │TrendWid. │ │AuditWid.  │  │
│  │Sidebar   │ │LoginView     │ │RiskBenefitPlot│ │Dashboard│ │Sensitivity│  │
│  └──────────┘ └──────────────┘ └──────────────┘ └──────────┘ └───────────┘  │
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
│  ┌────────────┐ ┌────────────┐ ┌──────────────┐ ┌────────────┐ ┌─────────┐  │
│  │DiseaseModel│ │   Action   │ │ MacroState   │ │  Patient   │ │History  │  │
│  │(Markov     │ │            │ │ (P, s)       │ │            │ │Step     │  │
│  │ Chain)     │ │            │ │              │ │            │ │         │  │
│  └────────────┘ └────────────┘ └──────────────┘ └────────────┘ └─────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      │ Queries / Updates
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          INFRASTRUCTURE LAYER                               │
│  ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌───────────┐  │
│  │ database.py│ │auth_service│ │patient_    │ │ SQLite     │ │   CSV     │  │
│  │(queries)   │ │ (login)    │ │service.py  │ │ cdss.db    │ │ exports   │  │
│  └────────────┘ └────────────┘ └────────────┘ └────────────┘ └───────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Note on PatientView:** PatientView is not directly accessible via the sidebar. It is only shown when a patient is selected from PatientManagementView and is rendered at a non-navigable stack index.

**Note on `analytics.py`:** Analytics functions (`compare_actions`, `state_success_rate`) are located in `src/analytics/analytics.py` — a separate module for pure computation.

---

## Layer Descriptions

### Presentation Layer (`src/ui/`)

**Purpose:** Handles user interaction and visualisation.

**Key Components:**
- `main_window.py`
- `login_view.py`
- `patient_view.py`
- `comparison_widget.py`
- `trend_widget.py`
- `audit_widget.py`
- `risk_benefit_plot.py`
- `sensitivity_panel.py`

**Key Design Principles:**
- No business logic
- Most data flows through service layer
- Analytics widgets may perform read-only database queries directly
- Communication via signals/slots

---

### Application Layer (`src/infrastructure/patient_service.py`)

**Purpose:** Coordinates loading of domain objects.

**Key Function:**
- `load_patients_with_actions()`

Ensures UI does not directly depend on raw database structures.

---

### Decision Engine Layer (`src/decision_engine/`)

**Purpose:** Implements Markov Decision Process logic.

**Key Elements:**
- `DecisionEngine`
- `ActionScore`

**Core Equation:**
```
V(P, s) = max_α [ r(P, s, α) + γ * Σ_s' P_α(s'|s) * V(P_α, s') ]
```

**Important:**
- Immediate utility (`benefit − risk − cost`) is computed in the infrastructure layer and passed into the engine.
- Engine operates purely on domain objects.

---

### Domain Layer (`src/domain/`)

**Purpose:** Encapsulates business logic.

**Key Classes:**
- `DiseaseModel`
- `Action`
- `MacroState`
- `Patient`
- `PatientRecord`

**Design Principles:**
- Immutable data structures
- No external dependencies
- No database awareness

---

### Infrastructure Layer (`src/infrastructure/`)

**Purpose:** Handles database and external concerns.

**Components:**
- `database.py`
- `auth_service.py`
- `patient_service.py`

**Responsibilities:**
- Query execution
- Data conversion to domain objects
- Authentication

---

## Data Flow – Recommendation Process

1. User logs in via `LoginView`
2. Patient selected → signal emitted
3. `MainWindow` loads patient into `PatientView`
4. `PatientView._refresh()` calls:
   ```
   DecisionEngine.rank_actions(macro_state, actions)
   ```
5. Engine:
   - Applies each action
   - Runs value iteration
   - Computes scores
6. UI displays:
   - ranked actions
   - risk score
   - decision trace
7. User interactions:
   - Accept / Reject / Override → persisted
   - Apply Action / Simulate → in-memory only

**Important:**
Apply Action and Simulate Progression modify only in-memory state. These changes are not persisted and are lost when the application closes.

---

## Why This Architecture

| Benefit | Explanation |
|--------|------------|
| Testability | Engine and domain are independent |
| Maintainability | UI and DB changes are isolated |
| Extensibility | Easy to add new interfaces |
| Transparency | Decision trace explains outputs |

---

## Folder Structure

```
Clinical-Decision-Support-System/
├── main.py
├── requirements.txt
├── cdss.db
├── docs/
├── src/
│   ├── __init__.py
│   ├── ui/
│   ├── decision_engine/
│   ├── domain/
│   ├── infrastructure/
│   └── analytics/
└── tests/
```