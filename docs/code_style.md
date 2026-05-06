# Code Style Guidelines – CDSS Project

## Overview

This document defines the coding conventions and standards used throughout the Clinical Decision Support System (CDSS) project. Following these guidelines ensures consistency, maintainability, and readability across the codebase.

These guidelines describe both the preferred coding style and the current state of the project. Where the current implementation does not fully follow a guideline, the gap is documented as a future refactor rather than hidden.

---

## Naming Conventions

| Element | Style | Example |
|---------|-------|---------|
| Classes | PascalCase | `PatientView`, `DecisionEngine`, `ActionScore` |
| Functions | snake_case | `get_all_patients()`, `rank_actions()` |
| Variables | snake_case | `patient_id`, `transition_matrix` |
| Constants | UPPER_SNAKE_CASE | `SIDEBAR_BG`, `ACCENT`, `THRESHOLD_SAFE` |
| Private methods/functions | `_` prefix + snake_case | `_update_trace()`, `_value_iteration()` |
| Internal attributes | `_` prefix + snake_case | `_patient`, `_current_scores` |
| Module-level helpers | `_` prefix + snake_case | `_card()`, `_label()` |

---

## File Organization

### Preferred Rule: One Main Class Per File

The preferred structure is one main class per file, especially for domain, engine, infrastructure, and analytics code.

Current exception:

- `main_window.py` currently contains multiple UI classes, including `MainWindow`, `PatientView`, `PatientManagementView`, `DashboardView`, and `Sidebar`.

This is acceptable for the current prototype but is a known maintainability issue. A future refactor should split these UI classes into separate files.

Small tightly related helper classes may remain in the same file, for example:

- `ActionScore` in `engine.py`
- small UI helper functions such as `_card()` and `_label()`

---

## Import Order

Imports should be grouped in this order:

```python
# 1. Standard library imports
from __future__ import annotations
import csv
from datetime import datetime
from typing import Dict, List, Optional

# 2. Third-party imports
import numpy as np
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QWidget, QVBoxLayout

# 3. Internal project imports
from ..domain.patient import Patient
from ..domain.action import Action
from ..decision_engine.engine import DecisionEngine
```

Rules:
- Use one blank line between groups
- Keep imports alphabetised within each group where practical
- Avoid unused imports

---

## Function Length

Preferred rule:

- Non-UI functions should generally stay below 50 lines
- Complex functions should be split into smaller helpers

Exception:

- UI layout/build methods may exceed 50 lines when they are mostly declarative widget construction

Current known issue:

- `PatientView._refresh()` is currently a monolithic method of roughly 70 lines.
- It is not currently split into `_update_ranked_table()`, `_update_risk_display()`, or `_update_history_table()`.
- This is acceptable for the current prototype but should be treated as a refactor candidate.

Recommended future refactor:

```python
def _refresh(self) -> None:
    self._update_header()
    self._update_ranked_table()
    self._update_risk_display()
    self._update_history_panel()
    self._update_transition_panel()
```

The goal is not to split code mechanically, but to separate different UI update responsibilities when doing so improves readability.

---

## Docstrings

Public classes and public functions should have concise docstrings.

### Class example

```python
class DecisionEngine:
    """
    Computes and ranks actions for a given macro-state using value iteration.
    Implements the Bellman optimality equation for Markov Decision Processes.
    """
```

### Function example

```python
def get_audit_log(patient_id: str | None = None):
    """
    Fetch audit log entries from recommendation_run.

    Args:
        patient_id: Optional patient ID filter.

    Returns:
        Audit log rows ordered by timestamp descending.
    """
```

### Simple function example

```python
def get_connection():
    """Return a database connection to cdss.db."""
```

---

## Comments

### Section Dividers

For long files such as `main_window.py`, use section dividers to separate logical areas:

```python
# ---------------------------------------------------------------------------
# Patient view — ranked actions + history
# ---------------------------------------------------------------------------
```

### Inline Comments

Comments should explain why something is done, not simply repeat what the code does.

```python
# Good — explains why
move = min(delta, P[i, worsen_idx])  # Prevent negative probabilities

# Bad — repeats the code
move = min(delta, P[i, worsen_idx])  # Take the minimum of delta and matrix value
```

---

## Error Handling

Database operations and file I/O should handle exceptions explicitly.

```python
try:
    with get_connection() as conn:
        cursor = conn.execute("...")
        return cursor.fetchall()
except sqlite3.OperationalError as e:
    print(f"Database error: {e}")
    return []
```

Rules:
- Do not silently swallow exceptions
- At minimum, print or log the error
- Return a safe fallback only when appropriate

---

## Type Hints

Function signatures should include type hints where practical.

```python
def load_patient(self, patient: Patient, actions: list[Action]) -> None:
    ...

def _update_trace(self) -> None:
    ...
```

For complex types, use standard typing tools when needed:

```python
from typing import Dict, List, Optional, Tuple
```

---

## Indentation and Spacing

- Indentation: 4 spaces
- No tabs
- Two blank lines between top-level classes/functions
- One blank line between methods in a class
- Line length: maximum 120 characters where practical

---

## Example – Well-Formatted Database Function

```python
def get_benefit_risk_for_patient(patient_id: str) -> list[tuple]:
    """
    Return benefit, risk, and cost values for available actions
    for the patient's current disease and state.
    """
    try:
        with get_connection() as conn:
            cursor = conn.execute("""
                SELECT
                    a.action_name,
                    au.expected_benefit,
                    au.complication_risk,
                    au.side_effect_cost
                FROM patient_status ps
                JOIN action a ON a.disease_id = ps.disease_id
                JOIN action_utility au
                    ON a.id = au.action_id
                    AND au.state_id = ps.current_state_id
                WHERE ps.patient_id = ?
                ORDER BY a.action_name
            """, (patient_id,))
            return cursor.fetchall()
    except sqlite3.OperationalError as e:
        print(f"Error fetching benefit/risk for patient {patient_id}: {e}")
        return []
```

---

## Exceptions to Rules

| Rule | Exception | Justification |
|------|-----------|---------------|
| One class per file | `main_window.py` currently contains multiple UI classes | Accepted for prototype; should be refactored later |
| 50-line limit | UI layout/build methods | Declarative UI layout can be clearer when kept together |
| 50-line limit | `PatientView._refresh()` currently exceeds the guideline | Known refactor candidate |
| One class per file | `ActionScore` in `engine.py` | Closely tied to `DecisionEngine` |
| No public access to widget internals | `Sidebar.set_active(idx)` is exposed intentionally | Provides a controlled public interface instead of direct internal access |

---

## Current Refactor TODOs

The following code-style issues are known and should be addressed in future work:

1. Split `main_window.py` into separate UI modules.
2. Break `PatientView._refresh()` into smaller helper methods.
3. Remove unused dependencies from `requirements.txt`.
4. Decide whether `_build_explanation()` should be displayed in the UI or removed.
5. Keep documentation aligned with actual code structure.

---

## Enforcement

These guidelines are enforced through review rather than automated tooling.

Future improvements could include:
- `ruff` for linting
- `black` for formatting
- `mypy` for optional type checking
- `pytest` for regression testing