"""
CDCL Conflict Analysis

This module implements conflict analysis for CDCL-style implication graphs.
Given a conflict node, it finds:
1. The learned clause (collection of node IDs)
2. The First Unique Implication Point (1-UIP)
3. The decision level to backjump to

IMPORTANT - Semantic Interpretation:
====================================
In SAT solving, literals in the trail are TRUE (assigned), and the learned
clause contains their NEGATIONS to prevent the conflict.

In this implementation:
- Node IDs in the implication graph represent POSITIVE assignments (what was assigned)
- Node IDs in the learned clause represent literals whose assignments CAUSED the conflict
- Semantically: "If these assignments are made together, conflict occurs"

For SAT encoding: The learned clause would be the NEGATION of these literals.
Example: If learned clause = {A, B}, the SAT clause is (NOT A OR NOT B)

Reference: https://users.aalto.fi/~tjunttil/2020-DP-AUT/notes-sat/cdcl.html
"""

from typing import Set, List, Tuple
from collections import deque
from .problem_structure import Tree, Node


class ConflictAnalyzer:
    """
    Analyzes conflicts in CDCL-style implication graphs to produce learned clauses.
    """
    
    def __init__(self, tree: Tree):
        """
        Initialize the conflict analyzer with an implication graph.
        
        Args:
            tree: The implication graph (Tree object)
        """
        self.tree = tree
        self.nodes = tree.nodes
    
    def analyze_conflict(self, conflict_node_id: int) -> Tuple[Set[int], int, int]:
        """
        Perform conflict analysis starting from a conflict node.
        
        Implements the 1-UIP conflict analysis algorithm:
        1. Start from the conflict clause (parents of conflict node)
        2. Perform resolution backward through the implication graph
        3. Stop at the First Unique Implication Point (1-UIP)
        4. Extract the learned clause and backjump level
        
        Args:
            conflict_node_id: The ID of the conflict node
            
        Returns:
            Tuple of (learned_clause, uip_node_id, backjump_level) where:
            - learned_clause: Set of node IDs forming the learned clause
            - uip_node_id: The node ID of the 1-UIP
            - backjump_level: The decision level to backjump to
            
        Raises:
            ValueError: If the conflict node doesn't exist or has no parents
        """
        if conflict_node_id not in self.nodes:
            raise ValueError(f"Conflict node {conflict_node_id} does not exist in the graph")
        
        conflict_node = self.nodes[conflict_node_id]
        
        if not conflict_node.parents:
            raise ValueError(f"Conflict node {conflict_node_id} has no parents")
        
        conflict_level = conflict_node.decision_level
        
        # Start with the conflict clause (parents of the conflict node)
        current_clause = set(conflict_node.parents)
        
        # Find the 1-UIP using backward resolution
        uip_node_id = self._find_1uip(current_clause, conflict_level)
        
        # Build the learned clause
        learned_clause = self._build_learned_clause(current_clause, conflict_level, uip_node_id)
        
        # Calculate backjump level
        backjump_level = self._calculate_backjump_level(learned_clause, conflict_level)
        
        return learned_clause, uip_node_id, backjump_level
    
    def _find_1uip(self, clause: Set[int], conflict_level: int) -> int:
        """
        Find the First Unique Implication Point (1-UIP) by performing resolution.
        
        The 1-UIP is the first node in the conflict level (closest to the conflict)
        such that all paths from the decision node to the conflict pass through it.
        
        Algorithm (from the reference):
        1. Start with the conflict clause
        2. While there is more than one literal from the conflict level in the clause:
           a. Pick the most recent literal from the conflict level (highest ID in trail order)
           b. Resolve with its antecedent (replace it with its parents)
        3. The remaining literal from the conflict level is the 1-UIP
        
        Args:
            clause: Current clause (set of node IDs)
            conflict_level: The decision level where conflict occurred
            
        Returns:
            The node ID of the 1-UIP
        """
        current_clause = clause.copy()
        
        # Perform resolution until only one conflict-level literal remains
        while True:
            # Get all nodes at the conflict level in current clause
            conflict_level_nodes = [
                node_id for node_id in current_clause 
                if self.nodes[node_id].decision_level == conflict_level
            ]
            
            # Stop when we have exactly one literal from conflict level (the 1-UIP)
            if len(conflict_level_nodes) == 1:
                return conflict_level_nodes[0]
            
            if len(conflict_level_nodes) == 0:
                raise ValueError("No literals from conflict level found - invalid conflict clause")
            
            # Pick the most recent (highest ID) node from conflict level
            # This corresponds to the last assigned literal in the trail
            most_recent = max(conflict_level_nodes)
            
            # Remove this node from the clause
            current_clause.remove(most_recent)
            
            # Add its parents (resolution step - resolve with antecedent)
            most_recent_node = self.nodes[most_recent]
            for parent_id in most_recent_node.parents:
                current_clause.add(parent_id)
    
    def _build_learned_clause(self, clause: Set[int], conflict_level: int, uip_node_id: int) -> Set[int]:
        """
        Build the learned clause by performing resolution up to the 1-UIP.
        
        The learned clause is formed by:
        1. Starting with the conflict clause
        2. Resolving away all conflict-level literals except the 1-UIP
        3. The result contains the 1-UIP and all literals from earlier levels
        
        In CDCL terms, the learned clause is a clause that:
        - Contains literals whose assignments CAUSED the conflict
        - Is falsified by the current trail up to the conflict level
        - Becomes unit (forces backjumping) when we backjump
        - In SAT: Would be encoded as the NEGATION of these literals
        
        Level-0 literals are excluded because they are always true (initial constraints),
        so their negations would make the learned clause trivially satisfied or useless.
        Reference: Aalto notes - "negations of decision level 0 literals are not included"
        
        Args:
            clause: The initial conflict clause
            conflict_level: The decision level where conflict occurred
            uip_node_id: The 1-UIP node ID
            
        Returns:
            Set of node IDs forming the learned clause (representing literals that caused conflict)
        """
        current_clause = clause.copy()
        
        # Resolve until only the 1-UIP remains from the conflict level
        while True:
            # Get all nodes at the conflict level
            conflict_level_nodes = [
                node_id for node_id in current_clause 
                if self.nodes[node_id].decision_level == conflict_level
            ]
            
            # Stop when only 1-UIP remains
            if len(conflict_level_nodes) == 1 and conflict_level_nodes[0] == uip_node_id:
                break
            
            # Pick the most recent node from conflict level (that's not the 1-UIP yet)
            most_recent = max(conflict_level_nodes)
            
            # Remove this node from the clause
            current_clause.remove(most_recent)
            
            # Add its parents (resolution step)
            most_recent_node = self.nodes[most_recent]
            for parent_id in most_recent_node.parents:
                current_clause.add(parent_id)
        
        # The learned clause excludes level 0 literals (they're always true - initial constraints)
        # Including them would be pointless as their negations would make the clause useless
        learned_clause = set()
        for node_id in current_clause:
            node = self.nodes[node_id]
            # Include all non-level-0 nodes
            if node.decision_level > 0:
                learned_clause.add(node_id)
        
        return learned_clause
    
    def _calculate_backjump_level(self, learned_clause: Set[int], conflict_level: int) -> int:
        """
        Calculate the decision level to backjump to.
        
        The backjump level is where the learned clause becomes unit-propagating.
        This is typically the second-highest decision level in the learned clause,
        or the highest level below the conflict level if there's only one level.
        
        From Aalto reference: The backjump level is the "assertion level" where
        the learned clause forces a new assignment via unit propagation.
        
        Args:
            learned_clause: The learned clause (set of node IDs)
            conflict_level: The decision level where conflict occurred
            
        Returns:
            The decision level to backjump to
        """
        if not learned_clause:
            return 0
        
        # Get all decision levels in the learned clause, sorted
        levels = sorted(set(
            self.nodes[node_id].decision_level 
            for node_id in learned_clause
        ), reverse=True)
        
        # If only one level or all are level 0, backjump to 0
        if len(levels) <= 1:
            return 0
        
        # Backjump to the second-highest level
        # (where the clause becomes unit after undoing the highest level)
        return levels[1]
    
    def get_cut_nodes(self, learned_clause: Set[int], conflict_level: int) -> Tuple[Set[int], Set[int]]:
        """
        Get the nodes on the reason side and conflict side of the 1-UIP cut.
        
        This is useful for visualization purposes.
        
        Args:
            learned_clause: The learned clause (set of node IDs)
            conflict_level: The decision level where conflict occurred
            
        Returns:
            Tuple of (reason_side, conflict_side) where:
            - reason_side: Nodes that lead to the 1-UIP (earlier in trail)
            - conflict_side: Nodes after the 1-UIP leading to conflict
        """
        reason_side = set()
        conflict_side = set()
        
        for node_id in self.nodes:
            node = self.nodes[node_id]
            if node.decision_level == conflict_level:
                if node_id in learned_clause:
                    reason_side.add(node_id)
                else:
                    conflict_side.add(node_id)
        
        return reason_side, conflict_side


