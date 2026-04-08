import sqlite3
from typing import List, Tuple
import numpy as np

from ..domain.disease_model import DiseaseModel
from ..domain.action import Action


def get_connection():
    """Get a database connection."""
    return sqlite3.connect("cdss.db")


def init_db():
    """
    Initialize all database tables using IF NOT EXISTS.
    Order matters due to foreign key constraints.
    """
    with get_connection() as conn:
        conn.execute("PRAGMA foreign_keys = ON")

        conn.execute("""
            CREATE TABLE IF NOT EXISTS disease (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                description TEXT
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS disease_state (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                disease_id INTEGER NOT NULL,
                state_name TEXT NOT NULL,
                severity_level INTEGER CHECK (severity_level BETWEEN 1 AND 5),
                FOREIGN KEY (disease_id) REFERENCES disease(id) ON DELETE CASCADE,
                UNIQUE(disease_id, state_name)
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS markov_model (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                disease_id INTEGER NOT NULL,
                model_name TEXT NOT NULL,
                version TEXT NOT NULL,
                is_active BOOLEAN DEFAULT 0,
                FOREIGN KEY (disease_id) REFERENCES disease(id) ON DELETE CASCADE,
                UNIQUE(disease_id, version)
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS markov_transition (
                model_id INTEGER NOT NULL,
                from_state_id INTEGER NOT NULL,
                to_state_id INTEGER NOT NULL,
                probability REAL NOT NULL CHECK (probability >= 0 AND probability <= 1),
                FOREIGN KEY (model_id) REFERENCES markov_model(id) ON DELETE CASCADE,
                FOREIGN KEY (from_state_id) REFERENCES disease_state(id) ON DELETE CASCADE,
                FOREIGN KEY (to_state_id) REFERENCES disease_state(id) ON DELETE CASCADE,
                PRIMARY KEY (model_id, from_state_id, to_state_id)
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS action (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                disease_id INTEGER NOT NULL,
                action_name TEXT NOT NULL,
                description TEXT,
                improve_state TEXT,
                worsen_state TEXT,
                delta REAL CHECK (delta >= 0 AND delta <= 1),
                FOREIGN KEY (disease_id) REFERENCES disease(id) ON DELETE CASCADE,
                UNIQUE(disease_id, action_name)
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS action_utility (
                disease_id INTEGER NOT NULL,
                state_id INTEGER NOT NULL,
                action_id INTEGER NOT NULL,
                expected_benefit REAL NOT NULL,
                complication_risk REAL NOT NULL,
                side_effect_cost REAL NOT NULL,
                FOREIGN KEY (disease_id) REFERENCES disease(id) ON DELETE CASCADE,
                FOREIGN KEY (state_id) REFERENCES disease_state(id) ON DELETE CASCADE,
                FOREIGN KEY (action_id) REFERENCES action(id) ON DELETE CASCADE,
                PRIMARY KEY (disease_id, state_id, action_id)
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS patient (
                id TEXT PRIMARY KEY,
                first_name TEXT NOT NULL,
                last_name TEXT NOT NULL
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS patient_status (
                patient_id TEXT PRIMARY KEY,
                disease_id INTEGER NOT NULL,
                current_state_id INTEGER NOT NULL,
                active_model_id INTEGER NOT NULL,
                FOREIGN KEY (patient_id) REFERENCES patient(id) ON DELETE CASCADE,
                FOREIGN KEY (disease_id) REFERENCES disease(id) ON DELETE CASCADE,
                FOREIGN KEY (current_state_id) REFERENCES disease_state(id) ON DELETE CASCADE,
                FOREIGN KEY (active_model_id) REFERENCES markov_model(id) ON DELETE CASCADE
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                hashed_password TEXT NOT NULL,
                salt TEXT NOT NULL
            )
        """)

        conn.commit()
        print("Database tables initialized successfully")


