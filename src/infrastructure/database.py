import sqlite3
from typing import List, Tuple, Dict, Any, Optional
from datetime import datetime
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

        # New table for tracking clinician decisions and recommendations
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


def get_all_patients_detailed() -> List[Dict[str, Any]]:
    """
    Returns detailed patient information including severity and model version.
    Used by PatientManagementView for the enhanced table display.
    """
    with get_connection() as conn:
        cursor = conn.execute("""
            SELECT 
                p.id,
                p.first_name,
                p.last_name,
                d.name as disease_name,
                ds.state_name as current_state,
                ds.severity_level,
                mm.version as model_version,
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
                "patient_id": row[0],
                "first_name": row[1],
                "last_name": row[2],
                "disease_name": row[3],
                "current_state": row[4],
                "severity_level": row[5],
                "model_version": row[6],
                "active_model_id": row[7]
            })
        return results


def get_diseases_with_states() -> List[Dict[str, Any]]:
    """
    Returns all diseases with their states and active model IDs.
    Used for populating the add patient form.
    """
    with get_connection() as conn:
        cursor = conn.execute("""
            SELECT 
                d.id as disease_id,
                d.name as disease_name,
                ds.id as state_id,
                ds.state_name,
                ds.severity_level,
                mm.id as model_id,
                mm.version as model_version
            FROM disease d
            JOIN disease_state ds ON d.id = ds.disease_id
            JOIN markov_model mm ON d.id = mm.disease_id
            WHERE mm.is_active = 1
            ORDER BY d.name, ds.severity_level
        """)
        
        results = []
        for row in cursor.fetchall():
            results.append({
                "disease_id": row[0],
                "disease_name": row[1],
                "state_id": row[2],
                "state_name": row[3],
                "severity_level": row[4],
                "model_id": row[5],
                "model_version": row[6]
            })
        return results


def add_patient(patient_id: str, first_name: str, last_name: str, 
                disease_id: int, state_id: int, model_id: int) -> bool:
    """
    Add a new patient to the database.
    Returns True if successful, False if patient ID already exists.
    """
    with get_connection() as conn:
        try:
            # Check if patient already exists
            cursor = conn.execute("SELECT 1 FROM patient WHERE id = ?", (patient_id,))
            if cursor.fetchone():
                return False
            
            # Insert into patient table
            conn.execute("""
                INSERT INTO patient (id, first_name, last_name)
                VALUES (?, ?, ?)
            """, (patient_id, first_name, last_name))
            
            # Insert into patient_status table
            conn.execute("""
                INSERT INTO patient_status (patient_id, disease_id, current_state_id, active_model_id)
                VALUES (?, ?, ?, ?)
            """, (patient_id, disease_id, state_id, model_id))
            
            conn.commit()
            return True
        except Exception as e:
            print(f"Error adding patient: {e}")
            return False


def get_patient_summary_export() -> List[Dict[str, Any]]:
    """
    Returns all patients with full details for CSV export.
    """
    with get_connection() as conn:
        cursor = conn.execute("""
            SELECT 
                p.id as patient_id,
                p.first_name,
                p.last_name,
                d.name as disease_name,
                ds.state_name as current_state,
                ds.severity_level,
                mm.version as model_version
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
                "patient_id": row[0],
                "first_name": row[1],
                "last_name": row[2],
                "disease_name": row[3],
                "current_state": row[4],
                "severity_level": row[5],
                "model_version": row[6]
            })
        return results


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


