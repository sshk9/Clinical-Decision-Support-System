# Clinical Decision Support System (CDSS)

A desktop application that assists General Practitioners (GPs) in making optimal treatment decisions for patients with diseases that evolve non‑deterministically over time. The system uses a **Markov Decision Process (MDP)** framework to model disease progression, evaluate treatment actions, and provide ranked recommendations.

## Features

- **Patient Management** – Add, view, and select patients
- **Markov Disease Models** – Evidence‑based transitions for Type 2 Diabetes and Chronic Kidney Disease
- **Decision Engine** – Value iteration to rank treatment actions by long‑term expected utility
- **Decision Trace (Why‑Panel)** – Full Bellman decomposition explaining each recommendation
- **Sensitivity Analysis** – Interactive what‑if controls for discount factor and risk tolerance
- **Risk‑Benefit Plot** – Scatter plot of expected benefit vs complication risk for all actions
- **Patient Comparison** – Side‑by‑side comparison of two patients' actions
- **Population Health Trends** – Severity distribution, success rates, action effectiveness
- **Audit Log** – Complete history of clinician decisions with CSV export
- **Authentication** – Secure login with password hashing

## Installation

### Prerequisites

- Python 3.10 or higher
- pip (Python package manager)

### Setup

1. **Clone the repository**
```bash
git clone https://github.com/sshk9/Clinical-Decision-Support-System.git
cd Clinical-Decision-Support-System
```

2. **Create a virtual environment (Windows)**
```bash
python -m venv venv
venv\Scripts\activate
```

3. **Install dependencies**
```bash
pip install -r requirements.txt
```
3. **Create the Database**
```bash
python -m src.infrastructure.database
```
4. **Run the Application**
```
python main.py
```

### Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| PyQt5 | ≥ 5.15 | GUI framework |
| numpy | ≥ 1.24 | Numerical computing (transition matrices) |
| matplotlib | ≥ 3.7 | Charts (risk‑benefit plot, trends) |
| pytest | ≥ 7.0 | Unit testing |

### Default Login Credentials

| Username | Password |
|----------|----------|
| admin | admin123|

The demo user is automatically created when you run `database.py`. 

## Project Structure

```
Clinical-Decision-Support-System/
├── main.py                          # Entry point
├── requirements.txt                 # Dependencies
├── cdss.db                          # SQLite database (auto‑generated)
├── README.md                        # This file
├── docs/                            # Documentation
│   ├── code_style.md
│   ├── architecture.md
│   ├── database_schema.md
│   └── decision_engine.md
├── src/
│   ├── ui/                          # Presentation layer
│   │   ├── main_window.py
│   │   ├── login_view.py
│   │   ├── comparison_widget.py
│   │   ├── trend_widget.py
│   │   ├── add_patient_dialog.py
│   │   ├── audit_widget.py
│   │   ├── risk_benefit_plot.py
│   │   ├── add_patient_dialog_.py
│   │   └── sensitivity_panel.py
│   ├── decision_engine/             # MDP engine
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
│   └── analytics/                   # Pure analytics
│       └── analytics.py
└── tests/                           # Unit tests
    └── test_basic.py
```

## How to Use

1. **Login**
2. **Select a patient** from the Patient Management view
3. **View ranked actions** – the decision engine shows the best‑first list
4. **Click any action row** – the Decision Trace panel explains why the engine gave that score
5. **Adjust sensitivity** – Change γ (future weight) or risk tolerance to see projected score changes
6. **Accept/Reject/Override** – Log your clinical decision to the audit log
7. **Apply Action** – Actually modify the patient's disease model
8. **Simulate Progression** – Advance the patient's micro‑state according to transition probabilities

## Key Features Explained

### Decision Trace (Why‑Panel)

When you click an action in the ranked actions table, the trace panel shows:
- Immediate benefit of the action
- All possible future states with their probabilities and values (risky states in red)
- Discounted future value calculation
- Net utility

This makes the MDP's reasoning transparent – no black box.

### Sensitivity Analysis

The sensitivity panel lets you explore "what‑if" scenarios:
- **Future Value Weight (γ)** – Slide to value short‑term relief vs long‑term outcomes
- **Risk Tolerance** – Simulate a more or less aggressive clinician

The panel shows the projected score change without re‑running the full value iteration.

### Risk‑Benefit Plot

A scatter plot showing every action's expected benefit (X) vs complication risk (Y):
- Points coloured by net utility (green = high, red = low)
- Diagonal reference line shows where risk equals benefit
- Tooltips show exact values on hover

## Known Limitations

| Limitation | Description | Impact |
|------------|-------------|--------|
| No real‑time calibration | The system learns from clinician decisions (audit log) but does not automatically update transition probabilities | Model remains static after seeding |
| No role‑based access control (UI) | User authentication exists but no admin/clinician distinction in the interface | All logged‑in users have same permissions(for now) |
| No browser support | Desktop application only (PyQt5) | Cannot run in a web browser |
| Confidence intervals not implemented | Action scores are shown without statistical confidence bounds | Clinicians see point estimates only |
| No HL7/FHIR integration | Cannot export to hospital EHR systems | Manual data entry required for external systems |

These limitations are acknowledged as scope for future work.

## Academic Integrity Statement

This project was developed as a student project. All code is original unless otherwise noted. Transition probabilities for Type 2 Diabetes are adapted from Varshney et al. (2020) as cited in the source code comments.

**Members**
- Eva
- Sara
- Stuti
