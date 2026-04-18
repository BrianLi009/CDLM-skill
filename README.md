# CDLM Skill

**Conflict-Driven Learning Method** — a framework-agnostic agent skill for
long-horizon reasoning. Inspired by CDCL (Conflict-Driven Clause Learning)
SAT solvers, but general enough for any problem that needs systematic
exploration with the ability to revise assumptions: combinatorial puzzles,
root-cause analysis, investigations, system design, mathematical proofs,
planning under constraints, and more.

The idea: instead of reasoning in one shot, the agent maintains an explicit
DAG of claims and assumptions, actively hunts for contradictions, and
backtracks with a learned lemma when one is found. The lemma persists and
narrows the search space permanently.

## What's in this repo

```
CDLM-skill/
├── SKILL.md            # Agent-facing skill definition (Anthropic Skills format)
├── references/
│   ├── conflict-analysis.md    # 1-UIP algorithm with worked details
│   ├── worked-example.md       # 4×4 Sudoku trace (concrete)
│   └── abstract-example.md     # Incident root-cause trace (abstract)
├── cdlm/               # Pip-installable Python package
│   ├── problem_structure.py    # Problem / Tree / Node / Deduction
│   ├── conflict_analysis.py    # Deterministic 1-UIP / learned clause / backjump
│   ├── session.py              # Seven tool handlers + state machine
│   └── schemas.py              # JSON schemas for every handler
└── examples/
    ├── direct_python.py        # Drive the loop from plain Python
    └── anthropic_tool_use.py   # Wire up as Claude API tools
```

## Installation

```bash
pip install -e .
```

Requires Python 3.9+ and `pydantic>=2.0`.

## The Seven Handlers

| Tool | Purpose |
|------|---------|
| `cdlm_init(problem_text)`                                | Start a session. |
| `cdlm_propagate(deductions)`                             | Add implications you derived. |
| `cdlm_conflict_check(is_conflict, reasoning, parents)`   | Report contradiction (or not). |
| `cdlm_decide(text, reasoning)`                           | Open a new decision level. |
| `cdlm_solution_check(is_solution, solution_text)`        | Report completeness. |
| `cdlm_backtrack(lemma)`                                  | Run conflict analysis + backjump + store lemma. |
| `cdlm_status()`                                          | Inspect current session. |

State machine:

```
init → propagate* → conflict_check
                    ├── conflict  → backtrack → propagate* → ...
                    └── no conflict → solution_check | decide → propagate* → ...
```

Each handler returns a JSON string with the current state, the reasoning tree,
and the `allowed_actions` list. Illegal transitions return an error without
mutating state.

## Wiring it into an agent framework

The handlers are plain Python callables. The `cdlm.schemas.ALL_SCHEMAS` list
holds JSON schemas in the standard function-calling shape. Adapt as needed:

### Anthropic Claude API tool use

```python
import anthropic
from cdlm.session import HANDLERS
from cdlm.schemas import ALL_SCHEMAS

tools = [
    {"name": s["name"], "description": s["description"], "input_schema": s["parameters"]}
    for s in ALL_SCHEMAS
]

client = anthropic.Anthropic()
messages = [{"role": "user", "content": "Solve this 4×4 Sudoku: ..."}]

while True:
    resp = client.messages.create(
        model="claude-opus-4-7",
        max_tokens=4096,
        tools=tools,
        messages=messages,
        system=open("SKILL.md").read(),
    )
    messages.append({"role": "assistant", "content": resp.content})
    tool_uses = [b for b in resp.content if b.type == "tool_use"]
    if not tool_uses:
        break
    results = [
        {"type": "tool_result", "tool_use_id": tu.id,
         "content": HANDLERS[tu.name](**tu.input)}
        for tu in tool_uses
    ]
    messages.append({"role": "user", "content": results})
```

See [`examples/anthropic_tool_use.py`](examples/anthropic_tool_use.py) for a
runnable version.

### MCP, LangChain, custom registries

The handlers take plain kwargs and return JSON strings. Register them with
whatever dispatch mechanism your framework uses; the schemas in
`cdlm.schemas` translate directly to OpenAI-style function schemas,
Anthropic `input_schema`, MCP tool definitions, etc.

### Claude Code / Claude Agent SDK (skill-loading frameworks)

Copy `SKILL.md` and `references/` into a skill directory (e.g.
`.claude/skills/cdlm/`) and expose the seven handlers as tools via whatever
mechanism your runtime provides (custom MCP server, bundled tool definitions,
etc.). Skill auto-loading is handled by the `description` field in the SKILL
frontmatter.

## How the conflict analysis works

`cdlm_backtrack` computes three things from the implication graph, all
deterministically:

1. **1-UIP** (First Unique Implication Point) — the node at the conflict
   decision level such that every path from that level's decision to the
   conflict passes through it.
2. **Learned clause** — the set of literals (excluding level-0 givens) that
   jointly cause the conflict, obtained by resolution up to the 1-UIP.
3. **Backjump level** — the second-highest decision level in the learned
   clause, or 0 if only one level is present.

The analysis is deterministic *given the tree*. Because the tree itself is
constructed by the host LLM, runs on the same problem can differ if the LLM
cites different parents or orders propagations differently — but the math
on any fixed tree is reproducible.

See [`references/conflict-analysis.md`](references/conflict-analysis.md) for
the full algorithm with an example.

## Direct-Python usage

For testing or non-agent workflows you can drive the loop yourself:

```python
from cdlm import cdlm_init, cdlm_propagate, cdlm_conflict_check, cdlm_backtrack

cdlm_init(problem_text="Solve 4x4 sudoku...")
cdlm_propagate(deductions=[
    {"text": "Cell(0,0) = 1", "reasoning": "given", "parents": []},
    # ...
])
cdlm_conflict_check(is_conflict=False, reasoning="no contradiction yet")
# ...
```

See [`examples/direct_python.py`](examples/direct_python.py).

## License

MIT. See [LICENSE](LICENSE).
