"""
Dev Buddy – planner.py
Maakt een simpel stappenplan uit een spec.
"""

from typing import List, Dict, Any

def make_plan(spec: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Zet spec['goals'] om naar een lijst stappen:
    [{step: 1, task: "...", status: "todo"}, ...]
    """
    goals = spec.get("goals", []) or []
    plan = []
    for i, g in enumerate(goals, start=1):
        task = str(g).strip()
        if task:
            plan.append({"step": i, "task": task, "status": "todo"})
    return plan

def mark_done(plan: List[Dict[str, Any]], step_no: int) -> None:
    """
    Zet de status van een stap op 'done' (in-place).
    Doet niks als step_no niet bestaat.
    """
    for item in plan:
        if item.get("step") == step_no:
            item["status"] = "done"
            break
