# Technical Design Document (TDD)
## Clinical Decision Support System (CDSS)

**Version:** 1.0  
**Date:** May 2026  
**Authors:** Eva, Sara, Stuti  

---

## 1. System Overview

### What this system is

The Clinical Decision Support System (CDSS) is a desktop application that assists General Practitioners in selecting treatment actions for patients with diseases that evolve non-deterministically over time. It models disease progression as a Markov chain, evaluates available treatment actions using value iteration, and presents a ranked list of recommendations together with a transparent explanation of how each ranking was derived.

The system is a prototype developed for academic purposes and is not validated for real clinical use.

---

### How it works at a high level

A patient is represented as a pair `(P, s)`:
- `P` — a Markov chain describing disease progression  
- `s` — the patient’s current disease state  

A treatment action `α` modifies the transition model (`P → P_α`) rather than the patient’s current state. The decision engine evaluates each action by computing long-term value using value iteration, balancing immediate utility with discounted future outcomes.

The clinician is presented with:
- ranked treatment options  
- decision trace  
- sensitivity panel  
- audit log  

---

### Technology stack

- Python 3.10+  
- PyQt5  
- NumPy  
- SQLite  
- matplotlib  
- hashlib + secrets  

---

### Audience

Developers extending or maintaining the system. Assumes knowledge of Python and Markov Decision Processes.

---

### Document Structure

- Section 2 — Codebase structure  
- Section 3 — Component interactions  
- Section 4 — Algorithms  
- Section 5 — Data flow  
- Section 6 — Design decisions  
- Section 7 — Limitations  

---

## 2. Codebase Structure

### 2.1 Top-Level Layout

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

| Layer | Responsibility |
|------|----------------|
| Domain | Business objects |
| Engine | Decision logic |
| Infrastructure | DB + services |
| Analytics | Aggregations |
| UI | Presentation |

---

### 2.3 Key Design Rules

- One-way dependencies  
- Domain is pure  
- Engine depends only on domain  
- UI orchestrates  

---

## 3. Interactions Between Components

### 3.1 Composition Root

```python
self._engine = DecisionEngine()
self._patient_view = PatientView(engine=self._engine)
```

---

### 3.2 Cross-Layer Communication

- UI → Service → Domain  
- UI → Engine  
- UI → DB (analytics only)

---

### 3.3 Sidebar Navigation (Final Design)

PatientView is **not directly accessible via navigation**.

```python
self._sidebar.set_active(1)        # Patient Management
self._stack.setCurrentIndex(5)     # PatientView
```

This preserves context while showing detailed patient view.

---

## 4. Key Algorithms and Decision Logic

### 4.1 Value Iteration

```
V(s) = max_a [ r(s,a) + γ Σ P(s'|s,a) V(s') ]
```

---

### 4.2 Action Evaluation

Each action:
1. modifies transition matrix  
2. runs value iteration  
3. computes total score  

---

### 4.3 Immediate Utility

Computed in infrastructure:

```
benefit − risk − cost
```

---

### 4.4 Risk Scoring

Based on state index ordering.

---

## 5. Data Flow Within the System

### 5.1 Startup

- initialise DB  
- seed conditionally  
- show login  

---

### 5.2 Login

- salted SHA-256  
- boolean auth  

---

### 5.3 Patient Selection

- signal emitted  
- engine runs  
- UI updates  

---

### 5.4 Decision Logging

ONLY persistence path:

```
INSERT INTO recommendation_run
```

---

### 5.5 In-Memory Updates

- Apply Action → modifies model  
- Simulate → modifies state  
- NOT persisted  

---

## 6. Design Decisions and Assumptions

### 6.1 Technology

- SQLite → simplicity  
- PyQt5 → desktop  
- NumPy → performance  

---

### 6.2 Architecture

- layered design  
- immutable domain  
- per-action value iteration  

---

### 6.3 Assumptions

- ordered states = severity  
- single disease  
- γ = 0.9  
- no concurrency  

---

## 7. Known Limitations and Future Work

### 7.1 Persistence Gaps

- Apply Action not persisted  
- Simulate not persisted  

---

### 7.2 Engine Limitations

- fixed γ  
- no learning  
- no uncertainty  

---

### 7.3 Code Quality

- large UI file  
- unused code  

---

### 7.4 Missing Features

- role-based access  
- comorbidity  
- web interface  

---

### 7.5 Recommended Priorities

1. Persist simulation  
2. Improve risk scoring  
3. Clean dependencies  
4. Refactor UI  
5. Add learning  
