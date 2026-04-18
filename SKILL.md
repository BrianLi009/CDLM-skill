---
name: cdlm
description: >
  A conflict-driven method for long-horizon reasoning. Maintains an explicit
  DAG of claims and assumptions, detects contradictions or tensions, backtracks
  with learned constraints, and systematically explores the solution space. Use
  for any problem that requires multi-step reasoning with revisable assumptions:
  combinatorial puzzles, root-cause analysis, investigations, system design,
  mathematical proofs, planning under constraints, strategic choices, and
  case-based reasoning.
version: 0.2.0
author: Brian Li
tags: [reasoning, long-horizon, conflict-driven, cdcl, search, planning]
---

# CDLM — Certificate Driven Language Model

A general-purpose reasoning strategy inspired by CDCL (Conflict-Driven Clause
Learning) SAT solvers. Instead of reasoning in one shot, you maintain an
explicit **reasoning tree** and cycle through structured phases: deduce, check
for conflicts, backtrack with learned lessons, and make decisions to explore
new possibilities.

The framing is **conflict as a first-class signal**. Contradictions and
tensions aren't failure modes — they are the most informative events in the
whole trajectory, because each one reshapes what you'll explore next. You
can use this method at any abstraction level: from concrete atomic facts
("Cell(0,1) = 2") to high-level strategic commitments ("optimize for latency
over consistency"). The data structure doesn't care; the discipline is what
matters.

## When to Use

- **Combinatorial / constraint satisfaction**: Sudoku, N-Queens, scheduling, graph coloring
- **Logic puzzles and mathematical proofs** requiring case analysis
- **Root-cause analysis and debugging**: incidents, failures, bugs where hypotheses need testing
- **Investigations and research**: weighing competing explanations with evidence that may conflict
- **System design and planning**: choices where tradeoffs surface contradictions downstream
- **Strategic decisions** where early framing commitments can prove wrong and need revision
- Any problem where single-pass reasoning is unreliable and you need systematic exploration with the ability to revise

## When NOT to Use

- Simple factual lookups or one-shot questions
- Creative or open-ended generation where "correctness" is subjective
- Problems with a single obvious solution path needing no revision
- Tasks where an approximate answer is acceptable and precision isn't worth the overhead

## Core Concepts

### The Reasoning Tree

A directed acyclic graph where every node is a claim you've committed to.
Each node records:

- **ID**: unique integer, assigned in order (0, 1, 2, ...) — never recycled
- **Text**: the claim itself, at whatever abstraction level fits
- **Type**: IMPLICATION (follows from parents) or DECISION (chosen to explore)
- **Decision Level**: how many decisions deep this claim lives
- **Parents**: earlier node IDs that **support** this one

### Nodes

**Implications** are claims forced (or strongly supported) by what you already know:
> "Row 0 already has {1, 4}. Col 2 has {3}. Therefore Cell(0,2) = 2." (parents cite the row/col facts)
> "Latency spike began at 14:02 UTC, coinciding with the v2.5 deploy window." (parents cite the metric node and deploy-log node)

**Decisions** are commitments you make to open a branch of exploration:
> "Assume Cell(2,1) = 4." (concrete)
> "Frame this as a database-contention problem, not a networking problem." (abstract)

Decisions don't need parents — they're choices, not derivations.

**Conflicts** are contradictions between claims in the current tree:
> "Cell(3,2) must be both 3 and 2 — impossible." (hard logical conflict)
> "Hypothesis H predicts impacted endpoints share DB X, but 3 of 7 impacted endpoints never touch DB X." (empirical conflict)

### Decision Level vs Abstraction Level

**Decision level** is about search depth: level 0 = no assumptions, level N = N
decisions deep. It determines what gets undone on a backjump.

**Abstraction level** is about *kind* of claim: framing / strategic / tactical
/ concrete. CDLM doesn't have a separate field for this, but you control it
implicitly by **what you decide on first**.

> **Rule of thumb**: decide at the highest abstraction level that still
> meaningfully narrows the space. Commit to a frame before committing to a
> mechanism; commit to a mechanism before committing to a value. That way,
> backjumping retracts the *right-sized* commitment.

A level-1 decision that frames the problem ("assume regression stems from the
v2.5 deploy") will cascade into many level-2 tactical deductions. If a
conflict invalidates the *frame*, backjump all the way to level 0 and pick a
different frame. If a conflict invalidates only a *tactic* at level 2, you
stay at level 1.

### Support vs Strict Entailment

In pure SAT, a parent **entails** its child via unit propagation. In general
reasoning, a parent often just **supports** the child (evidence, analogy,
precedent). CDLM accepts either — but note the tradeoff:

- **Strict entailment** gives the 1-UIP / learned-clause guarantees that SAT
  CDCL enjoys. Conflict analysis is airtight.
- **Support** is looser. The conflict analysis still identifies which
  combination of assumptions produced the contradiction, but the *learned
  lemma* may be a heuristic ("X and Y together tend to fail") rather than a
  theorem.

When nodes rest on support rather than entailment, be explicit in the
reasoning field about the nature of the link ("strongly suggests", "is
consistent with", "rules out"). That transparency lets you evaluate learned
lemmas properly.

### Conflicts vs Tensions

Not all contradictions are binary. You'll encounter:

- **Hard conflicts**: formally impossible (A and ¬A). Trigger `cdlm_conflict_check(is_conflict=True)` immediately.
- **Tensions**: evidence points both ways, or a claim stretches credibility without being refuted. Record as an IMPLICATION whose text names the tension ("Tension: H predicts X but 2/7 data points contradict"). If the tension hardens into a conflict later, promote it then.

CDLM is conflict-driven as a *way of thinking*: you actively hunt for
contradictions and tensions, because each one either kills a branch, learns
a new constraint, or exposes a faulty abstraction. Treat apparent agreement
with suspicion — the value of the method is in the disagreements.

### Learned Lemmas

After every conflict you author a **lemma**: a human-readable constraint that
prevents the same contradiction from recurring. Lemmas persist across
backjumps and permanently narrow the search space.

- Concrete lemma: `"Cell(1,2) != 1"`
- Abstract lemma: `"Any explanation must account for the 3 endpoints that don't touch the user-profile path"`

Good lemmas are *general* enough to prune more than one branch. A lemma that
only rules out the exact configuration you just tried is weak. Try to extract
the underlying principle that made the branch fail.

## CDLM Tools

When this skill is active, the host agent framework exposes seven tool
handlers (see `cdlm/session.py` and `cdlm/schemas.py` in the accompanying
package). **You MUST use these tools to execute the solver loop and drive
every phase yourself.** The tools do not call any external LLM — *you* are
the reasoning engine, and the tools handle state-machine validation, tree
bookkeeping, and the deterministic conflict-analysis math (1-UIP, learned
clause, backjump level). No API keys are required.

### Available Tools

| Tool | Description |
|------|-------------|
| `cdlm_init(problem_text, problem_type?)` | Initialize a session. Call this first. |
| `cdlm_propagate(deductions)` | Add the implications **you** have derived. |
| `cdlm_conflict_check(is_conflict, reasoning?, parents?)` | Record whether you found a contradiction. |
| `cdlm_solution_check(is_solution, reasoning?, solution_text?)` | Record whether the tree is now a complete solution. |
| `cdlm_decide(text, reasoning?)` | Add an assumption (decision) to explore. |
| `cdlm_backtrack(lemma)` | Run conflict analysis, backjump, and store the lemma you learned. |
| `cdlm_status()` | Show current session state, tree, and allowed actions. |

### How the Tools Work

You — the calling LLM — produce all of the *content* of each phase and pass
it in as arguments. The tools produce all of the *structure*:

* **`cdlm_propagate(deductions=[...])`** — pass a list of
  `{text, reasoning, parents}` objects. Each entry must be **atomic** (one
  claim per item) and must cite the IDs of existing tree nodes that support it.
  Use `parents=[]` for the initial level-0 givens that come straight from the
  problem statement.

* **`cdlm_conflict_check(is_conflict=True, reasoning=..., parents=[...])`** —
  when you spot a contradiction, set `is_conflict=True` and supply the
  `parents` list (the node IDs whose joint claims produce the conflict).
  These seed the conflict analysis. Use `is_conflict=False` to record that
  the current state is consistent.

* **`cdlm_decide(text=..., reasoning=...)`** — choose the most-informative
  variable (see *Decision heuristics* below) and pass your assumption as
  `text`. This opens a new decision level.

* **`cdlm_solution_check(is_solution=True, solution_text=...)`** — when the
  tree fully determines the answer, pass the final answer in `solution_text`.

* **`cdlm_backtrack(lemma=...)`** — runs 1-UIP / learned clause / backjump
  level computation deterministically from the implication graph, drops every
  node above the backjump level, and stores **your** human-readable `lemma`
  so future propagations are informed by it. The return value tells you the
  backjump level, the UIP node, and the literals in the learned clause so you
  can confirm your reasoning.

Each tool returns the current `state`, the `allowed_actions` list, and a
serialized view of the tree.

> **Node IDs are never recycled.** After `cdlm_backtrack` removes the nodes
> above the backjump level, the next propagation gets the *next unused* ID,
> not the lowest free one. Always read the latest tree (from the previous
> tool's response or `cdlm_status`) to find the actual ID of any node you
> want to cite as a parent.

### State Machine

```
cdlm_init → cdlm_propagate (repeat as needed)
          → cdlm_conflict_check
              → conflict found → cdlm_backtrack → cdlm_propagate ...
              → no conflict → cdlm_solution_check or cdlm_decide
                                → solved → done
                                → not solved → cdlm_decide → cdlm_propagate ...
```

If you call a tool in the wrong state, it will return an error telling you
which actions are allowed. Use `cdlm_status` at any time to see where you are.

### Typical Workflow

1. `cdlm_init(problem_text="...")` — set up the session.
2. `cdlm_propagate(deductions=[...])` — pass the level-0 givens (parents `[]`)
   first, then call again to add deductions that follow. Repeat until no
   further deductions are visible.
3. `cdlm_conflict_check(is_conflict=..., parents=...)` — report whether you
   spotted a contradiction.
4. If conflict: `cdlm_backtrack(lemma="...")` → go to step 2.
5. If no conflict: `cdlm_solution_check(is_solution=...)` — report whether
   the tree fully solves the problem.
6. If not solved: `cdlm_decide(text="...")` → go to step 2.
7. If solved: report the solution.

## Key Principles for General Reasoning

### Atomicity

A node should be atomic **at the granularity you would want to retract as a
unit**. On a backjump, the whole node goes — so if "Cell(1,2) = 4 and
Cell(1,3) = 1" is one node, you can't retract just one half. For abstract
reasoning the same rule applies: the grain of the node is the grain of
retraction.

- Concrete: one fact per node.
- Investigations: one hypothesis, one finding, or one inference per node.
- Design: one commitment, one requirement, or one implication per node.

### Propagate Exhaustively Before Deciding

Extract every deduction that follows from current state *before* making a new
decision. A premature decision opens a branch that cheaper propagation would
have resolved or refuted for free. This is doubly true at high abstraction
levels — a missed implication from your framing can waste many sub-decisions.

### Decision Heuristics (Generalized)

The classic CDCL heuristic is "most-constrained variable." The general
version is **highest-information decision**: commit to the claim whose
resolution most reshapes the tree.

- **Combinatorial**: most-constrained variable (fewest remaining candidates).
- **Root-cause**: the hypothesis that best discriminates between candidate causes. Prefer experiments whose outcome most splits the space of remaining explanations.
- **Design / strategy**: the commitment that most constrains subsequent choices. Frame before mechanism; mechanism before parameter.
- **Mathematical proof**: the case split, assumption, or lemma that most collapses the remaining work.

### Parent Tracking Is Non-Negotiable

Every implication must cite its parents — even for abstract claims where
"entailment" feels fuzzy. Parents make the conflict analysis work: they are
the only record of *why* a node is in the tree. Without them, backjump has
nothing to reason about.

### Hunt for Conflicts and Tensions

Don't just propagate forward until you get stuck. At every step, actively
ask: *does this new claim contradict anything already in the tree?* Scan the
frontier for tensions. Premature consensus is the failure mode — CDLM's
value is in the contradictions it surfaces.

### Good Lemmas Generalize

After a conflict, the weakest possible lemma just restates the specific
failing assignment. The strongest lemma names the underlying constraint the
failed branch violated. Spend effort on the lemma — it's the only thing you
permanently gain from the failed branch.

## Worked Example A (concrete): 4×4 Sudoku

Full trace in `references/worked-example.md`. Summary:

- Level 0: six givens + two forced propagations.
- Level 1 decision: `Cell(1,2) = 1`. Propagations force `Cell(1,3) = 4`.
- Conflict: `Cell(1,3) = 4` contradicts given `Cell(0,3) = 4` in column 3.
- 1-UIP = the level-1 decision. Learned clause: `{Cell(1,2) = 1}` causes conflict.
- Learned lemma: `Cell(1,2) != 1`. Backjump to level 0.
- Continue with this lemma installed; eventually solve.

## Worked Example B (abstract): Incident Root-Cause Analysis

Full trace in `references/abstract-example.md`. Summary:

**Problem**: After deploying v2.5, API p99 latency jumped from 80ms to 800ms
across most endpoints. Find the cause.

**Level 0 (givens and immediate deductions)**
- [0] Latency spike started at 14:02 UTC.
- [1] v2.5 deploy completed at 14:01 UTC.
- [2] 7 of 12 endpoints are impacted; 5 are not. (parents: [])
- [3] The 7 impacted endpoints do not share a database. (parents: [2])
- [4] Spike is temporally coincident with v2.5 deploy. (parents: [0, 1])

**Level 1 decision (framing)**
- [5] DECISION: Frame as a regression introduced by v2.5 code changes. (reasoning: temporal coincidence from [4])

**Level 1 propagations**
- [6] v2.5 changeset includes three candidate areas: a new DB query in `/profile`, a new logging middleware, and a refactored auth handler. (parents: [5])

**Level 2 decision (tactical)**
- [7] DECISION: Assume the new DB query in `/profile` is the cause. (most obvious from [6])

**Level 2 propagations**
- [8] `/profile` query trace shows 600ms latency — matches magnitude. (parents: [7])
- [9] But 4 of 7 impacted endpoints don't call `/profile`. (parents: [7, 2])

**Conflict check**
- CONFLICT: [7] predicts only `/profile`-touching endpoints are impacted, but [2] shows 4 impacted endpoints that don't touch it. (parents: [7, 9])

**Backtrack**
- 1-UIP: [7]. Learned clause: `{[7]}`.
- **Learned lemma**: *"Any explanation must account for impact across endpoints that don't share a database or code path — the cause is shared infrastructure, not an endpoint-specific query."*
- Backjump to level 1.

**Level 2 decision (tactical, attempt 2)**
- [10] DECISION: Assume the cause is in the new logging middleware (it runs on every request, which matches the lemma). (reasoning: lemma + [6])

**Level 2 propagations**
- [11] Logging middleware does a synchronous DNS lookup to a logging collector on every request. (parents: [10])
- [12] DNS is misconfigured for the new collector hostname, timing out at ~700ms per request. (parents: [11])
- [13] Sync DNS timeout is consistent with 800ms p99 and cross-endpoint impact. (parents: [12, 0, 2])

**Solution check**: explanation accounts for all observations. **Solved**.
Final answer: *synchronous DNS lookup in the new v2.5 logging middleware, hitting a misconfigured hostname, is the root cause*.

**What this demonstrates**: the level-1 decision was a *framing* choice. The
level-2 decisions were *tactical hypotheses*. The conflict killed one
tactical hypothesis without invalidating the frame, so the backjump stopped
at level 1. The learned lemma encoded a general constraint ("must account for
cross-endpoint impact") that guided the second tactical decision. If the
framing itself had been wrong (e.g., latency was coincidentally caused by an
infra incident at 14:02 unrelated to v2.5), a deeper conflict would eventually
force a backjump all the way to level 0 and a different frame.

## Output Requirements

**You MUST output the full reasoning trace, not just the final answer.** The
trace is the primary output — it shows exactly how the solution was derived,
which branches were explored, what went wrong, and what was learned.

Every response must include:

1. **Iteration-by-iteration trace** showing every phase executed.
2. **The reasoning tree** at key moments (after propagation, after conflicts, at the end).
3. **The final answer** clearly marked at the end.
4. **Solve statistics**: iterations, decisions made, conflicts, lemmas learned.

### Iteration Trace Format

```
--- Iteration 1 ---

[PROPAGATE] Deducing from current state...
  Added [6] IMPLICATION: Cell(0,1) = 2 (Parents: 0, 1, 2)
    Reasoning: Row 0 has {1, 4}. Col 1 has {3}. Only candidate is 2.
  No more deductions possible.

[CONFLICT CHECK] No conflict detected.

[SOLUTION CHECK] Not yet complete — 8 cells remain unassigned.

[DECIDE] Most constrained open cell: Cell(1,2) with candidates {1, 4}.
  Added [9] DECISION: Cell(1,2) = 1
```

When a conflict occurs, show the full analysis:

```
[CONFLICT CHECK] CONFLICT: Cell(1,3) = 4 contradicts Cell(0,3) = 4 in col 3.
  Added [11] CONFLICT (Parents: 1, 10)

[BACKTRACK]
  1-UIP: Node 9 (Cell(1,2) = 1)
  Learned clause: {9}
  Learned lemma: Cell(1,2) != 1
  Backjump level: 0. Nodes above level 0 removed.
```

### Final Answer Format

```
=== SOLUTION FOUND (Iteration 5) ===

Solve Statistics:
  Total iterations: 5
  Decisions made: 2
  Conflicts encountered: 1
  Lemmas learned: 1
  Total deductions: 14

Answer:
  <the final answer, verified>
```

## Use Code Execution Where It Helps

For problems with precise state (grids, graphs, numeric constraints), use
Python to compute candidates, verify deductions, and detect conflicts
programmatically — this prevents arithmetic and bookkeeping errors. For
abstract reasoning, code execution is rarely useful; rely on structured
textual reasoning and rigorous parent tracking instead.

## Tips

- **Decide at the right abstraction level first.** Frame before mechanism, mechanism before value. This makes backjumps retract the right thing.
- **Propagate exhaustively.** Premature decisions cost more than exhaustive propagation.
- **Keep deductions atomic** at the grain of retraction.
- **Track parents even when the link is "support," not "entailment."** Conflict analysis depends on it.
- **Hunt for contradictions.** Every apparent consensus is a candidate tension in disguise.
- **Write lemmas that generalize.** The lemma is the permanent takeaway from a failed branch — make it worth the branch.

## References

- `references/conflict-analysis.md` — the conflict-analysis algorithm with 1-UIP worked through in detail.
- `references/worked-example.md` — full CDLM trace on a 4×4 Sudoku (concrete).
- `references/abstract-example.md` — full CDLM trace on an incident root-cause analysis (abstract).