def seed_data():
    """
    Seed the database with two real diseases:
    1. Type 2 Diabetes — transition probabilities from Varshney et al. (2020)
       'Estimation of transition probabilities for diabetic patients using HMM'
    2. Chronic Kidney Disease — based on published CKD progression literature
    """
    with get_connection() as conn:
        conn.execute("PRAGMA foreign_keys = ON")

        # Clear existing data
        conn.execute("DELETE FROM patient_status")
        conn.execute("DELETE FROM patient")
        conn.execute("DELETE FROM action_utility")
        conn.execute("DELETE FROM action")
        conn.execute("DELETE FROM markov_transition")
        conn.execute("DELETE FROM markov_model")
        conn.execute("DELETE FROM disease_state")
        conn.execute("DELETE FROM disease")

        # ---------------------------------------------------------------
        # Disease 1 — Type 2 Diabetes
        # Transition matrix from Varshney et al. (2020), Table 4
        # States based on HbA1c levels
        # ---------------------------------------------------------------
        conn.execute("""
            INSERT INTO disease (name, description) VALUES (?, ?)
        """, (
            "Type 2 Diabetes",
            "Three-state diabetes model based on HbA1c levels: "
            "Normal (HbA1c < 5.6%), Pre-diabetic (5.7-6.4%), Diabetic (>= 6.5%). "
            "Transition probabilities from Varshney et al. (2020)."
        ))
        diabetes_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

        diabetes_states = ["Normal", "Pre-diabetic", "Diabetic"]
        diabetes_severity = {"Normal": 1, "Pre-diabetic": 3, "Diabetic": 5}
        diabetes_state_ids = {}

        for state in diabetes_states:
            conn.execute("""
                INSERT INTO disease_state (disease_id, state_name, severity_level)
                VALUES (?, ?, ?)
            """, (diabetes_id, state, diabetes_severity[state]))
            diabetes_state_ids[state] = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

        conn.execute("""
            INSERT INTO markov_model (disease_id, model_name, version, is_active)
            VALUES (?, ?, ?, ?)
        """, (diabetes_id, "HbA1c-based Diabetes Model", "1.0.0", 1))
        diabetes_model_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

        # From Varshney et al. (2020), Table 4 — estimated transition probabilities
        diabetes_transitions = [
            ("Normal",      "Normal",      0.280),
            ("Normal",      "Pre-diabetic",0.208),
            ("Normal",      "Diabetic",    0.512),
            ("Pre-diabetic","Normal",      0.267),
            ("Pre-diabetic","Pre-diabetic",0.339),
            ("Pre-diabetic","Diabetic",    0.394),
            ("Diabetic",    "Normal",      0.240),
            ("Diabetic",    "Pre-diabetic",0.196),
            ("Diabetic",    "Diabetic",    0.564),
        ]

        for from_state, to_state, prob in diabetes_transitions:
            conn.execute("""
                INSERT INTO markov_transition (model_id, from_state_id, to_state_id, probability)
                VALUES (?, ?, ?, ?)
            """, (diabetes_model_id,
                  diabetes_state_ids[from_state],
                  diabetes_state_ids[to_state],
                  prob))

        diabetes_actions = [
            ("Watch and Wait",
             "Monitor HbA1c levels and reassess at next visit. No pharmacological intervention.",
             None, None, 0.0),
            ("Prescribe Metformin",
             "First-line pharmacological treatment. Reduces hepatic glucose production.",
             "Pre-diabetic", "Diabetic", 0.10),
            ("Lifestyle Intervention",
             "Structured diet, exercise, and behavioural changes to reduce HbA1c.",
             "Normal", "Diabetic", 0.08),
            ("Refer to Endocrinologist",
             "Escalate to specialist for advanced diabetes management.",
             "Normal", "Diabetic", 0.15),
        ]

        diabetes_action_ids = {}
        for name, desc, improve, worsen, delta in diabetes_actions:
            conn.execute("""
                INSERT INTO action (disease_id, action_name, description,
                                   improve_state, worsen_state, delta)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (diabetes_id, name, desc, improve, worsen, delta))
            diabetes_action_ids[name] = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

        diabetes_utilities = {
            "Watch and Wait":          {"benefit": 0.20, "risk": 0.05, "cost": 0.02},
            "Prescribe Metformin":     {"benefit": 0.75, "risk": 0.10, "cost": 0.12},
            "Lifestyle Intervention":  {"benefit": 0.60, "risk": 0.05, "cost": 0.08},
            "Refer to Endocrinologist":{"benefit": 0.70, "risk": 0.08, "cost": 0.10},
        }

        for state_name in diabetes_states:
            state_id = diabetes_state_ids[state_name]
            for action_name, u in diabetes_utilities.items():
                conn.execute("""
                    INSERT INTO action_utility
                        (disease_id, state_id, action_id,
                         expected_benefit, complication_risk, side_effect_cost)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (diabetes_id, state_id, diabetes_action_ids[action_name],
                      u["benefit"], u["risk"], u["cost"]))

        # ---------------------------------------------------------------
        # Disease 2 — Chronic Kidney Disease (CKD)
        # States based on GFR (glomerular filtration rate)
        # ---------------------------------------------------------------
        conn.execute("""
            INSERT INTO disease (name, description) VALUES (?, ?)
        """, (
            "Chronic Kidney Disease",
            "Three-state CKD model based on GFR: "
            "Normal (GFR > 60), Mild CKD (GFR 30-60), Severe CKD (GFR < 30)."
        ))
        ckd_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

        ckd_states = ["Normal", "Mild CKD", "Severe CKD"]
        ckd_severity = {"Normal": 1, "Mild CKD": 3, "Severe CKD": 5}
        ckd_state_ids = {}

        for state in ckd_states:
            conn.execute("""
                INSERT INTO disease_state (disease_id, state_name, severity_level)
                VALUES (?, ?, ?)
            """, (ckd_id, state, ckd_severity[state]))
            ckd_state_ids[state] = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

        conn.execute("""
            INSERT INTO markov_model (disease_id, model_name, version, is_active)
            VALUES (?, ?, ?, ?)
        """, (ckd_id, "GFR-based CKD Progression Model", "1.0.0", 1))
        ckd_model_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

        # CKD is more progressive and less reversible than diabetes
        ckd_transitions = [
            ("Normal",    "Normal",    0.90),
            ("Normal",    "Mild CKD",  0.08),
            ("Normal",    "Severe CKD",0.02),
            ("Mild CKD",  "Normal",    0.05),
            ("Mild CKD",  "Mild CKD",  0.75),
            ("Mild CKD",  "Severe CKD",0.20),
            ("Severe CKD","Normal",    0.02),
            ("Severe CKD","Mild CKD",  0.08),
            ("Severe CKD","Severe CKD",0.90),
        ]

        for from_state, to_state, prob in ckd_transitions:
            conn.execute("""
                INSERT INTO markov_transition (model_id, from_state_id, to_state_id, probability)
                VALUES (?, ?, ?, ?)
            """, (ckd_model_id,
                  ckd_state_ids[from_state],
                  ckd_state_ids[to_state],
                  prob))

        ckd_actions = [
            ("Watch and Wait",
             "Monitor GFR and creatinine levels. Reassess at next visit.",
             None, None, 0.0),
            ("Blood Pressure Control",
             "ACE inhibitors or ARBs to slow CKD progression by reducing proteinuria.",
             "Normal", "Severe CKD", 0.12),
            ("Dietary Restriction",
             "Low-protein, low-sodium diet to reduce kidney workload.",
             "Mild CKD", "Severe CKD", 0.06),
            ("Refer to Nephrologist",
             "Specialist referral for advanced CKD management and dialysis planning.",
             "Normal", "Severe CKD", 0.15),
        ]

        ckd_action_ids = {}
        for name, desc, improve, worsen, delta in ckd_actions:
            conn.execute("""
                INSERT INTO action (disease_id, action_name, description,
                                   improve_state, worsen_state, delta)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (ckd_id, name, desc, improve, worsen, delta))
            ckd_action_ids[name] = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

        ckd_utilities = {
            "Watch and Wait":       {"benefit": 0.15, "risk": 0.05, "cost": 0.02},
            "Blood Pressure Control":{"benefit": 0.70, "risk": 0.10, "cost": 0.12},
            "Dietary Restriction":  {"benefit": 0.50, "risk": 0.05, "cost": 0.05},
            "Refer to Nephrologist":{"benefit": 0.75, "risk": 0.08, "cost": 0.10},
        }

        for state_name in ckd_states:
            state_id = ckd_state_ids[state_name]
            for action_name, u in ckd_utilities.items():
                conn.execute("""
                    INSERT INTO action_utility
                        (disease_id, state_id, action_id,
                         expected_benefit, complication_risk, side_effect_cost)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (ckd_id, state_id, ckd_action_ids[action_name],
                      u["benefit"], u["risk"], u["cost"]))

        # ---------------------------------------------------------------
        # Patients — 3 diabetes, 3 CKD
        # ---------------------------------------------------------------
        diabetes_patients = [
            ("P001", "John",  "Smith",    "Normal"),
            ("P002", "Maria", "Klein",    "Diabetic"),
            ("P003", "Lucas", "Mitchell", "Pre-diabetic"),
        ]

        ckd_patients = [
            ("P004", "Anna",   "Fischer", "Mild CKD"),
            ("P005", "James",  "Patel",   "Severe CKD"),
            ("P006", "Sophie", "Müller",  "Normal"),
        ]

        for patient_id, first, last, state in diabetes_patients:
            conn.execute("""
                INSERT INTO patient (id, first_name, last_name) VALUES (?, ?, ?)
            """, (patient_id, first, last))
            conn.execute("""
                INSERT INTO patient_status
                    (patient_id, disease_id, current_state_id, active_model_id)
                VALUES (?, ?, ?, ?)
            """, (patient_id, diabetes_id,
                  diabetes_state_ids[state], diabetes_model_id))

        for patient_id, first, last, state in ckd_patients:
            conn.execute("""
                INSERT INTO patient (id, first_name, last_name) VALUES (?, ?, ?)
            """, (patient_id, first, last))
            conn.execute("""
                INSERT INTO patient_status
                    (patient_id, disease_id, current_state_id, active_model_id)
                VALUES (?, ?, ?, ?)
            """, (patient_id, ckd_id,
                  ckd_state_ids[state], ckd_model_id))

        conn.commit()
        print("Database seeded: 2 diseases, 6 patients")
        print("  - Type 2 Diabetes: 3 patients (P001-P003)")
        print("  - Chronic Kidney Disease: 3 patients (P004-P006)")

