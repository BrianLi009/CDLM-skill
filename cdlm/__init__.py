"""CDLM — Conflict-Driven Learning Method.

Framework-agnostic implementation of a CDCL-style reasoning engine. The host
agent is the reasoning engine; this package provides the state-machine
bookkeeping and deterministic conflict analysis (1-UIP / learned clause /
backjump level).
"""

from .problem_structure import (
    Problem,
    Tree,
    Node,
    Deduction,
    Decision,
    Conflict,
    Solution,
)
from .conflict_analysis import ConflictAnalyzer
from .session import (
    HANDLERS,
    STATES,
    VALID_TRANSITIONS,
    cdlm_init,
    cdlm_propagate,
    cdlm_conflict_check,
    cdlm_decide,
    cdlm_solution_check,
    cdlm_backtrack,
    cdlm_status,
)
from .schemas import ALL_SCHEMAS

__version__ = "0.2.0"

__all__ = [
    "Problem", "Tree", "Node",
    "Deduction", "Decision", "Conflict", "Solution",
    "ConflictAnalyzer",
    "HANDLERS", "STATES", "VALID_TRANSITIONS", "ALL_SCHEMAS",
    "cdlm_init", "cdlm_propagate", "cdlm_conflict_check",
    "cdlm_decide", "cdlm_solution_check", "cdlm_backtrack",
    "cdlm_status",
]
