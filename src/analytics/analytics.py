from __future__ import annotations
from typing import List, Dict, Any, Tuple
from dataclasses import dataclass


@dataclass
class ActionComparison:
    """Result of comparing actions by net utility"""
    action_name: str
    avg_benefit: float
    avg_risk: float
    avg_cost: float
    net_utility: float


@dataclass
class StateDistributionResult:
    """Result of state distribution analysis"""
    disease_name: str
    state_name: str
    severity_level: int
    patient_count: int
    is_success: bool  # severity_level <= 2 considered success


def compare_actions(actions_data) -> List[ActionComparison]:
    """
    Ranks actions by net utility.

    Supports either:
    - dict rows with keys like action_name / avg_benefit / avg_risk / avg_cost / net_utility
    - tuple rows from get_actions_for_patient(), expected as:
      (name, description, benefit, risk, cost, improve, worsen, delta)
    """
    comparisons = []

    for action in actions_data:
        # Case 1: dictionary format
        if isinstance(action, dict):
            comparisons.append(ActionComparison(
                action_name=action["action_name"],
                avg_benefit=action["avg_benefit"],
                avg_risk=action["avg_risk"],
                avg_cost=action["avg_cost"],
                net_utility=action["net_utility"]
            ))

        # Case 2: tuple/list format from get_actions_for_patient()
        elif isinstance(action, (tuple, list)) and len(action) >= 5:
            name = action[0]
            benefit = action[2]
            risk = action[3]
            cost = action[4]
            net_utility = benefit - risk - cost

            comparisons.append(ActionComparison(
                action_name=name,
                avg_benefit=benefit,
                avg_risk=risk,
                avg_cost=cost,
                net_utility=net_utility
            ))

    return sorted(comparisons, key=lambda x: x.net_utility, reverse=True)


def state_success_rate(state_distribution: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Computes percentage of patients in successful states (severity_level <= 2).
    
    Args:
        state_distribution: List of dicts from get_state_distribution()
        
    Returns:
        Dict with overall success rate and per-disease breakdown
    """
    disease_stats = {}
    total_patients = 0
    total_success = 0
    
    for item in state_distribution:
        disease = item["disease_name"]
        count = item["patient_count"]
        is_success = item["severity_level"] <= 2
        
        if disease not in disease_stats:
            disease_stats[disease] = {"total": 0, "success": 0}
        
        disease_stats[disease]["total"] += count
        if is_success:
            disease_stats[disease]["success"] += count
            total_success += count
        
        total_patients += count
    
    # Calculate percentages
    result = {
        "overall": {
            "success_count": total_success,
            "total_patients": total_patients,
            "success_rate": round(total_success / total_patients * 100, 2) if total_patients > 0 else 0
        },
        "by_disease": {}
    }
    
    for disease, stats in disease_stats.items():
        result["by_disease"][disease] = {
            "success_count": stats["success"],
            "total_patients": stats["total"],
            "success_rate": round(stats["success"] / stats["total"] * 100, 2) if stats["total"] > 0 else 0
        }
    
    return result


def most_common_actions_by_utility(actions_comparison: List[ActionComparison]) -> List[ActionComparison]:
    """
    Returns the most effective actions based on utility model.
    Since we don't have a treatment_log table, this uses the utility model
    to determine which actions are theoretically most effective.
    
    Args:
        actions_comparison: List of ActionComparison from compare_actions()
        
    Returns:
        Top 3 actions by net utility
    """
    return actions_comparison[:3] if len(actions_comparison) >= 3 else actions_comparison


def get_top_action_recommendation(actions_comparison: List[ActionComparison]) -> str:
    """Returns the name of the highest-ranked action"""
    if actions_comparison:
        return actions_comparison[0].action_name
    return "No actions available"


def get_disease_summary(disease_id: int, actions_data: List[Dict], distribution_data: List[Dict]) -> Dict[str, Any]:
    """
    Generates a comprehensive summary for a disease.
    
    Args:
        disease_id: Disease ID to summarize
        actions_data: From get_action_utility_comparison()
        distribution_data: From get_state_distribution()
        
    Returns:
        Dictionary with disease insights
    """
    comparisons = compare_actions(actions_data)
    success_rates = state_success_rate(distribution_data)
    
    # Find this disease in distribution
    disease_name = None
    disease_success_rate = 0
    for disease, stats in success_rates["by_disease"].items():
        if disease_name is None:
            disease_name = disease
            disease_success_rate = stats["success_rate"]
    
    return {
        "disease_name": disease_name,
        "top_action": get_top_action_recommendation(comparisons),
        "top_actions": [(a.action_name, a.net_utility) for a in comparisons[:3]],
        "success_rate": disease_success_rate,
        "total_patients": success_rates["overall"]["total_patients"]
    }