# ---------------------------------------------------------------------------
# Raw query functions
# ---------------------------------------------------------------------------

def get_all_patients() -> List[Tuple[str, str, str, str]]:
    """Returns a list of (patient_id, full_name, current_state, disease_name)."""
    with get_connection() as conn:
        cursor = conn.execute("""
            SELECT
                p.id,
                p.first_name || ' ' || p.last_name as full_name,
                ds.state_name as current_state,
                d.name as disease_name
            FROM patient p
            JOIN patient_status ps ON p.id = ps.patient_id
            JOIN disease_state ds ON ps.current_state_id = ds.id
            JOIN disease d ON ps.disease_id = d.id
            ORDER BY p.id
        """)
        return cursor.fetchall()

def get_model_for_patient(patient_id: str) -> Tuple[List[str], List[List[float]]]:
    """Returns (state_names, transition_matrix) for the patient's active model."""
    with get_connection() as conn:
        cursor = conn.execute("""
            SELECT active_model_id FROM patient_status WHERE patient_id = ?
        """, (patient_id,))
        result = cursor.fetchone()
        if not result:
            return [], []

        model_id = result[0]

        cursor = conn.execute("""
            SELECT ds.id, ds.state_name
            FROM disease_state ds
            JOIN patient_status ps ON ds.disease_id = ps.disease_id
            WHERE ps.patient_id = ?
            ORDER BY ds.id
        """, (patient_id,))
        states = cursor.fetchall()

        state_names = [s[1] for s in states]
        state_id_to_index = {s[0]: i for i, s in enumerate(states)}

        n = len(state_names)
        matrix = [[0.0] * n for _ in range(n)]

        cursor = conn.execute("""
            SELECT from_state_id, to_state_id, probability
            FROM markov_transition WHERE model_id = ?
        """, (model_id,))

        for from_id, to_id, prob in cursor.fetchall():
            matrix[state_id_to_index[from_id]][state_id_to_index[to_id]] = prob

        return state_names, matrix


