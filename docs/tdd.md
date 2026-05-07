# Technical Design Document (TDD)
## Clinical Decision Support System (CDSS)

**Version:** 1.0  
**Date:** May 2026  
**Authors:** Eva, Sara, Stuti  

---

## 1. System Overview

### 1.1 Purpose of the System

The Clinical Decision Support System (CDSS) is a desktop-based application designed to assist General Practitioners in selecting treatment actions for patients with diseases that evolve probabilistically over time. The system is intended to demonstrate how formal decision-making methods—specifically Markov Decision Processes (MDPs)—can be applied to clinical scenarios.

The system models disease progression using a discrete-state Markov chain and evaluates treatment options using value iteration. The goal is to rank actions based on their expected long-term impact, rather than relying solely on immediate effects.

The CDSS is implemented as an academic prototype. It is not clinically validated and is not intended for real-world deployment.

---

### 1.2 Conceptual Model

Each patient is represented as a pair:

```
(P, s)
```

Where:
- `P` is a transition probability matrix describing disease progression  
- `s` is the current disease state  

The system assumes that:

- disease evolution is stochastic  
- treatment actions influence transition probabilities  
- future outcomes are discounted relative to immediate outcomes  

A treatment action `α` transforms the model:

```
P → P_α
```

This reflects a key modelling assumption:

> Treatments do not instantly change a patient’s state; they change the likelihood of future transitions.

---

### 1.3 Decision Process

For each available action:

1. The transition matrix is modified  
2. Value iteration is applied to compute long-term state values  
3. Expected future value is calculated  
4. Immediate utility is added  
5. A total score is produced  

The output presented to the clinician includes:

- ranked list of actions  
- explanation of each score (decision trace)  
- sensitivity panel for parameter exploration  
- audit log of clinician decisions  

---

### 1.4 Technology Stack

| Component | Technology | Rationale |
|----------|-----------|----------|
| Language | Python 3.10+ | Rapid development, strong ecosystem |
| GUI | PyQt5 | Mature desktop framework |
| Numerical | NumPy | Efficient matrix operations |
| Database | SQLite | Zero configuration, single-user |
| Visualisation | matplotlib | Embedded plotting |
| Authentication | hashlib + secrets | Simple and sufficient for prototype |

---

### 1.5 Intended Audience

This document is written for developers who will:

- extend the system  
- maintain the codebase  
- review the design  

It assumes familiarity with Python and basic algorithmic concepts, but not prior exposure to this system.

---

## 2. Codebase Structure

### 2.1 Overview

The system is organised into five layers, each with a clearly defined responsibility. This layered architecture enforces separation of concerns and ensures that changes in one layer do not propagate unnecessarily to others.

```
src/
├── domain/
├── decision_engine/
├── infrastructure/
├── analytics/
└── ui/
```

---

### 2.2 Layer Responsibilities

#### Domain Layer (`src/domain/`)

Defines core business entities:

- `DiseaseModel` – immutable Markov chain with validation  
- `Action` – treatment that modifies the model  
- `MacroState` – `(P, s)` with history  
- `Patient` – wraps macro-state  
- `PatientRecord` – aggregation for UI  

Key properties:
- immutable objects  
- no database access  
- no UI dependencies  

---

#### Decision Engine (`src/decision_engine/`)

Implements the MDP logic:

- value iteration  
- action evaluation  
- ranking  

Key constraints:
- operates only on domain objects  
- does not access database  
- does not interact with UI  

---

#### Infrastructure Layer (`src/infrastructure/`)

Responsible for:

- database access (`database.py`)  
- authentication (`auth_service.py`)  
- data loading (`patient_service.py`)  

Critical responsibility:

- converts database rows into domain objects  
- computes immediate utility  

---

#### Analytics Layer (`src/analytics/`)

Provides:

- aggregate statistics  
- comparison data  
- visualisation inputs  

Properties:
- read-only  
- stateless  
- no business logic  

---

#### Presentation Layer (`src/ui/`)

Implements UI components:

- MainWindow  
- PatientView  
- PatientManagementView  
- various widgets  

Responsibilities:
- user interaction  
- data presentation  
- orchestration  