def get_action_utility_comparison(disease_id: int) -> List[Dict[str, Any]]:
    """
    Fetches all actions with their avg benefit, risk, cost across all states for a given disease.
    Powers the "most effective strategies" insight.
    
    Args:
        disease_id: The disease ID to query actions for
        
    Returns:
        List of dicts with keys: action_name, avg_benefit, avg_risk, avg_cost, net_utility
    """
    with get_connection() as conn:
        cursor = conn.execute("""
            SELECT 
                a.action_name,
                AVG(au.expected_benefit) as avg_benefit,
                AVG(au.complication_risk) as avg_risk,
                AVG(au.side_effect_cost) as avg_cost
            FROM action a
            JOIN action_utility au ON a.id = au.action_id
            WHERE a.disease_id = ?
            GROUP BY a.id, a.action_name
            ORDER BY (AVG(au.expected_benefit) - AVG(au.complication_risk) - AVG(au.side_effect_cost)) DESC
        """, (disease_id,))
        
        results = []
        for row in cursor.fetchall():
            action_name, avg_benefit, avg_risk, avg_cost = row
            results.append({
                "action_name": action_name,
                "avg_benefit": round(avg_benefit, 4),
                "avg_risk": round(avg_risk, 4),
                "avg_cost": round(avg_cost, 4),
                "net_utility": round(avg_benefit - avg_risk - avg_cost, 4)
            })
        return results


def get_state_distribution() -> List[Dict[str, Any]]:
    """
    Counts how many patients are in each state per disease.
    Powers the "success rate of states" insight.
    
    Returns:
        List of dicts with keys: disease_name, state_name, severity_level, patient_count
    """
    with get_connection() as conn:
        cursor = conn.execute("""
            SELECT 
                d.name as disease_name,
                ds.state_name,
                ds.severity_level,
                COUNT(ps.patient_id) as patient_count
            FROM disease d
            JOIN disease_state ds ON ds.disease_id = d.id
            LEFT JOIN patient_status ps ON ps.current_state_id = ds.id
            GROUP BY d.id, ds.id
            ORDER BY d.name, ds.severity_level
        """)
        
        results = []
        for row in cursor.fetchall():
            disease_name, state_name, severity_level, patient_count = row
            results.append({
                "disease_name": disease_name,
                "state_name": state_name,
                "severity_level": severity_level,
                "patient_count": patient_count
            })
        return results


def get_benefit_risk_for_patient(patient_id: str) -> List[Tuple]:
    """
    Returns a list of (action_name, expected_benefit, complication_risk, side_effect_cost)
    for the patient's current disease and state.
    """
    with get_connection() as conn:
        cursor = conn.execute("""
            SELECT 
                a.action_name,
                au.expected_benefit,
                au.complication_risk,
                au.side_effect_cost
            FROM patient_status ps
            JOIN action a ON a.disease_id = ps.disease_id
            JOIN action_utility au ON a.id = au.action_id AND au.state_id = ps.current_state_id
            WHERE ps.patient_id = ?
            ORDER BY a.action_name
        """, (patient_id,))
        return cursor.fetchall()


# ---------------------------------------------------------------------------
# Recommendation tracking functions
# ---------------------------------------------------------------------------

def log_recommendation(
    patient_id: str,
    recommended_action: str,
    recommended_score: float,
    clinician_decision: str,
    override_action: Optional[str] = None
) -> None:
    """
    Log a clinical recommendation and the clinician's decision.
    
    Args:
        patient_id: The patient ID
        recommended_action: Name of the action recommended by the CDSS
        recommended_score: The total score of the recommended action
        clinician_decision: One of 'accept', 'reject', 'override'
        override_action: If decision is 'override', the action the clinician chose instead
    """
    with get_connection() as conn:
        conn.execute("""
            INSERT INTO recommendation_run 
            (patient_id, recommended_action, recommended_score, clinician_decision, override_action)
            VALUES (?, ?, ?, ?, ?)
        """, (patient_id, recommended_action, recommended_score, clinician_decision, override_action))
        conn.commit()


