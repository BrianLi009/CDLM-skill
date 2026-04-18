# Worked Example: Incident Root-Cause Analysis

A full CDLM trace on an open-ended reasoning problem — no numeric state, no
constraint satisfaction, just hypotheses, evidence, and contradictions. The
point is to show that the same machinery (implication graph, decision levels,
conflict-driven backjump, learned lemmas) applies cleanly to fuzzy
investigative work.

## Problem

> After deploying v2.5 at 14:01 UTC, our API's p99 latency jumped from 80ms to
> 800ms. 7 of 12 endpoints are impacted; 5 are unaffected. The 7 impacted
> endpoints do not share a database. Find the root cause.

## Iteration 1

### [PROPAGATE] Level 0 — Givens and Immediate Deductions

Level-0 nodes come directly from the problem statement and trivial inferences
from it:

```
Decision Level 0:
  [0] IMPLICATION: Latency spike started at 14:02 UTC. (parents: [])
  [1] IMPLICATION: v2.5 deploy completed at 14:01 UTC. (parents: [])
  [2] IMPLICATION: 7 of 12 endpoints are impacted; 5 are not. (parents: [])
  [3] IMPLICATION: The 7 impacted endpoints do not share a database. (parents: [2])
  [4] IMPLICATION: Spike is temporally coincident with the v2.5 deploy. (parents: [0, 1])
    Reasoning: Spike at 14:02, deploy at 14:01 — 1-minute gap.
```

### [CONFLICT CHECK] No conflict.

### [SOLUTION CHECK] Not solved — we don't yet have a root cause.

### [DECIDE] Framing

The most informative commitment at this point is *how to frame the
investigation*. Two reasonable frames:

- **Frame A**: Regression introduced by v2.5 code changes.
- **Frame B**: Infra incident coincidentally occurring at 14:02.

The temporal coincidence in [4] is strong but not conclusive. Frame A is more
productive because it points to a bounded changeset. We'll try A first; if
it fails we'll backjump and try B.

```
  [5] DECISION: Frame as a regression introduced by v2.5 code changes.
    Reasoning: Temporal coincidence from [4]; bounded search space of code changes.
```

## Iteration 2

### [PROPAGATE]

```
  [6] IMPLICATION: v2.5 changeset includes three candidate areas: (parents: [5])
      - new DB query in /profile endpoint
      - new logging middleware (runs on every request)
      - refactored auth handler
```

### [CONFLICT CHECK] No conflict.

### [SOLUTION CHECK] Not solved.

### [DECIDE] Tactical hypothesis

Which candidate cause first? The `/profile` DB query is the most visible
change and easiest to measure directly. Decide on it:

```
  [7] DECISION: Assume the new DB query in /profile is the cause.
    Reasoning: Most visible change in [6]; direct query traces are easy to pull.
```

## Iteration 3

### [PROPAGATE]

```
  [8] IMPLICATION: /profile query trace shows 600ms execution time — matches
      latency magnitude. (parents: [7])
    Reasoning: Pulled query logs for 14:02+; /profile query takes 600ms.
  [9] IMPLICATION: 4 of the 7 impacted endpoints never call /profile. (parents: [7, 2])
    Reasoning: Traced the 7 impacted endpoints; 4 have no /profile dependency.
```

### [CONFLICT CHECK]

[7] predicts only `/profile`-touching endpoints should be impacted. [9] shows
4 impacted endpoints that don't touch `/profile`. Direct contradiction.

```
  CONFLICT DETECTED.
  Added [10] CONFLICT (Parents: 7, 9)
    Reasoning: Hypothesis [7] cannot explain the cross-endpoint impact from [9].
```

### [BACKTRACK]

```
  [CONFLICT ANALYSIS]
    Tracing back from [10] (conflict, level 2)...
      [10] parents: {7, 9}
      [9] is level 2, parents {7, 2} — resolve: clause becomes {7, 2}
      [7] is the decision at level 2 — it's the 1-UIP.
    1-UIP: Node 7 (Assume /profile DB query is the cause).
    Learned clause: {7}.
    Backjump level: 1.
```

**Learned lemma** (human-authored, not mechanical):

> *"Any explanation must account for impact across endpoints that don't share
> a database or code path — the cause is in shared infrastructure, not in an
> endpoint-specific query."*

This is a *generalization* of the immediate clause. The mechanical learned
clause just says `[7]` was wrong; the authored lemma says *why* it was wrong
and constrains future hypotheses.

```
  [BACKJUMP] Removing nodes above level 1. Lemma added.
```

State after backjump:

