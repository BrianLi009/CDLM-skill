"""
CDLM session — pure-Python state machine and handlers.

This module exposes seven callable handlers that together implement the CDLM
solver loop. They are framework-agnostic: every handler takes plain Python
arguments and returns a JSON string. Any agent framework that can dispatch
tool calls (Anthropic Claude API tool use, MCP, LangChain, a custom REPL,
etc.) can wire these handlers to its tool registry using the JSON schemas in
``cdlm.schemas``.

Handlers:

* ``cdlm_init(problem_text, problem_type="general")``
* ``cdlm_propagate(deductions)``
* ``cdlm_conflict_check(is_conflict, reasoning="", parents=None)``
* ``cdlm_decide(text, reasoning="")``
* ``cdlm_solution_check(is_solution, reasoning="", solution_text=None)``
* ``cdlm_backtrack(lemma)``
* ``cdlm_status()``

Every handler accepts an optional ``task_id`` keyword so a single process can
host multiple concurrent sessions. If omitted, the session key is ``"default"``.

State machine::

    INIT           → propagate
    PROPAGATED     → propagate, conflict_check
    NO_CONFLICT    → propagate, solution_check, decide
    CONFLICT       → backtrack
    DECIDED        → propagate
    SOLVED         → (terminal)

Calling a handler in the wrong state returns an error JSON with the allowed
actions; the session state is not mutated.
"""

import json
import logging
from typing import Any, Dict, List, Optional

from .problem_structure import Tree, Problem, Deduction, Decision, Conflict, Solution
from .conflict_analysis import ConflictAnalyzer

logger = logging.getLogger(__name__)

STATES = {"INIT", "PROPAGATED", "NO_CONFLICT", "CONFLICT", "DECIDED", "SOLVED"}

VALID_TRANSITIONS = {
    "INIT":        {"propagate"},
    "PROPAGATED":  {"propagate", "conflict_check"},
    "NO_CONFLICT": {"propagate", "solution_check", "decide"},
    "CONFLICT":    {"backtrack"},
    "DECIDED":     {"propagate"},
}


_sessions: Dict[str, Dict[str, Any]] = {}


def _get_session(task_id: str) -> Optional[Dict[str, Any]]:
    return _sessions.get(task_id)


def _validate_transition(session: Dict[str, Any], action: str) -> Optional[str]:
    state = session["state"]
    if state == "SOLVED":
        return "Session is already solved. Start a new session with cdlm_init."
    allowed = VALID_TRANSITIONS.get(state, set())
    if action not in allowed:
        return (
            f"Invalid action '{action}' in state '{state}'. "
            f"Allowed actions: {sorted(allowed)}"
        )
    return None


def _allowed_actions(session: Dict[str, Any]) -> List[str]:
    return sorted(VALID_TRANSITIONS.get(session["state"], set()))


def _tree_summary(session: Dict[str, Any]) -> str:
    tree = session["tree"]
    return (
        f"State: {session['state']} | Nodes: {len(tree.nodes)} | "
        f"Decision level: {tree.curr_decision_level}"
    )


def _err(message: str, session: Optional[Dict[str, Any]] = None) -> str:
    payload: Dict[str, Any] = {"error": message}
    if session is not None:
        payload["status"] = _tree_summary(session)
        payload["allowed_actions"] = _allowed_actions(session)
    return json.dumps(payload)


def cdlm_init(problem_text: str, problem_type: str = "general", **kwargs) -> str:
    task_id = kwargs.get("task_id", "default")

    if not problem_text or not problem_text.strip():
        return _err("problem_text is required and cannot be empty.")

    problem = Problem(problem_text)
    tree = Tree()
    # Default Tree starts at curr_decision_level=1; we want the first
    # propagation batch (level-0 givens) to file at level 0.
    tree.curr_decision_level = 0

    session = {
        "problem": problem,
        "tree": tree,
        "problem_type": problem_type,
        "state": "INIT",
        "iteration": 0,
    }
    _sessions[task_id] = session

    return json.dumps({
        "success": True,
        "message": f"CDLM session initialized for problem type '{problem_type}'.",
        "problem": str(problem),
        "status": _tree_summary(session),
        "allowed_actions": _allowed_actions(session),
    })


