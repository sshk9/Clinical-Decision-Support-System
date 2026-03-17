import sqlite3
from typing import List, Tuple, Any
import numpy as np

def get_connection():
    """Get a database connection"""
    return sqlite3.connect("cdss.db")

def init_db():
    """
    Initialize all database tables using IF NOT EXISTS.
    Order matters due to foreign key constraints.
    """
    with get_connection() as conn:
        # Enable foreign key support
        conn.execute("PRAGMA foreign_keys = ON")
        
        # 1. disease table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS disease (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                description TEXT
            )
        """)
        
        # 2. disease_state table
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
        
        # 3. markov_model table
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
        
        # 4. markov_transition table
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
        
        # 5. action table
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
        
        # 6. action_utility table
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
        
        # 7. patient table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS patient (
                id TEXT PRIMARY KEY,
                first_name TEXT NOT NULL,
                last_name TEXT NOT NULL
            )
        """)
        
        # 8. patient_status table
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
        
        conn.commit()
        print("Database tables initialized successfully")

def seed_data():
    """
    Seed the database with demo data from the codebase:
    - Simple progression disease model
    - Default actions
    - Demo patients
    """
    with get_connection() as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        
        # First, clear existing data (for clean reseeding)
        conn.execute("DELETE FROM patient_status")
        conn.execute("DELETE FROM patient")
        conn.execute("DELETE FROM action_utility")
        conn.execute("DELETE FROM action")
        conn.execute("DELETE FROM markov_transition")
        conn.execute("DELETE FROM markov_model")
        conn.execute("DELETE FROM disease_state")
        conn.execute("DELETE FROM disease")
        
        # 1. Insert disease
        conn.execute("""
            INSERT INTO disease (name, description) VALUES (?, ?)
        """, ("Simple Progression", "Three-state linear disease: Healthy -> Mild -> Severe"))
        disease_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        
        # 2. Insert disease states (from make_simple_progression)
        states = ["Healthy", "Mild", "Severe"]
        severity_map = {"Healthy": 1, "Mild": 3, "Severe": 5}
        state_ids = {}
        
        for state in states:
            conn.execute("""
                INSERT INTO disease_state (disease_id, state_name, severity_level)
                VALUES (?, ?, ?)
            """, (disease_id, state, severity_map[state]))
            state_ids[state] = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        
        # 3. Insert Markov model
        conn.execute("""
            INSERT INTO markov_model (disease_id, model_name, version, is_active)
            VALUES (?, ?, ?, ?)
        """, (disease_id, "Simple Progression Model", "1.0.0", 1))
        model_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        
        # 4. Insert transition probabilities (from make_simple_progression)
        # Matrix: [[0.85, 0.10, 0.05],
        #          [0.10, 0.70, 0.20],
        #          [0.05, 0.15, 0.80]]
        transitions = [
            ("Healthy", "Healthy", 0.85),
            ("Healthy", "Mild", 0.10),
            ("Healthy", "Severe", 0.05),
            ("Mild", "Healthy", 0.10),
            ("Mild", "Mild", 0.70),
            ("Mild", "Severe", 0.20),
            ("Severe", "Healthy", 0.05),
            ("Severe", "Mild", 0.15),
            ("Severe", "Severe", 0.80),
        ]
        
        for from_state, to_state, prob in transitions:
            conn.execute("""
                INSERT INTO markov_transition (model_id, from_state_id, to_state_id, probability)
                VALUES (?, ?, ?, ?)
            """, (model_id, state_ids[from_state], state_ids[to_state], prob))
        
        # 5. Insert actions (from make_default_actions)
        actions_data = [
            ("Watch and Wait", 
             "No intervention. Monitor patient and reassess at next visit.",
             None, None, 0.0),
            ("Prescribe Medication",
             "Standard pharmacological treatment to slow disease progression.",
             "Healthy", "Severe", 0.1),
            ("Lifestyle Intervention",
             "Diet, exercise, and behavioural changes to support recovery.",
             "Mild", "Severe", 0.05),
            ("Refer to Specialist",
             "Escalate care to a specialist for advanced treatment options.",
             "Healthy", "Severe", 0.15),
        ]
        
        action_ids = {}
        for name, desc, improve, worsen, delta in actions_data:
            conn.execute("""
                INSERT INTO action (disease_id, action_name, description, improve_state, worsen_state, delta)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (disease_id, name, desc, improve, worsen, delta))
            action_ids[name] = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        
        # 6. Insert action utilities
        # Break down immediate_utility into components:
        # Watch and Wait: 0.2 -> benefit=0.3, risk=0.05, cost=0.05
        # Prescribe Medication: 0.6 -> benefit=0.8, risk=0.1, cost=0.1
        # Lifestyle Intervention: 0.4 -> benefit=0.6, risk=0.1, cost=0.1
        # Refer to Specialist: 0.5 -> benefit=0.7, risk=0.1, cost=0.1
        
        utility_components = {
            "Watch and Wait": {"benefit": 0.3, "risk": 0.05, "cost": 0.05},
            "Prescribe Medication": {"benefit": 0.8, "risk": 0.1, "cost": 0.1},
            "Lifestyle Intervention": {"benefit": 0.6, "risk": 0.1, "cost": 0.1},
            "Refer to Specialist": {"benefit": 0.7, "risk": 0.1, "cost": 0.1},
        }
        
        for state_name in states:
            state_id = state_ids[state_name]
            for action_name, components in utility_components.items():
                action_id = action_ids[action_name]
                conn.execute("""
                    INSERT INTO action_utility (disease_id, state_id, action_id, expected_benefit, complication_risk, side_effect_cost)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (disease_id, state_id, action_id, 
                      components["benefit"], components["risk"], components["cost"]))
        
        # 7. Insert patients (from _load_demo_data)
        patients = [
            ("P001", "John", "Smith", "Mild"),
            ("P002", "Maria", "Klein", "Severe"),
            ("P003", "Lucas", "Mitchell", "Healthy"),
        ]
        
        for patient_id, first, last, state in patients:
            conn.execute("""
                INSERT INTO patient (id, first_name, last_name)
                VALUES (?, ?, ?)
            """, (patient_id, first, last))
            
            conn.execute("""
                INSERT INTO patient_status (patient_id, disease_id, current_state_id, active_model_id)
                VALUES (?, ?, ?, ?)
            """, (patient_id, disease_id, state_ids[state], model_id))
        
        conn.commit()
        print(f"Database seeded successfully with {len(states)} states, {len(actions_data)} actions, and {len(patients)} patients")

