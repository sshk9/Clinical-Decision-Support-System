"""
Basic unit tests for Clinical Decision Support System (CDSS)

Tests cover:
1. DiseaseModel validation (rows sum to 1)
2. Action.apply() matrix modification
3. DecisionEngine ranking order
4. Database patient loading
"""

import pytest
import numpy as np
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.domain.disease_model import DiseaseModel
from src.domain.action import Action
from src.domain.macro_state import MacroState
from src.decision_engine.engine import DecisionEngine
from src.infrastructure.database import (
    init_db, seed_data, get_all_patients,
    get_model_for_patient, get_actions_for_patient,
    get_connection
)


class TestDiseaseModel:
    """Tests for DiseaseModel validation"""
    
    def test_rejects_non_stochastic_matrix(self):
        """Test 1: DiseaseModel rejects matrix whose rows don't sum to 1"""
        states = ("Healthy", "Sick")
        
        # Matrix with rows that don't sum to 1
        bad_matrix = np.array([
            [0.8, 0.1],  # sums to 0.9
            [0.3, 0.3]   # sums to 0.6
        ])
        
        # Check that the ValueError is raised (message may vary)
        with pytest.raises(ValueError):
            DiseaseModel(states=states, P=bad_matrix)
        
        # This one should work (rows sum to 1)
        good_matrix = np.array([
            [0.8, 0.2],
            [0.3, 0.7]
        ])
        
        model = DiseaseModel(states=states, P=good_matrix)
        assert model is not None


class TestAction:
    """Tests for Action transformations"""
    
    def test_apply_modifies_transition_matrix(self):
        """Test 2: Action.apply() actually modifies the transition matrix"""
        # Create a simple model
        states = ("Healthy", "Sick")
        model = DiseaseModel(
            states=states,
            P=np.array([
                [0.9, 0.1],
                [0.2, 0.8]
            ])
        )
        
        # Create an action that moves probability from Sick to Healthy
        # Note: improve_state and worsen_state are provided, delta is set
        action = Action(
            name="Treatment",
            immediate_utility=0.5,
            description="Test action",
            improve_state="Healthy",
            worsen_state="Sick",
            delta=0.1
        )
        
        # Apply the action
        modified_model = action.apply(model)
        
        # Get the original and modified matrices
        original_P = model.P.copy()
        modified_P = modified_model.P
        
        # Assert they are different
        assert not np.array_equal(original_P, modified_P), \
            "Action should modify the transition matrix"
        
        # Specifically check that probability moved from Sick to Healthy
        sick_idx = model.index_of("Sick")
        healthy_idx = model.index_of("Healthy")
        
        # Original: from Sick to Healthy was 0.2
        # After moving 0.1: should be 0.3
        assert abs(modified_P[sick_idx, healthy_idx] - 0.3) < 1e-6, \
            "Probability should increase from Sick to Healthy"


class TestDecisionEngine:
    """Tests for DecisionEngine ranking"""
    
    def test_rank_actions_returns_sorted_results(self):
        """Test 3: DecisionEngine.rank_actions() returns actions sorted best-first"""
        # Create a simple model
        states = ("Healthy", "Mild", "Severe")
        model = DiseaseModel(
            states=states,
            P=np.array([
                [0.85, 0.10, 0.05],
                [0.10, 0.70, 0.20],
                [0.05, 0.15, 0.80]
            ])
        )
        
        # Create actions with different utilities
        # Note: improve_state and worsen_state default to None
        actions = [
            Action(name="Poor", immediate_utility=0.1, description="Low utility"),
            Action(name="Good", immediate_utility=0.9, description="High utility"),
            Action(name="Medium", immediate_utility=0.5, description="Medium utility"),
        ]
        
        # Create macro state
        macro_state = MacroState(model=model, current_state="Mild")
        
        # Create engine and rank actions
        engine = DecisionEngine()
        ranked = engine.rank_actions(macro_state, actions)
        
        # Assert they're sorted descending
        assert len(ranked) == 3
        # Fix: rank is not a name attribute - use the correct attribute access
        # The actions are already sorted by total_score
        assert ranked[0].total_score >= ranked[1].total_score >= ranked[2].total_score, \
            "Actions should be sorted best-first"
        
        # The action with highest immediate utility should rank first
        assert ranked[0].action.name == "Good", "Highest utility action should rank first"


class TestDatabase:
    """Tests for database functionality"""
    
    @pytest.fixture(autouse=True)
    def setup_database(self):
        """Set up a fresh in-memory database for each test"""
        self.test_db_path = "test_cdss.db"

        import src.infrastructure.database as db_module
        self.original_get_connection = db_module.get_connection
        
        # Use a test-specific connection with a unique file path
        def test_connection():
            import sqlite3
            return sqlite3.connect(self.test_db_path)
        
        db_module.get_connection = test_connection
        
        # Initialize and seed the test database
        init_db()
        seed_data()
        
        yield
        
        # Clean up - restore original connection
        db_module.get_connection = self.original_get_connection
        
        # Close any open connections and remove test database file
        import sqlite3
        try:
            conn = sqlite3.connect(self.test_db_path)
            conn.close()
            if os.path.exists(self.test_db_path):
                os.remove(self.test_db_path)
        except Exception:
            pass
    
    def test_get_all_patients_returns_seeded_data(self):
        """Test 4: get_all_patients() returns the 6 seeded patients"""
        patients = get_all_patients()
        
        # Should have exactly 6 patients
        assert len(patients) == 6, f"Expected 6 patients, got {len(patients)}"
        
        # Check patient IDs
        patient_ids = [p[0] for p in patients]
        assert "P001" in patient_ids
        assert "P002" in patient_ids
        assert "P003" in patient_ids
        assert "P004" in patient_ids
        assert "P005" in patient_ids
        assert "P006" in patient_ids
        
        # Check names and states for first patient
        for patient_id, name, state, disease in patients:
            if patient_id == "P001":
                assert name == "John Smith"
                assert state == "Normal"
                assert disease == "Type 2 Diabetes"
    
    def test_get_model_for_patient_returns_valid_matrix(self):
        """Additional test: verify model retrieval works"""
        patients = get_all_patients()
        assert len(patients) > 0
        
        patient_id = patients[0][0]
        state_names, matrix = get_model_for_patient(patient_id)
        
        # Verify matrix properties
        assert len(state_names) > 0
        assert len(matrix) == len(state_names)
        
        # Check rows sum to 1
        for i, row in enumerate(matrix):
            row_sum = sum(row)
            assert abs(row_sum - 1.0) < 1e-6, \
                f"Row {i} sums to {row_sum}, should be 1.0"
    
    def test_get_actions_for_patient_returns_actions(self):
        """Additional test: verify actions retrieval works"""
        patients = get_all_patients()
        assert len(patients) > 0
        
        patient_id = patients[0][0]
        actions = get_actions_for_patient(patient_id)
        
        # Should have 4 actions (from seed data)
        assert len(actions) == 4
        
        # Check action structure
        for action in actions:
            name, desc, benefit, risk, cost, improve, worsen, delta = action
            assert name is not None
            assert benefit >= 0
            assert risk >= 0
            assert cost >= 0
            assert 0 <= delta <= 1