def analyze_and_print(tree: Tree):
    """
    Analyze a conflict and print detailed results.
    
    Args:
        tree: The implication graph
        conflict_node_id: The ID of the conflict node
    """
    if tree.conflict_id is None:
        raise ValueError("No conflict to analyze")
    
    conflict_node_id = tree.conflict_id
    analyzer = ConflictAnalyzer(tree)
    
    try:
        learned_clause, uip_node_id, backjump_level = analyzer.analyze_conflict(conflict_node_id)
        
        print("=" * 80)
        print("CONFLICT ANALYSIS RESULTS")
        print("=" * 80)
        print(f"Conflict Node: {conflict_node_id} - {tree.nodes[conflict_node_id].text}")
        print(f"Conflict Level: {tree.nodes[conflict_node_id].decision_level}")
        print()
        
        print(f"First Unique Implication Point (1-UIP): {uip_node_id}")
        print(f"  Node: {tree.nodes[uip_node_id].text}")
        print(f"  Level: {tree.nodes[uip_node_id].decision_level}")
        print()
        
        print(f"Learned Clause (node IDs): {sorted(learned_clause)}")
        print("Learned Clause (literals that caused conflict):")
        for node_id in sorted(learned_clause):
            node = tree.nodes[node_id]
            print(f"  [{node_id}] {node.text} @ level {node.decision_level}")
        print()
        print("Note: In SAT terms, the learned clause would be the NEGATION of these literals:")
        print(f"  NOT({' AND '.join(tree.nodes[nid].text for nid in sorted(learned_clause))})")
        print()
        
        print(f"Backjump to Decision Level: {backjump_level}")
        print("=" * 80)
        
        return learned_clause, uip_node_id, backjump_level
        
    except ValueError as e:
        print(f"Error: {e}")
        return None, None, None


