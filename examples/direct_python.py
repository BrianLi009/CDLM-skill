"""
Drive the CDLM loop directly from Python — useful for testing or for
non-agent workflows where you want to script the reasoning yourself.

Runs a tiny 4-cell toy problem end to end: givens → propagation → decision →
conflict → backtrack → solution.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cdlm import (
    cdlm_init,
    cdlm_propagate,
    cdlm_conflict_check,
    cdlm_decide,
    cdlm_solution_check,
    cdlm_backtrack,
    cdlm_status,
)


def show(label: str, payload: str) -> dict:
    data = json.loads(payload)
    print(f"\n--- {label} ---")
    print(json.dumps(data, indent=2))
    return data


def main() -> None:
    # Toy problem: 4 cells (A, B, C, D), each must hold a distinct value from
    # {1, 2}. A = 1 is given. Find an assignment; demonstrate a conflict and
    # recovery along the way.
    show("init", cdlm_init(
        problem_text="Cells A, B, C, D each hold a distinct value from {1, 2}. A = 1 is given.",
    ))

    # Level 0 givens
    show("propagate level 0", cdlm_propagate(deductions=[
        {"text": "A = 1", "reasoning": "given", "parents": []},
        {"text": "Values are drawn from {1, 2}", "reasoning": "given", "parents": []},
    ]))

    show("conflict_check (none)", cdlm_conflict_check(
        is_conflict=False, reasoning="no contradiction yet",
    ))

    show("solution_check (not solved)", cdlm_solution_check(
        is_solution=False, reasoning="B, C, D not yet assigned",
    ))

    # Decision: assume B = 1 (this will conflict with A = 1 because of distinctness)
    show("decide B=1", cdlm_decide(
        text="B = 1", reasoning="try B = 1 first",
    ))

    # Propagate — B = 1 contradicts A = 1 under distinctness
    show("propagate after decision", cdlm_propagate(deductions=[
        {
            "text": "A and B both equal 1",
            "reasoning": "A=1 from node 0, B=1 from node 2",
            "parents": [0, 2],
        },
    ]))

    # Conflict: violates distinctness
    show("conflict_check (conflict)", cdlm_conflict_check(
        is_conflict=True,
        reasoning="A and B must be distinct but both equal 1",
        parents=[0, 2],
    ))

    # Backtrack with a learned lemma
    show("backtrack", cdlm_backtrack(
        lemma="B != 1",
    ))

    # Re-propagate with lemma installed; now B must be 2
    show("propagate with lemma", cdlm_propagate(deductions=[
        {"text": "B = 2", "reasoning": "B != 1 (lemma) and B in {1,2}", "parents": [0, 1]},
    ]))

    show("conflict_check (none)", cdlm_conflict_check(
        is_conflict=False, reasoning="A=1, B=2 distinct so far",
    ))

    show("solution_check (not solved)", cdlm_solution_check(
        is_solution=False, reasoning="C, D still unassigned",
    ))

    # Note: this toy problem is under-specified (only 2 values for 4 cells)
    # so there is no actual full solution — in a real problem you would now
    # continue deciding on C, D until cdlm_solution_check(is_solution=True).
    print("\n--- Final status ---")
    print(json.loads(cdlm_status())["tree"])


if __name__ == "__main__":
    main()