def cdlm_propagate(deductions: List[Dict[str, Any]], **kwargs) -> str:
    task_id = kwargs.get("task_id", "default")
    session = _get_session(task_id)
    if not session:
        return _err("No active CDLM session. Call cdlm_init first.")

    err = _validate_transition(session, "propagate")
    if err:
        return _err(err, session)

    if deductions is None:
        deductions = []
    if not isinstance(deductions, list):
        return _err("deductions must be a list of {text, reasoning, parents} dicts.", session)

    tree = session["tree"]

    parsed: List[Any] = []
    for i, d in enumerate(deductions):
        if not isinstance(d, dict):
            return _err(f"deductions[{i}] must be a dict, got {type(d).__name__}.", session)
        text = d.get("text")
        if not text:
            return _err(f"deductions[{i}].text is required.", session)
        reasoning = d.get("reasoning", "")
        parents = d.get("parents", []) or []
        if not isinstance(parents, list) or not all(isinstance(p, int) for p in parents):
            return _err(f"deductions[{i}].parents must be a list of integers.", session)
        try:
            parsed.append(Deduction(text=text, reasoning=reasoning, parents=parents))
        except Exception as exc:
            return _err(f"deductions[{i}] failed validation: {exc}", session)

    nodes_before = set(tree.nodes.keys())
    tree.append_deductions(parsed)
    nodes_after = set(tree.nodes.keys())
    new_ids = sorted(nodes_after - nodes_before)

    session["state"] = "PROPAGATED"

    return json.dumps({
        "success": True,
        "deductions_submitted": len(parsed),
        "deductions_added": len(new_ids),
        "new_node_ids": new_ids,
        "status": _tree_summary(session),
        "allowed_actions": _allowed_actions(session),
        "tree": str(tree),
    })


def cdlm_conflict_check(
    is_conflict: bool,
    reasoning: str = "",
    parents: Optional[List[int]] = None,
    **kwargs,
) -> str:
    task_id = kwargs.get("task_id", "default")
    session = _get_session(task_id)
    if not session:
        return _err("No active CDLM session. Call cdlm_init first.")

    err = _validate_transition(session, "conflict_check")
    if err:
        return _err(err, session)

    if not isinstance(is_conflict, bool):
        return _err("is_conflict must be a boolean.", session)

    tree = session["tree"]

    if is_conflict:
        if not parents:
            return _err(
                "is_conflict=True requires a non-empty 'parents' list "
                "containing the node IDs that jointly cause the conflict.",
                session,
            )
        if not isinstance(parents, list) or not all(isinstance(p, int) for p in parents):
            return _err("parents must be a list of integers.", session)
        missing = [p for p in parents if p not in tree.nodes]
        if missing:
            return _err(
                f"parents reference unknown node IDs: {missing}. "
                f"Existing IDs: {sorted(tree.nodes.keys())}",
                session,
            )

        conflict = Conflict(
            reasoning=reasoning or "",
            is_conflict=True,
            parents=list(parents),
        )
        tree.append_deductions(conflict)
        session["state"] = "CONFLICT"
        return json.dumps({
            "success": True,
            "is_conflict": True,
            "reasoning": reasoning or "",
            "conflict_node_id": tree.conflict_id,
            "message": "Conflict recorded. You MUST call cdlm_backtrack next.",
            "status": _tree_summary(session),
            "allowed_actions": _allowed_actions(session),
            "tree": str(tree),
        })

    session["state"] = "NO_CONFLICT"
    return json.dumps({
        "success": True,
        "is_conflict": False,
        "reasoning": reasoning or "",
        "message": "No conflict. You can propagate more, check for a solution, or make a decision.",
        "status": _tree_summary(session),
        "allowed_actions": _allowed_actions(session),
    })


def cdlm_decide(text: str, reasoning: str = "", **kwargs) -> str:
    task_id = kwargs.get("task_id", "default")
    session = _get_session(task_id)
    if not session:
        return _err("No active CDLM session. Call cdlm_init first.")

    err = _validate_transition(session, "decide")
    if err:
        return _err(err, session)

    if not text or not text.strip():
        return _err("decision 'text' is required and cannot be empty.", session)

    tree = session["tree"]

    decision = Decision(reasoning=reasoning or "", text=text)
    nodes_before = set(tree.nodes.keys())
    tree.append_deductions(decision)
    nodes_after = set(tree.nodes.keys())
    new_ids = sorted(nodes_after - nodes_before)

    if not new_ids:
        return json.dumps({
            "success": False,
            "message": "Decision was not added (likely a duplicate of an existing node). Try a different decision.",
            "status": _tree_summary(session),
            "allowed_actions": _allowed_actions(session),
        })

    session["state"] = "DECIDED"
    return json.dumps({
        "success": True,
        "decision_node_id": new_ids[-1],
        "decision_text": text,
        "reasoning": reasoning or "",
        "decision_level": tree.curr_decision_level,
        "status": _tree_summary(session),
        "allowed_actions": _allowed_actions(session),
        "tree": str(tree),
    })