def get_recommendation_history(patient_id: str, limit: int = 50) -> List[Dict[str, Any]]:
    """
    Get recommendation history for a specific patient.
    
    Args:
        patient_id: The patient ID
        limit: Maximum number of records to return
        
    Returns:
        List of dicts with recommendation data
    """
    with get_connection() as conn:
        cursor = conn.execute("""
            SELECT 
                id,
                recommended_action,
                recommended_score,
                clinician_decision,
                override_action,
                timestamp
            FROM recommendation_run
            WHERE patient_id = ?
            ORDER BY timestamp DESC
            LIMIT ?
        """, (patient_id, limit))
        
        results = []
        for row in cursor.fetchall():
            results.append({
                "id": row[0],
                "recommended_action": row[1],
                "recommended_score": row[2],
                "clinician_decision": row[3],
                "override_action": row[4],
                "timestamp": row[5]
            })
        return results


def get_decision_analytics() -> Dict[str, Any]:
    """
    Get analytics on clinician decisions across all patients.
    
    Returns:
        Dict with acceptance rate, most common overrides, etc.
    """
    with get_connection() as conn:
        # Total recommendations
        cursor = conn.execute("SELECT COUNT(*) FROM recommendation_run")
        total = cursor.fetchone()[0]
        
        if total == 0:
            return {
                "total_recommendations": 0,
                "acceptance_rate": 0.0,
                "rejection_rate": 0.0,
                "override_rate": 0.0,
                "most_overridden_action": None,
                "top_overrides": []
            }
        
        # Decision counts
        cursor = conn.execute("""
            SELECT 
                clinician_decision,
                COUNT(*) as count
            FROM recommendation_run
            GROUP BY clinician_decision
        """)
        
        decision_counts = {row[0]: row[1] for row in cursor.fetchall()}
        
        accept_count = decision_counts.get('accept', 0)
        reject_count = decision_counts.get('reject', 0)
        override_count = decision_counts.get('override', 0)
        
        # Most overridden actions
        cursor = conn.execute("""
            SELECT 
                recommended_action,
                COUNT(*) as count
            FROM recommendation_run
            WHERE clinician_decision = 'override'
            GROUP BY recommended_action
            ORDER BY count DESC
            LIMIT 5
        """)
        
        top_overrides = [{"action": row[0], "count": row[1]} for row in cursor.fetchall()]
        
        # Most common override actions chosen
        cursor = conn.execute("""
            SELECT 
                override_action,
                COUNT(*) as count
            FROM recommendation_run
            WHERE clinician_decision = 'override' AND override_action IS NOT NULL
            GROUP BY override_action
            ORDER BY count DESC
            LIMIT 5
        """)
        
        most_overridden = cursor.fetchone()
        
        return {
            "total_recommendations": total,
            "acceptance_rate": round(accept_count / total * 100, 1) if total > 0 else 0,
            "rejection_rate": round(reject_count / total * 100, 1) if total > 0 else 0,
            "override_rate": round(override_count / total * 100, 1) if total > 0 else 0,
            "most_overridden_action": most_overridden[0] if most_overridden else None,
            "top_overrides": top_overrides
        }


def get_clinician_feedback_summary(patient_id: str) -> Dict[str, Any]:
    """
    Get summary of clinician feedback for a specific patient.
    
    Args:
        patient_id: The patient ID
        
    Returns:
        Dict with feedback summary
    """
    with get_connection() as conn:
        cursor = conn.execute("""
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN clinician_decision = 'accept' THEN 1 ELSE 0 END) as accepted,
                SUM(CASE WHEN clinician_decision = 'reject' THEN 1 ELSE 0 END) as rejected,
                SUM(CASE WHEN clinician_decision = 'override' THEN 1 ELSE 0 END) as overridden
            FROM recommendation_run
            WHERE patient_id = ?
        """, (patient_id,))
        
        row = cursor.fetchone()
        total, accepted, rejected, overridden = row
        
        return {
            "total_recommendations": total or 0,
            "accepted": accepted or 0,
            "rejected": rejected or 0,
            "overridden": overridden or 0,
            "acceptance_rate": round((accepted or 0) / (total or 1) * 100, 1)
        }