---

### 2.3 Dependency Rules

The system enforces strict dependency direction:

- Domain → no dependencies  
- Engine → depends only on domain  
- Infrastructure → depends on domain  
- UI → depends on all layers  

This ensures:

- high testability  
- modularity  
- clear boundaries  

---

## 3. Interactions Between Components

### 3.1 Composition Root

All components are instantiated in `MainWindow`:

```python
self._engine = DecisionEngine()
self._patient_view = PatientView(engine=self._engine)
```

This enables dependency injection and avoids hidden dependencies.

---

### 3.2 Interaction Flow

The system follows structured interaction paths:

- UI → service layer → domain objects  
- UI → decision engine  
- UI → analytics queries  

The engine never directly accesses persistence or UI.

---

### 3.3 Navigation Design

PatientView is not directly navigable:

```python
self._sidebar.set_active(1)
self._stack.setCurrentIndex(5)
```

This ensures:
- patient must be selected first  
- navigation context remains consistent  

---

## 4. Algorithms and Decision Logic

### 4.1 Markov Decision Process

The system models decision-making as an MDP:

```
(S, A, P, R, γ)
```

Where:
- `S` = states  
- `A` = actions  
- `P` = transition probabilities  
- `R` = reward function  
- `γ` = discount factor  

---

### 4.2 Bellman Equation

```
V(s) = max_a [ r(s,a) + γ Σ P(s'|s,a) V(s') ]
```

This defines the optimal value of a state under optimal decisions.

---

### 4.3 Value Iteration

Value iteration computes `V(s)` iteratively until convergence:

- initialise all values to 0  
- repeatedly update values  
- stop when change < threshold  

Properties:
- deterministic  
- guaranteed to converge (under assumptions)  

---

### 4.4 Per-Action Evaluation

Each action produces a different transition model:

```
P → P_α
```

Therefore:

```
V(P_α₁) ≠ V(P_α₂)
```

The system correctly recomputes value iteration per action.

---

### 4.5 Immediate Utility

```
benefit − risk − cost
```

Important:

- computed in infrastructure layer  
- not computed by engine  
- stored in Action object  

---

### 4.6 Risk Scoring

Risk is derived from state ordering:

- assumes states ordered by severity  
- uses index-based weighting  

This is a simplification.

---

## 5. Data Flow

### 5.1 Startup

- database initialised  
- seed data inserted if empty  
- login view displayed  

---

### 5.2 Login

- credentials validated  
- salted SHA-256 used  
- boolean result returned  

---

### 5.3 Patient Selection Flow

1. patient selected  
2. signal emitted  
3. PatientView loads data  
4. engine computes rankings  
5. UI updates  

---

### 5.4 Recommendation Flow

1. macro-state passed to engine  
2. actions evaluated  
3. scores computed  
4. sorted results returned  

---

### 5.5 Decision Logging

```
INSERT INTO recommendation_run
```

Only persisted workflow during runtime.

---

### 5.6 In-Memory Updates

- Apply Action modifies model  
- Simulate modifies state  
- changes not persisted  

Implication:
- state resets on restart  

---

## 6. Design Decisions and Assumptions

### 6.1 Architectural Decisions

- layered architecture  
- immutable domain  
- per-action evaluation  

---

### 6.2 Technology Decisions

- SQLite for simplicity  
- PyQt5 for desktop  
- NumPy for performance  

---

### 6.3 Modelling Assumptions

- state order reflects severity  
- single disease per patient  
- fixed γ = 0.9  
- no concurrency  
- infinite horizon  

---

## 7. Limitations and Future Work

### 7.1 Persistence Gaps

- Apply Action not persisted  
- Simulate not persisted  

---

### 7.2 Engine Limitations

- no learning  
- fixed discount factor  
- no uncertainty modelling  

---

### 7.3 Code Limitations

- large UI file  
- partial refactor needs  

---

### 7.4 Missing Features

- role-based access  
- multi-disease support  
- web interface  

---

### 7.5 Recommended Priorities

1. persist simulation  
2. improve risk scoring  
3. refactor UI  
4. remove unused dependencies  
5. add learning  