def get_actions_for_patient(patient_id: str) -> List[Tuple]:
    """Returns raw action tuples for the patient's current state."""
    with get_connection() as conn:
        cursor = conn.execute("""
            SELECT ps.disease_id, ps.current_state_id
            FROM patient_status ps WHERE ps.patient_id = ?
        """, (patient_id,))
        result = cursor.fetchone()
        if not result:
            return []

        disease_id, current_state_id = result

        cursor = conn.execute("""
            SELECT
                a.action_name,
                a.description,
                au.expected_benefit,
                au.complication_risk,
                au.side_effect_cost,
                a.improve_state,
                a.worsen_state,
                a.delta
            FROM action a
            JOIN action_utility au ON a.id = au.action_id
            WHERE a.disease_id = ? AND au.state_id = ?
            ORDER BY a.action_name
        """, (disease_id, current_state_id))

        return cursor.fetchall()


# ---------------------------------------------------------------------------
# Domain object conversion functions
# ---------------------------------------------------------------------------

def load_disease_model(patient_id: str) -> DiseaseModel:
    """
    Load the active disease model for a patient and return a DiseaseModel object.
    """
    state_names, matrix = get_model_for_patient(patient_id)
    if not state_names:
        raise ValueError(f"No disease model found for patient '{patient_id}'.")
    return DiseaseModel(states=tuple(state_names), P=np.array(matrix))