def log_clinician_decision(patient_id: str, recommended_action: str, recommended_score: float,
                           decision: str, override_action: str = None) -> None:
    """
    Log a clinician's decision regarding a recommendation.
    
    Args:
        patient_id: The patient's ID
        recommended_action: Name of the recommended action (top-ranked)
        recommended_score: Score of the recommended action
        decision: 'accept', 'reject', or 'override'
        override_action: If decision is 'override', the name of the action chosen instead
    """
    with get_connection() as conn:
        conn.execute("""
            INSERT INTO recommendation_run 
            (patient_id, recommended_action, recommended_score, clinician_decision, override_action)
            VALUES (?, ?, ?, ?, ?)
        """, (patient_id, recommended_action, recommended_score, decision, override_action))
        conn.commit()


# ---------------------------------------------------------------------------
# Audit log retrieval function
# ---------------------------------------------------------------------------
def get_audit_log(patient_id: str = None):
    """
    Fetch audit log entries from recommendation_run.
    
    Args:
        patient_id: If provided, filter to a specific patient. If None, return all records.
    
    Returns:
        List of tuples: (patient_id, patient_name, recommended_action, recommended_score,
                         clinician_decision, override_action, timestamp)
        Ordered by timestamp descending.
    """
    with get_connection() as conn:
        if patient_id:
            cursor = conn.execute("""
                SELECT 
                    p.id,
                    p.first_name || ' ' || p.last_name as patient_name,
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
                    p.first_name || ' ' || p.last_name as patient_name,
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

def get_user_by_username(username: str) -> Optional[Tuple[str, str]]:
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
# Patient service function
# ---------------------------------------------------------------------------

def load_patients_with_actions() -> List:
    """
    Load all patients with their actions for UI display.
    Returns a list of PatientRecord objects.
    """
    from ..domain.patient_record import PatientRecord
    from ..domain.patient import Patient
    from ..domain.macro_state import MacroState
    from ..domain.disease_model import DiseaseModel
    
    records = []
    for patient_id, full_name, current_state, disease_name in get_all_patients():
        # Load disease model and actions
        try:
            disease_model = load_disease_model(patient_id)
            actions = load_actions(patient_id)
            
            # Create MacroState with appropriate state index
            state_index = disease_model.states.index(current_state) if current_state in disease_model.states else 0
            
            macro_state = MacroState(
                state_index=state_index,
                model=disease_model,
                history=[],
                action_utility_history=[]
            )
            
            patient = Patient(
                patient_id=patient_id,
                name=full_name,
                disease_name=disease_name,
                macro_state=macro_state
            )
            
            records.append(PatientRecord(patient=patient, actions=actions))
        except Exception as e:
            print(f"Error loading patient {patient_id}: {e}")
            continue
    
    return records


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
        print(f"  - {patient_id}: {full_name} - {state} ({disease_name})")

    # Test action utility comparison
    print("\nAction Utility Comparison (Diabetes):")
    diabetes_comparison = get_action_utility_comparison(1)  # Diabetes ID = 1
    for item in diabetes_comparison:
        print(f"  - {item['action_name']}: Net Utility = {item['net_utility']:.3f}")

    # Test state distribution
    print("\nState Distribution:")
    state_dist = get_state_distribution()
    for item in state_dist:
        print(f"  - {item['disease_name']} - {item['state_name']}: {item['patient_count']} patients")

    # Test loading a specific patient
    test_patient = "P001"
    print(f"\nLoading patient {test_patient}:")
    disease_model = load_disease_model(test_patient)
    print(f"  Disease Model: {disease_model.states}")
    
    actions = load_actions(test_patient)
    print(f"  Actions ({len(actions)}):")
    for action in actions:
        print(f"    - {action.name}: utility={action.immediate_utility:.3f}")

    # Test new detailed patient query
    print("\nDetailed Patient Data:")
    detailed = get_all_patients_detailed()
    for patient in detailed:
        print(f"  - {patient['patient_id']}: {patient['first_name']} {patient['last_name']} - "
              f"Severity: {patient['severity_level']}, Model: {patient['model_version']}")

    print("\nDatabase ready!")
