# Conflict Analysis Algorithm

When a conflict is detected in the reasoning tree, this algorithm determines:
1. **What caused the conflict** (the learned clause)
2. **Where to backjump** (the backjump level)
3. **What to remember** (the learned lemma)

## Terminology

- **Conflict clause**: The set of parent nodes of the CONFLICT node
- **Antecedent**: The parents of an implication node (the nodes that forced it)
- **Resolution**: Replacing a node in the clause with its antecedent (its parents)
- **1-UIP** (First Unique Implication Point): The single node at the current decision level that, on its own, is sufficient to reach the conflict given the other assignments
- **Learned clause**: The final clause after resolution -- the minimal set of assignments across decision levels that together cause the conflict
- **Backjump level**: The decision level to return to after learning

## The 1-UIP Algorithm

### Step 1: Start with the Conflict Clause

Take the parents of the CONFLICT node. This is your initial clause.

```
CONFLICT parents: {Node 8, Node 10, Node 12}
Initial clause = {8, 10, 12}
```

### Step 2: Resolve Until One Current-Level Literal Remains

Count how many nodes in the clause are from the **current decision level** (the
level where the conflict occurred).

While there is **more than one** node from the current decision level:
1. Pick the most recent node (highest ID) from the current level
2. Replace it with its parents (this is resolution)
3. Remove duplicates and level-0 nodes (initial givens are always true)

```
Clause: {8, 10, 12}
  Node 12 is at level 2, Node 10 is at level 2, Node 8 is at level 1
  Two nodes at current level (2) -- resolve the most recent one

  Resolve Node 12 (parents: {9, 6}):
    Remove 12, add 9 and 6
    Clause: {8, 10, 9, 6}

  Node 10 at level 2, Node 9 at level 2 -- still two at current level
  Resolve Node 10 (parents: {9, 7}):
    Remove 10, add 9 and 7
    Clause: {8, 9, 6, 7}

  Node 9 is the only one at level 2 -- STOP
  1-UIP = Node 9
```

### Step 3: Build the Learned Clause

The learned clause contains:
- The 1-UIP node
- All nodes from OTHER decision levels (not level 0) still in the clause

```
Clause after resolution: {8, 9, 6, 7}
  Node 9: level 2 (1-UIP) -- KEEP
  Node 8: level 1 -- KEEP
  Node 6: level 0 -- REMOVE (always true)
  Node 7: level 1 -- KEEP

Learned clause: {8, 9, 7}
```

**Semantic meaning**: "Node 8 AND Node 9 AND Node 7 cannot all be true together."

**As a lemma**: NOT(assignment-8 AND assignment-9 AND assignment-7)

### Step 4: Calculate Backjump Level

Look at the decision levels of all nodes in the learned clause. The backjump
level is the **second-highest** level.

```
Learned clause: {8, 9, 7}
  Node 8: level 1
  Node 9: level 2
  Node 7: level 1

Decision levels present: [2, 1]
Second-highest = 1

Backjump level = 1
```

**Why second-highest?** At this level, the learned clause has exactly one
unassigned literal (the 1-UIP), making it a unit-propagating constraint. The
solver can immediately derive the negation of the 1-UIP's assignment.

If only one decision level is present, backjump to level 0.

### Step 5: Backjump and Learn

1. Remove all nodes with decision_level > backjump_level
2. Add the learned lemma to the problem's known constraints
3. Resume the solver loop from Phase 1 (propagation)

The lemma immediately enables new deductions that were not possible before,
because it encodes knowledge gained from the failed exploration.

## Why This Works

Without learning, a naive backtracker would:
- Undo only the most recent decision
- Potentially re-explore the same failed region from a different entry point
- Have exponential worst-case behavior

With conflict-driven learning:
- The solver jumps directly to the decision level that matters (non-chronological backtracking)
- The learned lemma prevents the same conflict pattern from ever recurring
- Each conflict permanently shrinks the search space

## Simplified Conflict Analysis

For problems where full 1-UIP analysis is overkill, a simpler approach:

1. Identify which **decisions** (not implications) are ancestors of the conflict
2. The most recent decision is the one to undo
3. Learn: "that decision's value is impossible given the earlier decisions"
4. Backjump to just before that decision and try a different value

This is less powerful (it learns less general clauses) but easier to execute
and still far better than no learning at all.
