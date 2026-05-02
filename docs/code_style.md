# Code Style Guidelines – CDSS Project

## Overview

This document defines the coding conventions and standards used throughout the Clinical Decision Support System (CDSS) project. Following these guidelines ensures consistency, maintainability, and readability across the codebase.

## Naming Conventions

| Element | Style | Example |
|---------|-------|---------|
| Classes | PascalCase | `PatientView`, `DecisionEngine`, `ActionScore` |
| Functions (public) | snake_case | `get_all_patients()`, `rank_actions()` |
| Variables | snake_case | `patient_id`, `transition_matrix` |
| Constants | UPPER_SNAKE_CASE | `SIDEBAR_BG`, `ACCENT`, `THRESHOLD_SAFE` |
| Private methods/functions | _ prefix + snake_case | `_update_trace()`, `_value_iteration()` |
| Protected attributes | _ prefix + snake_case | `_patient`, `_current_scores` |
| Module-level (internal) | _ prefix + snake_case | `_card()`, `_label()` |

## File Organization

### One Class Per File (Single Responsibility)

Except for small helper classes (like `ActionScore` defined in `engine.py`) and UI helpers (`_card`, `_label` in `main_window.py`).

### Import Order

```python
# 1. Standard library imports
from __future__ import annotations
import csv
from datetime import datetime
from typing import List, Dict, Optional

# 2. Third-party imports
from PyQt5.QtWidgets import QWidget, QVBoxLayout
from PyQt5.QtCore import Qt
import numpy as np

# 3. Internal project imports
from ..domain.patient import Patient
from ..domain.action import Action
from ..decision_engine.engine import DecisionEngine
```

Blank line between each group. Within each group, imports are alphabetical.

## Function Length

**Rule:** No function longer than 50 lines (excluding docstrings and blank lines).

**Exception:** UI `_build` methods in `src/ui/` may exceed 50 lines because they are **declarative layout code** rather than procedural logic. A 150‑line `_build` that simply stacks widgets is acceptable and more maintainable than splitting it arbitrarily. However, **logic** inside `_build` (e.g., signal connections, non‑layout initialisation) should still be extracted into helper methods.

If a non‑UI function exceeds 50 lines, refactor it into smaller helper functions. For example, `PatientView._refresh()` (which would be ~60 lines) is split into:
- `_refresh()` – coordinates refresh (10 lines)
- `_update_ranked_table()` – populates the action table (20 lines)
- `_update_risk_display()` – updates risk score and progress bar (15 lines)
- `_update_history_table()` – fills action history (10 lines)

## Docstrings

Every public function and class must have a docstring following this format:

### For a class:

```python
class DecisionEngine:
    """
    Computes and ranks actions for a given macro-state using value iteration.
    Implements the Bellman optimality equation for Markov Decision Processes.
    """
```

### For a function with parameters and return value:

```python
def get_audit_log(patient_id: str = None):
    """
    Fetch audit log entries from recommendation_run.
    
    Args:
        patient_id: If provided, filter to a specific patient.
                    If None, return all records.
    
    Returns:
        List of tuples: (patient_id, patient_name, recommended_action,
                         recommended_score, clinician_decision,
                         override_action, timestamp)
        Ordered by timestamp descending.
    """
```

### For simple functions without parameters:

```python
def get_connection():
    """Get a database connection to cdss.db."""
```

## Comments

### Section Dividers

For long files like `main_window.py`, use decorative dividers to separate logical sections:

```python
# ---------------------------------------------------------------------------
# Patient view — ranked actions + history
# ---------------------------------------------------------------------------
```

### Inline Comments

Write `why`, not `what`. The code itself tells what it does:

```python
# Good — explains why
risk_factor = 1.0 + (self.risk_spin.value() * 0.1)  # Each step = ±10% on immediate benefit

# Bad — repeats the code
risk_factor = 1.0 + (self.risk_spin.value() * 0.1)  # Multiply risk spin value by 0.1 and add 1
```

## Error Handling

All database operations and file I/O must be wrapped in try/except blocks:

```python
try:
    with get_connection() as conn:
        cursor = conn.execute("...")
        return cursor.fetchall()
except sqlite3.OperationalError as e:
    print(f"Database error: {e}")
    return []  # or re-raise, or handle appropriately
```

**Never silently swallow exceptions.** At minimum, print the error or log it.

## Type Hints

All function signatures must include type hints:

```python
def get_actions_for_patient(patient_id: str) -> List[Tuple]:
def load_patient(self, patient: Patient, actions: list[Action]) -> None:
def _update_trace(self) -> None:
```

For complex types, import from `typing`:

```python
from typing import List, Tuple, Dict, Optional
```

## Indentation & Spacing

- **Indentation:** 4 spaces (no tabs)
- **Blank lines:**
  - Two blank lines between top-level functions and classes
  - One blank line between methods in a class
  - One blank line before and after section dividers
- **Line length:** Maximum 120 characters

## Example – A Well-Formatted Function

```python
def get_benefit_risk_for_patient(patient_id: str) -> List[Tuple]:
    """
    Returns (action_name, expected_benefit, complication_risk, side_effect_cost)
    for the patient's current disease and state.
    """
    with get_connection() as conn:
        try:
            cursor = conn.execute("""
                SELECT 
                    a.action_name,
                    au.expected_benefit,
                    au.complication_risk,
                    au.side_effect_cost
                FROM patient_status ps
                JOIN action a ON a.disease_id = ps.disease_id
                JOIN action_utility au ON a.id = au.action_id 
                    AND au.state_id = ps.current_state_id
                WHERE ps.patient_id = ?
                ORDER BY a.action_name
            """, (patient_id,))
            return cursor.fetchall()
        except sqlite3.OperationalError as e:
            print(f"Error fetching benefit/risk for patient {patient_id}: {e}")
            return []
```

## Exceptions to Rules

| Rule | Exception | Justification |
|------|-----------|---------------|
| 50‑line limit | UI `_build` methods | Declarative layout code; splitting would harm readability |
| One class per file | `ActionScore` in `engine.py` | Tightly coupled to `DecisionEngine`; separate file would add overhead |
| No `_` prefix for module‑level helpers | `_card`, `_label` in `main_window.py` | Indicates they are internal to the UI module, not part of the public API |

## Enforcement

These guidelines are enforced by code review, not automation. All team members are responsible for following them.
