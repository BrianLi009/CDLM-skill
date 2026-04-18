"""
JSON schemas for CDLM tool handlers.

These follow the OpenAI / Anthropic function-calling schema shape and can be
adapted to any agent framework. Each schema describes one callable in
``cdlm.session.HANDLERS``.

Usage example (Anthropic Claude API)::

    from cdlm.schemas import ALL_SCHEMAS
    from cdlm.session import HANDLERS

    anthropic_tools = [
        {
            "name": s["name"],
            "description": s["description"],
            "input_schema": s["parameters"],
        }
        for s in ALL_SCHEMAS
    ]
"""

CDLM_INIT_SCHEMA = {
    "name": "cdlm_init",
    "description": (
        "Initialize a CDLM (Conflict-Driven Learning) session for a reasoning "
        "problem. Provide the problem statement as text. The reasoning tree "
        "starts empty; you drive each phase by calling cdlm_propagate / "
        "cdlm_conflict_check / cdlm_decide / cdlm_solution_check / "
        "cdlm_backtrack."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "problem_text": {
                "type": "string",
                "description": "The full problem statement to solve.",
            },
            "problem_type": {
                "type": "string",
                "description": "Optional label for the problem type (e.g. 'sudoku', 'general').",
                "default": "general",
            },
        },
        "required": ["problem_text"],
    },
}

CDLM_PROPAGATE_SCHEMA = {
    "name": "cdlm_propagate",
    "description": (
        "Add implications you have derived from the current reasoning tree. "
        "Pass a list of {text, reasoning, parents} objects. Each deduction "
        "must be atomic (one claim per item) and must cite the IDs of the "
        "existing nodes that support it (use [] for the initial level-0 "
        "givens that come directly from the problem statement). Can be "
        "called multiple times before checking for conflicts."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "deductions": {
                "type": "array",
                "description": "List of implications to add to the tree.",
                "items": {
                    "type": "object",
                    "properties": {
                        "text": {
                            "type": "string",
                            "description": "The atomic implication, e.g. 'Cell(0,1) = 2'.",
                        },
                        "reasoning": {
                            "type": "string",
                            "description": "Why this follows from the parents.",
                        },
                        "parents": {
                            "type": "array",
                            "items": {"type": "integer"},
                            "description": (
                                "Node IDs that jointly support this deduction. "
                                "Use [] for level-0 givens with no antecedents."
                            ),
                        },
                    },
                    "required": ["text", "parents"],
                },
            },
        },
        "required": ["deductions"],
    },
}

CDLM_CONFLICT_CHECK_SCHEMA = {
    "name": "cdlm_conflict_check",
    "description": (
        "Record whether you have identified a contradiction in the reasoning "
        "tree. If is_conflict=True, you MUST supply 'parents' — the node IDs "
        "whose joint claims produce the contradiction (these seed the "
        "conflict analysis). After a conflict, the only legal next action is "
        "cdlm_backtrack."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "is_conflict": {
                "type": "boolean",
                "description": "True if a contradiction has been identified.",
            },
            "reasoning": {
                "type": "string",
                "description": "Explanation of the contradiction (or why none exists).",
            },
            "parents": {
                "type": "array",
                "items": {"type": "integer"},
                "description": (
                    "Required when is_conflict=True. Node IDs that jointly "
                    "cause the contradiction."
                ),
            },
        },
        "required": ["is_conflict"],
    },
}

CDLM_DECIDE_SCHEMA = {
    "name": "cdlm_decide",
    "description": (
        "Add a caller-chosen assumption to the tree to explore the search "
        "space. A decision opens a new decision level. Only available after "
        "cdlm_conflict_check finds no conflict. Prefer the highest-information "
        "decision (the claim whose resolution most reshapes the tree)."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "text": {
                "type": "string",
                "description": "The assumption, e.g. 'Cell(1,2) = 1'.",
            },
            "reasoning": {
                "type": "string",
                "description": "Why this is a good decision to try.",
            },
        },
        "required": ["text"],
    },
}

CDLM_SOLUTION_CHECK_SCHEMA = {
    "name": "cdlm_solution_check",
    "description": (
        "Record whether the current reasoning tree constitutes a complete "
        "solution. Only available after cdlm_conflict_check finds no "
        "conflict. If is_solution=True, supply solution_text with the final "
        "answer."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "is_solution": {
                "type": "boolean",
                "description": "True if the problem is solved.",
            },
            "reasoning": {
                "type": "string",
                "description": "Explanation of why the tree is (not) a complete solution.",
            },
            "solution_text": {
                "type": "string",
                "description": "Required when is_solution=True. The final answer.",
            },
        },
        "required": ["is_solution"],
    },
}

CDLM_BACKTRACK_SCHEMA = {
    "name": "cdlm_backtrack",
    "description": (
        "After a conflict, run conflict analysis (1-UIP / learned clause / "
        "backjump level is computed deterministically from the tree), drop "
        "every node above the backjump level, and store the caller-supplied "
        "lemma so future propagations are informed by it. The lemma should be "
        "a concise constraint that prevents this conflict from recurring "
        "(e.g. 'Cell(1,2) != 1')."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "lemma": {
                "type": "string",
                "description": "Concise human-readable constraint learned from the conflict.",
            },
        },
        "required": ["lemma"],
    },
}

CDLM_STATUS_SCHEMA = {
    "name": "cdlm_status",
    "description": (
        "Show the current CDLM session state: problem, reasoning tree, "
        "current state, and allowed next actions."
    ),
    "parameters": {
        "type": "object",
        "properties": {},
        "required": [],
    },
}

ALL_SCHEMAS = [
    CDLM_INIT_SCHEMA,
    CDLM_PROPAGATE_SCHEMA,
    CDLM_CONFLICT_CHECK_SCHEMA,
    CDLM_DECIDE_SCHEMA,
    CDLM_SOLUTION_CHECK_SCHEMA,
    CDLM_BACKTRACK_SCHEMA,
    CDLM_STATUS_SCHEMA,
]