def load_actions(patient_id: str) -> List[Action]:
    """
    Load available actions for a patient and return a list of Action objects.
    immediate_utility is computed as benefit - risk - cost.
    """
    rows = get_actions_for_patient(patient_id)
    actions = []
    for name, desc, benefit, risk, cost, improve, worsen, delta in rows:
        actions.append(Action(
            name=name,
            description=desc or "",
            immediate_utility=round(benefit - risk - cost, 6),
            improve_state=improve,
            worsen_state=worsen,
            delta=delta or 0.0,
        ))
    return actions


# ---------------------------------------------------------------------------
# User authentication functions
# ---------------------------------------------------------------------------

def get_user_by_username(username: str):
    """Returns (hashed_password, salt) or None if user not found."""
    with get_connection() as conn:
        cursor = conn.execute(
            "SELECT hashed_password, salt FROM users WHERE username = ?", (username,)
        )
        return cursor.fetchone()


def create_user(username: str, hashed_password: str, salt: str) -> None:
    """Inserts a new user into the database."""
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO users (username, hashed_password, salt) VALUES (?, ?, ?)",
            (username, hashed_password, salt)
        )
        conn.commit()


# ---------------------------------------------------------------------------
# Direct execution — initialize and verify
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("Initializing database...")
    init_db()
    print("Seeding data...")
    seed_data()

    print("\nVerification:")
    patients = get_all_patients()
    print(f"Found {len(patients)} patients:")
    for patient_id, full_name, state, disease_name in patients:
        print(f"  - {patient_id}: {full_name} - {state}")

        if patient_id == "P001":
            model = load_disease_model(patient_id)
            print(f"\n  DiseaseModel for {full_name}: {model.states}")

            actions = load_actions(patient_id)
            print(f"  Actions for {full_name}:")
            for action in actions:
                print(f"    - {action.name}: immediate_utility={action.immediate_utility}")

    print("\nDatabase ready!")