```
Decision Level 0:
  [0] Latency spike started at 14:02 UTC.
  [1] v2.5 deploy completed at 14:01 UTC.
  [2] 7 of 12 endpoints impacted; 5 not.
  [3] Impacted endpoints don't share a database.
  [4] Spike temporally coincident with v2.5 deploy.

Decision Level 1:
  [5] DECISION: Frame as v2.5 regression.
  [6] v2.5 changeset has 3 candidate areas: /profile query, logging middleware, auth handler.

Known Lemmas:
  1. Cause must be in shared infrastructure, not endpoint-specific code.
```

## Iteration 4

### [PROPAGATE] Apply the new lemma

With the lemma installed, re-examine the three candidates from [6]:

- `/profile` DB query: endpoint-specific. *Ruled out by lemma.*
- Logging middleware: runs on every request → shared. *Consistent.*
- Auth handler: only triggers on authenticated requests; the 5 non-impacted endpoints include some authenticated ones. *Partially rules out auth.*

No new deductions until we pick one.

### [CONFLICT CHECK] No conflict.

### [SOLUTION CHECK] Not solved.

### [DECIDE] Tactical hypothesis #2

```
  [10'] DECISION: Assume the new logging middleware is the cause.
    (Note: ID 10 was removed; next unused ID is the one after the highest
     still-in-tree. Suppose the tool assigns [10] again as next free ID in
     this example. In practice, always read the tool's response for the
     actual ID.)
    Reasoning: Logging middleware runs on every request — consistent with
    cross-endpoint impact per the lemma. Higher prior than auth because auth
    wouldn't affect unauthenticated endpoints that are also impacted.
```

## Iteration 5

### [PROPAGATE]

```
  [11] IMPLICATION: Logging middleware does a synchronous DNS lookup to a
       logging collector on every request. (parents: [10'])
    Reasoning: Code review of middleware shows sync dns.resolve() call before
    emitting the log record.
  [12] IMPLICATION: DNS is misconfigured for the new collector hostname,
       timing out at ~700ms per request. (parents: [11])
    Reasoning: Direct DNS probe returns SERVFAIL after 700ms timeout.
  [13] IMPLICATION: Sync DNS timeout is consistent with 800ms p99 and
       cross-endpoint impact. (parents: [12, 0, 2])
    Reasoning: 700ms DNS + ~80ms baseline ≈ 780ms. Runs on every request,
    matching cross-endpoint pattern. Matches magnitude and scope.
```

### [CONFLICT CHECK] No conflict — explanation is internally consistent and
matches all observations.

### [SOLUTION CHECK] Solved.

```
=== SOLUTION FOUND (Iteration 5) ===

Answer: Root cause is a synchronous DNS lookup in the new v2.5 logging
middleware. The lookup hits a misconfigured hostname for the logging
collector and times out at ~700ms per request, which runs in-band on every
endpoint and produces the observed ~800ms p99 with cross-endpoint impact.

Solve Statistics:
  Total iterations: 5
  Decisions made: 2 (1 framing, 1 tactical — plus 1 retracted tactical)
  Conflicts encountered: 1
  Lemmas learned: 1
  Total deductions: ~13
```

## What This Example Illustrates

### Abstraction Levels Fall Out of Decision Order

The level-1 decision ([5]) was *framing* — a coarse commitment about what
kind of problem this is. The level-2 decisions ([7], then [10']) were
*tactical* — specific hypotheses to test within the frame. When [7] was
contradicted, backjump went to level 1, preserving the framing. If the
*framing* itself had been wrong (e.g., it really was a coincidental infra
incident), a deeper contradiction would eventually force a backjump to
level 0.

This hierarchy emerges from deciding at the right abstraction level in the
right order, not from a separate abstraction-level field in the data
structure.

### Parents as Support, Not Entailment

In a SAT puzzle, parents *entail* the child by unit propagation. Here, the
links are support: [4] says "temporal coincidence suggests causal
relationship" — strong evidence, not proof. The conflict analysis still
works: [10] traces back through [9] to [7], and [7] is the 1-UIP. The
mechanical guarantee is slightly weaker (the learned clause is heuristic,
not a theorem), but the discipline of tracking parents is what makes the
backjump work at all.

### Lemmas Are Where the Intelligence Lives

The mechanical learned clause was `{7}` — "that specific hypothesis was
wrong." That's almost useless on its own. The authored lemma —
*"cause must be in shared infrastructure, not endpoint-specific code"* —
is what actually pruned the next decision ([10']) and steered the solve
toward the right answer. Spend effort on lemmas; they're the main
carry-over from failed branches.

### Conflict as a Positive Signal

The contradiction at [10] wasn't a failure — it was the most productive
event in the whole trace. It ruled out one third of the candidate causes
with a single set of observations, and it produced the lemma that
immediately eliminated `/profile` from further consideration. Actively
hunting for conflicts (rather than avoiding them) is what makes CDLM
conflict-driven as a *way of thinking*.