# ============================================================
# QUERY FUNCTIONS - Interface for Member B
# ============================================================

def get_all_patients() -> List[Tuple[str, str, str]]:
    """
    Returns a list of (patient_id, full_name, current_state)
    
    Example return:
    [
        ("P001", "John Smith", "Mild"),
        ("P002", "Maria Klein", "Severe"),
        ("P003", "Lucas Mitchell", "Healthy")
    ]
    """
    with get_connection() as conn:
        cursor = conn.execute("""
            SELECT 
                p.id,
                p.first_name || ' ' || p.last_name as full_name,
                ds.state_name as current_state
            FROM patient p
            JOIN patient_status ps ON p.id = ps.patient_id
            JOIN disease_state ds ON ps.current_state_id = ds.id
            ORDER BY p.id
        """)
        return cursor.fetchall()

def get_model_for_patient(patient_id: str) -> Tuple[List[str], List[List[float]]]:
    """
    Returns (state_names, transition_matrix) for the patient's active model.
    
    Args:
        patient_id: The patient's ID (e.g., "P001")
    
    Returns:
        state_names: List of state names in order
        transition_matrix: 2D list of probabilities where matrix[i][j] is prob from state i to j
    
    Example:
        (["Healthy", "Mild", "Severe"], 
         [[0.85, 0.10, 0.05],
          [0.10, 0.70, 0.20],
          [0.05, 0.15, 0.80]])
    """
    with get_connection() as conn:
        # Get the active model for the patient
        cursor = conn.execute("""
            SELECT active_model_id
            FROM patient_status
            WHERE patient_id = ?
        """, (patient_id,))
        result = cursor.fetchone()
        if not result:
            return [], []
        
        model_id = result[0]
        
        # Get all state names for this disease in order
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
        
        # Initialize matrix with zeros
        n = len(state_names)
        matrix = [[0.0] * n for _ in range(n)]
        
        # Get all transitions for this model
        cursor = conn.execute("""
            SELECT from_state_id, to_state_id, probability
            FROM markov_transition
            WHERE model_id = ?
        """, (model_id,))
        
        for from_id, to_id, prob in cursor.fetchall():
            from_idx = state_id_to_index[from_id]
            to_idx = state_id_to_index[to_id]
            matrix[from_idx][to_idx] = prob
        
        return state_names, matrix

def get_actions_for_patient(patient_id: str) -> List[Tuple[str, str, float, float, float, str, str, float]]:
    """
    Returns list of actions available for the patient's current state.
    
    Args:
        patient_id: The patient's ID (e.g., "P001")
    
    Returns:
        List of tuples: (action_name, description, expected_benefit, complication_risk, 
                        side_effect_cost, improve_state, worsen_state, delta)
    
    Note: 
        - The utility components are for the patient's CURRENT state
        - improve_state and worsen_state may be None (Python None) for actions 
          that don't modify transition probabilities
    """
    with get_connection() as conn:
        # Get patient's current state and disease
        cursor = conn.execute("""
            SELECT ps.disease_id, ps.current_state_id
            FROM patient_status ps
            WHERE ps.patient_id = ?
        """, (patient_id,))
        result = cursor.fetchone()
        if not result:
            return []
        
        disease_id, current_state_id = result
        
        # Get all actions with their utilities for the current state
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

# ============================================================
# Safety check for direct execution
# ============================================================

if __name__ == "__main__":
    print("Initializing database...")
    init_db()
    print("Seeding data...")
    seed_data()
    
    # Verify the data
    print("\nVerification:")
    patients = get_all_patients()
    print(f"Found {len(patients)} patients:")
    for patient_id, full_name, state in patients:
        print(f"  • {patient_id}: {full_name} - {state}")
        
        # Show model for first patient
        if patient_id == "P001":
            states, matrix = get_model_for_patient(patient_id)
            print(f"\n  Model for {full_name}:")
            print(f"  States: {states}")
            print("  Transition matrix:")
            for row in matrix:
                print(f"    {row}")
        
        # Show actions
        actions = get_actions_for_patient(patient_id)
        print(f"\n  Available actions for {full_name}:")
        for action in actions[:2]:  # Show first 2 actions as sample
            action_name, desc, benefit, risk, cost, improve, worsen, delta = action
            improve_str = improve if improve is not None else "None"
            worsen_str = worsen if worsen is not None else "None"
            print(f"    • {action_name}: benefit={benefit}, risk={risk}, cost={cost}, improve={improve_str}, worsen={worsen_str}")
    
    print("\nDatabase ready!")
