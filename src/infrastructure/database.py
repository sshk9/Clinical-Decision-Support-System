import sqlite3
import hashlib
import secrets
from typing import List, Tuple, Dict, Any

import numpy as np

from ..domain.disease_model import DiseaseModel
from ..domain.action import Action


# ---------------------------------------------------------------------------
# Connection
# ---------------------------------------------------------------------------

def get_connection():
    """Get a database connection to cdss.db."""
    return sqlite3.connect("cdss.db")


# ---------------------------------------------------------------------------
# Schema initialisation
# ---------------------------------------------------------------------------

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

        conn.execute("""
            CREATE TABLE IF NOT EXISTS recommendation_run (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                patient_id TEXT NOT NULL,
                recommended_action TEXT,
                recommended_score REAL,
                clinician_decision TEXT CHECK(clinician_decision IN ('accept', 'reject', 'override')),
                override_action TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (patient_id) REFERENCES patient(id) ON DELETE CASCADE
            )
        """)

        conn.commit()
        print("Database tables initialized successfully")


# ---------------------------------------------------------------------------
# Seed data
# ---------------------------------------------------------------------------

def seed_data():
    """
    Seed the database with two real diseases:
    1. Type 2 Diabetes — transition probabilities from Varshney et al. (2020)
    2. Chronic Kidney Disease — based on published CKD progression literature
    Also creates a demo user account (admin / admin123).
    """
    with get_connection() as conn:
        conn.execute("PRAGMA foreign_keys = ON")

        # Clear existing data
        conn.execute("DELETE FROM recommendation_run")
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

        diabetes_transitions = [
            ("Normal",       "Normal",       0.280),
            ("Normal",       "Pre-diabetic", 0.208),
            ("Normal",       "Diabetic",     0.512),
            ("Pre-diabetic", "Normal",       0.267),
            ("Pre-diabetic", "Pre-diabetic", 0.339),
            ("Pre-diabetic", "Diabetic",     0.394),
            ("Diabetic",     "Normal",       0.240),
            ("Diabetic",     "Pre-diabetic", 0.196),
            ("Diabetic",     "Diabetic",     0.564),
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
             "Monitor HbA1c levels. No pharmacological intervention.",
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
            "Watch and Wait":           {"benefit": 0.20, "risk": 0.05, "cost": 0.02},
            "Prescribe Metformin":      {"benefit": 0.75, "risk": 0.10, "cost": 0.12},
            "Lifestyle Intervention":   {"benefit": 0.60, "risk": 0.05, "cost": 0.08},
            "Refer to Endocrinologist": {"benefit": 0.70, "risk": 0.08, "cost": 0.10},
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

        ckd_transitions = [
            ("Normal",    "Normal",     0.90),
            ("Normal",    "Mild CKD",   0.08),
            ("Normal",    "Severe CKD", 0.02),
            ("Mild CKD",  "Normal",     0.05),
            ("Mild CKD",  "Mild CKD",   0.75),
            ("Mild CKD",  "Severe CKD", 0.20),
            ("Severe CKD","Normal",     0.02),
            ("Severe CKD","Mild CKD",   0.08),
            ("Severe CKD","Severe CKD", 0.90),
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
            "Watch and Wait":         {"benefit": 0.15, "risk": 0.05, "cost": 0.02},
            "Blood Pressure Control": {"benefit": 0.70, "risk": 0.10, "cost": 0.12},
            "Dietary Restriction":    {"benefit": 0.50, "risk": 0.05, "cost": 0.05},
            "Refer to Nephrologist":  {"benefit": 0.75, "risk": 0.08, "cost": 0.10},
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
        # Patients
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
            conn.execute(
                "INSERT INTO patient (id, first_name, last_name) VALUES (?, ?, ?)",
                (patient_id, first, last))
            conn.execute(
                "INSERT INTO patient_status "
                "(patient_id, disease_id, current_state_id, active_model_id) "
                "VALUES (?, ?, ?, ?)",
                (patient_id, diabetes_id, diabetes_state_ids[state], diabetes_model_id))

        for patient_id, first, last, state in ckd_patients:
            conn.execute(
                "INSERT INTO patient (id, first_name, last_name) VALUES (?, ?, ?)",
                (patient_id, first, last))
            conn.execute(
                "INSERT INTO patient_status "
                "(patient_id, disease_id, current_state_id, active_model_id) "
                "VALUES (?, ?, ?, ?)",
                (patient_id, ckd_id, ckd_state_ids[state], ckd_model_id))

        # ---------------------------------------------------------------
        # Demo user: admin / admin123
        # ---------------------------------------------------------------
        demo_salt = secrets.token_hex(16)
        demo_hashed = hashlib.sha256((demo_salt + "admin123").encode()).hexdigest()
        conn.execute("""
            INSERT OR IGNORE INTO users (username, hashed_password, salt)
            VALUES (?, ?, ?)
        """, ("admin", demo_hashed, demo_salt))

        conn.commit()
        print("Database seeded: 2 diseases, 6 patients, 1 demo user")
        print("  - Type 2 Diabetes: P001-P003")
        print("  - Chronic Kidney Disease: P004-P006")
        print("  - Login: admin / admin123")


# ---------------------------------------------------------------------------
# Core patient queries
# ---------------------------------------------------------------------------

def get_all_patients() -> List[Tuple[str, str, str, str]]:
    """
    Returns a list of (patient_id, full_name, current_state, disease_name).
    Kept for backward compatibility with ComparisonWidget, AuditWidget, TrendWidget.
    """
    with get_connection() as conn:
        cursor = conn.execute("""
            SELECT
                p.id,
                p.first_name || ' ' || p.last_name AS full_name,
                ds.state_name AS current_state,
                d.name AS disease_name
            FROM patient p
            JOIN patient_status ps ON p.id = ps.patient_id
            JOIN disease_state ds ON ps.current_state_id = ds.id
            JOIN disease d ON ps.disease_id = d.id
            ORDER BY p.id
        """)
        return cursor.fetchall()


def get_all_patients_detailed() -> List[Dict[str, Any]]:
    """
    Returns detailed patient information including severity and model version.
    Used by PatientManagementView for the enhanced table display.

    Returns:
        List of dicts with keys: patient_id, first_name, last_name,
        disease_name, current_state, severity_level, model_version, active_model_id
    """
    with get_connection() as conn:
        cursor = conn.execute("""
            SELECT
                p.id,
                p.first_name,
                p.last_name,
                d.name AS disease_name,
                ds.state_name AS current_state,
                ds.severity_level,
                mm.version AS model_version,
                ps.active_model_id
            FROM patient p
            JOIN patient_status ps ON p.id = ps.patient_id
            JOIN disease d ON ps.disease_id = d.id
            JOIN disease_state ds ON ps.current_state_id = ds.id
            JOIN markov_model mm ON ps.active_model_id = mm.id
            ORDER BY p.id
        """)
        results = []
        for row in cursor.fetchall():
            results.append({
                "patient_id":      row[0],
                "first_name":      row[1],
                "last_name":       row[2],
                "disease_name":    row[3],
                "current_state":   row[4],
                "severity_level":  row[5],
                "model_version":   row[6],
                "active_model_id": row[7],
            })
        return results


def get_model_for_patient(patient_id: str) -> Tuple[List[str], List[List[float]]]:
    """
    Returns (state_names, transition_matrix) for the patient's active model.

    Args:
        patient_id: The patient's ID string (e.g. "P001")

    Returns:
        Tuple of (list of state names, 2D transition matrix as list of lists)
    """
    with get_connection() as conn:
        cursor = conn.execute(
            "SELECT active_model_id FROM patient_status WHERE patient_id = ?",
            (patient_id,))
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

        cursor = conn.execute(
            "SELECT from_state_id, to_state_id, probability "
            "FROM markov_transition WHERE model_id = ?",
            (model_id,))
        for from_id, to_id, prob in cursor.fetchall():
            matrix[state_id_to_index[from_id]][state_id_to_index[to_id]] = prob

        return state_names, matrix


def get_actions_for_patient(patient_id: str) -> List[Tuple]:
    """
    Returns raw action tuples for the patient's current disease and state.

    Returns:
        List of (action_name, description, expected_benefit, complication_risk,
                 side_effect_cost, improve_state, worsen_state, delta)
    """
    with get_connection() as conn:
        cursor = conn.execute(
            "SELECT ps.disease_id, ps.current_state_id "
            "FROM patient_status ps WHERE ps.patient_id = ?",
            (patient_id,))
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
# Analytics queries
# ---------------------------------------------------------------------------

def get_action_utility_comparison(disease_id: int) -> List[Dict[str, Any]]:
    """
    Fetches all actions with their avg benefit, risk, cost across all states
    for a given disease. Powers the action effectiveness chart.

    Args:
        disease_id: The disease ID to query actions for

    Returns:
        List of dicts with keys: action_name, avg_benefit, avg_risk,
        avg_cost, net_utility. Sorted by net_utility descending.
    """
    with get_connection() as conn:
        cursor = conn.execute("""
            SELECT
                a.action_name,
                AVG(au.expected_benefit)  AS avg_benefit,
                AVG(au.complication_risk) AS avg_risk,
                AVG(au.side_effect_cost)  AS avg_cost
            FROM action a
            JOIN action_utility au ON a.id = au.action_id
            WHERE a.disease_id = ?
            GROUP BY a.id, a.action_name
            ORDER BY (AVG(au.expected_benefit)
                      - AVG(au.complication_risk)
                      - AVG(au.side_effect_cost)) DESC
        """, (disease_id,))

        results = []
        for row in cursor.fetchall():
            action_name, avg_benefit, avg_risk, avg_cost = row
            results.append({
                "action_name": action_name,
                "avg_benefit": round(avg_benefit, 4),
                "avg_risk":    round(avg_risk, 4),
                "avg_cost":    round(avg_cost, 4),
                "net_utility": round(avg_benefit - avg_risk - avg_cost, 4),
            })
        return results


def get_state_distribution() -> List[Dict[str, Any]]:
    """
    Counts how many patients are in each state per disease.
    Powers the population health trend analytics.

    Returns:
        List of dicts with keys: disease_name, state_name,
        severity_level, patient_count
    """
    with get_connection() as conn:
        cursor = conn.execute("""
            SELECT
                d.name  AS disease_name,
                ds.state_name,
                ds.severity_level,
                COUNT(ps.patient_id) AS patient_count
            FROM patient_status ps
            JOIN disease d ON ps.disease_id = d.id
            JOIN disease_state ds ON ps.current_state_id = ds.id
            GROUP BY d.id, ds.id
            ORDER BY d.name, ds.severity_level
        """)
        results = []
        for row in cursor.fetchall():
            results.append({
                "disease_name":   row[0],
                "state_name":     row[1],
                "severity_level": row[2],
                "patient_count":  row[3],
            })
        return results


def get_benefit_risk_for_patient(patient_id: str) -> List[Tuple]:
    """
    Returns (action_name, expected_benefit, complication_risk, side_effect_cost)
    for the patient's current disease and state.
    Used by the risk-benefit scatter plot.
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


# ---------------------------------------------------------------------------
# Patient management
# ---------------------------------------------------------------------------

def get_diseases_with_states() -> List[Dict[str, Any]]:
    """
    Returns all diseases with their states and active model IDs.
    Used for populating the Add Patient dialog dropdowns.

    Returns:
        List of dicts with keys: disease_id, disease_name, state_id,
        state_name, severity_level, model_id, model_version
    """
    with get_connection() as conn:
        cursor = conn.execute("""
            SELECT
                d.id   AS disease_id,
                d.name AS disease_name,
                ds.id  AS state_id,
                ds.state_name,
                ds.severity_level,
                mm.id  AS model_id,
                mm.version AS model_version
            FROM disease d
            JOIN disease_state ds ON d.id = ds.disease_id
            JOIN markov_model mm ON d.id = mm.disease_id
            WHERE mm.is_active = 1
            ORDER BY d.name, ds.severity_level
        """)
        results = []
        for row in cursor.fetchall():
            results.append({
                "disease_id":     row[0],
                "disease_name":   row[1],
                "state_id":       row[2],
                "state_name":     row[3],
                "severity_level": row[4],
                "model_id":       row[5],
                "model_version":  row[6],
            })
        return results


def add_patient(patient_id: str, first_name: str, last_name: str,
                disease_id: int, state_id: int, model_id: int) -> bool:
    """
    Add a new patient to the database.

    Args:
        patient_id: Unique patient ID (e.g. "P007")
        first_name: Patient's first name
        last_name: Patient's last name
        disease_id: FK to disease(id)
        state_id: FK to disease_state(id) for initial state
        model_id: FK to markov_model(id) for active model

    Returns:
        True if inserted successfully, False if patient_id already exists.
    """
    with get_connection() as conn:
        try:
            cursor = conn.execute("SELECT 1 FROM patient WHERE id = ?", (patient_id,))
            if cursor.fetchone():
                return False

            conn.execute(
                "INSERT INTO patient (id, first_name, last_name) VALUES (?, ?, ?)",
                (patient_id, first_name, last_name))
            conn.execute(
                "INSERT INTO patient_status "
                "(patient_id, disease_id, current_state_id, active_model_id) "
                "VALUES (?, ?, ?, ?)",
                (patient_id, disease_id, state_id, model_id))
            conn.commit()
            return True
        except Exception as e:
            print(f"Error adding patient: {e}")
            return False


def get_patient_summary_export() -> List[Dict[str, Any]]:
    """
    Returns all patients with full details for CSV export.

    Returns:
        List of dicts with keys: patient_id, first_name, last_name,
        disease_name, current_state, severity_level, model_version
    """
    with get_connection() as conn:
        cursor = conn.execute("""
            SELECT
                p.id AS patient_id,
                p.first_name,
                p.last_name,
                d.name AS disease_name,
                ds.state_name AS current_state,
                ds.severity_level,
                mm.version AS model_version
            FROM patient p
            JOIN patient_status ps ON p.id = ps.patient_id
            JOIN disease d ON ps.disease_id = d.id
            JOIN disease_state ds ON ps.current_state_id = ds.id
            JOIN markov_model mm ON ps.active_model_id = mm.id
            ORDER BY p.id
        """)
        results = []
        for row in cursor.fetchall():
            results.append({
                "patient_id":     row[0],
                "first_name":     row[1],
                "last_name":      row[2],
                "disease_name":   row[3],
                "current_state":  row[4],
                "severity_level": row[5],
                "model_version":  row[6],
            })
        return results


# ---------------------------------------------------------------------------
# Audit log
# ---------------------------------------------------------------------------

def log_clinician_decision(patient_id: str, recommended_action: str,
                           recommended_score: float, decision: str,
                           override_action: str = None) -> None:
    """
    Log a clinician's decision regarding a recommendation.

    Args:
        patient_id: The patient's ID
        recommended_action: Name of the top-ranked recommended action
        recommended_score: Total score of the recommended action
        decision: One of 'accept', 'reject', 'override'
        override_action: If decision is 'override', the action chosen instead
    """
    with get_connection() as conn:
        conn.execute("""
            INSERT INTO recommendation_run
                (patient_id, recommended_action, recommended_score,
                 clinician_decision, override_action)
            VALUES (?, ?, ?, ?, ?)
        """, (patient_id, recommended_action, recommended_score,
              decision, override_action))
        conn.commit()
        
def log_recommendation(patient_id, recommended_action, recommended_score,
                       clinician_decision, override_action=None):
    """Alias for log_clinician_decision for backward compatibility."""
    log_clinician_decision(patient_id, recommended_action, recommended_score,
                           clinician_decision, override_action)


def get_audit_log(patient_id: str = None) -> List[Tuple]:
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
    with get_connection() as conn:
        if patient_id:
            cursor = conn.execute("""
                SELECT
                    p.id,
                    p.first_name || ' ' || p.last_name AS patient_name,
                    rr.recommended_action,
                    rr.recommended_score,
                    rr.clinician_decision,
                    rr.override_action,
                    rr.timestamp
                FROM recommendation_run rr
                JOIN patient p ON rr.patient_id = p.id
                WHERE rr.patient_id = ?
                ORDER BY rr.timestamp DESC
            """, (patient_id,))
        else:
            cursor = conn.execute("""
                SELECT
                    p.id,
                    p.first_name || ' ' || p.last_name AS patient_name,
                    rr.recommended_action,
                    rr.recommended_score,
                    rr.clinician_decision,
                    rr.override_action,
                    rr.timestamp
                FROM recommendation_run rr
                JOIN patient p ON rr.patient_id = p.id
                ORDER BY rr.timestamp DESC
            """)
        return cursor.fetchall()


# ---------------------------------------------------------------------------
# Domain object conversion
# ---------------------------------------------------------------------------

def load_disease_model(patient_id: str) -> DiseaseModel:
    """
    Load the active disease model for a patient and return a DiseaseModel object.

    Args:
        patient_id: The patient's ID string

    Returns:
        DiseaseModel with states and transition matrix

    Raises:
        ValueError: If no model is found for the patient
    """
    state_names, matrix = get_model_for_patient(patient_id)
    if not state_names:
        raise ValueError(f"No disease model found for patient '{patient_id}'.")
    return DiseaseModel(states=tuple(state_names), P=np.array(matrix))


def load_actions(patient_id: str) -> List[Action]:
    """
    Load available actions for a patient and return a list of Action objects.
    immediate_utility is computed as benefit - risk - cost.

    Args:
        patient_id: The patient's ID string

    Returns:
        List of Action domain objects
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
# User authentication
# ---------------------------------------------------------------------------

def get_user_by_username(username: str):
    """
    Returns (hashed_password, salt) for the given username,
    or None if user not found.
    """
    with get_connection() as conn:
        cursor = conn.execute(
            "SELECT hashed_password, salt FROM users WHERE username = ?",
            (username,))
        return cursor.fetchone()


def create_user(username: str, hashed_password: str, salt: str) -> None:
    """
    Inserts a new user into the database.

    Args:
        username: Unique login username
        hashed_password: SHA256 hash of (salt + password)
        salt: Random salt used for hashing
    """
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO users (username, hashed_password, salt) VALUES (?, ?, ?)",
            (username, hashed_password, salt))
        conn.commit()


# ---------------------------------------------------------------------------
# Entry point — initialize and seed
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
        print(f"  - {patient_id}: {full_name} ({disease_name}) — {state}")
    print("\nDatabase ready!")