def cdlm_solution_check(
    is_solution: bool,
    reasoning: str = "",
    solution_text: Optional[str] = None,
    **kwargs,
) -> str:
    task_id = kwargs.get("task_id", "default")
    session = _get_session(task_id)
    if not session:
        return _err("No active CDLM session. Call cdlm_init first.")

    err = _validate_transition(session, "solution_check")
    if err:
        return _err(err, session)

    if not isinstance(is_solution, bool):
        return _err("is_solution must be a boolean.", session)

    if is_solution:
        if not solution_text or not solution_text.strip():
            return _err(
                "is_solution=True requires 'solution_text' (the final answer).",
                session,
            )
        session["state"] = "SOLVED"
        return json.dumps({
            "success": True,
            "is_solution": True,
            "solution": solution_text,
            "reasoning": reasoning or "",
            "message": "Problem solved. Session is terminal.",
            "status": _tree_summary(session),
            "allowed_actions": _allowed_actions(session),
        })

    return json.dumps({
        "success": True,
        "is_solution": False,
        "reasoning": reasoning or "",
        "message": "Not yet solved. Continue propagating or make a decision.",
        "status": _tree_summary(session),
        "allowed_actions": _allowed_actions(session),
    })


def cdlm_backtrack(lemma: str, **kwargs) -> str:
    task_id = kwargs.get("task_id", "default")
    session = _get_session(task_id)
    if not session:
        return _err("No active CDLM session. Call cdlm_init first.")

    err = _validate_transition(session, "backtrack")
    if err:
        return _err(err, session)

    if not lemma or not lemma.strip():
        return _err(
            "lemma is required: provide a concise constraint that prevents "
            "this conflict from recurring (e.g., 'Cell(1,2) != 1').",
            session,
        )

    tree = session["tree"]
    problem = session["problem"]

    if tree.conflict_id is None:
        return _err("No conflict to analyze (tree.conflict_id is None).", session)

    try:
        analyzer = ConflictAnalyzer(tree)
        learned_clause, uip_node_id, backjump_level = analyzer.analyze_conflict(
            tree.conflict_id
        )
    except Exception as exc:
        logger.exception("Conflict analysis failed: %s", exc)
        return _err(f"Conflict analysis failed: {type(exc).__name__}: {exc}", session)

    learned_clause_literals = [
        {"id": nid, "text": tree.nodes[nid].text, "level": tree.nodes[nid].decision_level}
        for nid in sorted(learned_clause)
        if nid in tree.nodes
    ]
    uip_text = tree.nodes[uip_node_id].text if uip_node_id in tree.nodes else None

    # Backjump: drop everything above the backjump level. Tree.remove_nodes
    # has a quirk where backjump_level==0 leaves curr_decision_level at 1
    # (so the next propagation batch would file at level 1 instead of 0);
    # snap it back here so level-0 propagations post-backjump file correctly.
    tree.remove_nodes(backjump_level)
    tree.curr_decision_level = backjump_level

    problem.lemmas.append(lemma)

    session["state"] = "PROPAGATED"

    return json.dumps({
        "success": True,
        "learned_lemma": lemma,
        "backjump_level": backjump_level,
        "uip_node_id": uip_node_id,
        "uip_text": uip_text,
        "learned_clause": learned_clause_literals,
        "message": (
            f"Backjumped to level {backjump_level}. Lemma stored: {lemma}"
        ),
        "status": _tree_summary(session),
        "allowed_actions": _allowed_actions(session),
        "tree": str(tree),
    })


def cdlm_status(**kwargs) -> str:
    task_id = kwargs.get("task_id", "default")
    session = _get_session(task_id)
    if not session:
        return _err("No active CDLM session. Call cdlm_init first.")

    return json.dumps({
        "state": session["state"],
        "allowed_actions": _allowed_actions(session),
        "problem": str(session["problem"]),
        "tree": str(session["tree"]),
        "status": _tree_summary(session),
    })


HANDLERS = {
    "cdlm_init": cdlm_init,
    "cdlm_propagate": cdlm_propagate,
    "cdlm_conflict_check": cdlm_conflict_check,
    "cdlm_decide": cdlm_decide,
    "cdlm_solution_check": cdlm_solution_check,
    "cdlm_backtrack": cdlm_backtrack,
    "cdlm_status": cdlm_status,
}
