from typing import List, Optional, Union
from pydantic import BaseModel, Field
from collections import defaultdict


class Problem:
    def __init__(self, problem_statement: str, lemmas: List[str] = None):
        self.problem_statement = problem_statement
        self.lemmas = lemmas.copy() if lemmas else []
    
    def __str__(self):
        lemmas = ""
        for lemma in self.lemmas:
            lemmas += "\n" + lemma + ","
        return f"Problem Description: {self.problem_statement}\nKnown Lemmas: {lemmas}" 
 

# Prop Agent outputs List[Deduction]
class Deduction(BaseModel):
    reasoning: str = Field(description="The proper reasoning used to deduce the deduction text")
    text: str = Field(description="The actual and complete deduction in text format")
    parents: List[int] = Field(description="The complete list of IDs of the existing parent nodes/deductions that together imply this deduction")

# Decision Agent takes a design decision / assumption
class Decision(BaseModel):
    reasoning: str = Field(description="The proper reasoning used to make the decision regarding the problem")
    text: Optional[str] = Field(description="The actual and complete decision in text format. This is empty string / left as None if no decision is necessary at this point")

# Conflict Detection Agent outputs Conflict
class Conflict(BaseModel):
    reasoning: str = Field(description="The proper reasoning used to decide that a logical conflict / contradiction exists or does not exist")
    is_conflict: bool = Field(description="The decision that a logical contradiction exists (True) or does not exist (False)")
    parents: List[int] = Field(description="The complete list of IDs of the existing parent nodes/deductions that together imply the conflict - this is empty if is_conflict is False")

# Solution Checker Agent outputs 
class Solution(BaseModel):
    reasoning: str = Field(description="The proper reasoning used to decide that a solution is found or if more work is needed")
    is_solution: bool = Field(description="The decision that a solution is found (True) or we must continue searching / solving the problem (False)")
    solution_text: Optional[str] = Field(description="The actual and complete solution in text format if a solution is found - this must be populated only if is_solution is True")

class Node:
    def __init__(self, id: int, text: str, parents: List[int], decision_level: int, is_decision: bool = False):
        self.text = text
        self.id = id
        self.parents = parents.copy()
        self.decision_level = decision_level
        self.is_decision = is_decision
 

# Manually add nodes 
class Tree:
    def __init__(self):
        self.graph = defaultdict(set)
        self.nodes = {}
        self.id = 0
        self.curr_decision_level = 1
        self.conflict_id = None
    
    def append_deductions(self, deductions: Union[List[Deduction], Decision, Conflict], 
                          decision_level: int = None, is_decision: bool = None):
        """
        Append deductions/decisions/conflicts to the tree.
        
        Args:
            deductions: The deduction(s) to add
            decision_level: Optional override for decision level (used in testing/examples)
            is_decision: Optional override for is_decision flag (used in testing/examples)
        """
        if not isinstance(deductions, list):
            deductions = [deductions]

        for deduction in deductions:
            computed_decision_level = 0
            parents = []
            is_decision_node = False
            
            if not isinstance(deduction, Decision):
                valid_parents = 0
                invalid_parents = []
                for parent in deduction.parents:
                    if parent != self.id and parent in self.nodes:
                        parents.append(parent)
                        computed_decision_level = max(computed_decision_level, self.nodes[parent].decision_level)
                        self.graph[parent].add(self.id)
                        valid_parents += 1
                    else:
                        invalid_parents.append(parent)
                
                # Warn if any invalid parents were referenced
                if invalid_parents:
                    if isinstance(deduction, Deduction):
                        print(f"Warning: Deduction '{deduction.text}' referenced invalid parent IDs: {invalid_parents}")
                    elif isinstance(deduction, Conflict):
                        print(f"Warning: Conflict referenced invalid parent IDs: {invalid_parents}")
                
                # If all parents were invalid, this is a potential issue
                if deduction.parents and valid_parents == 0:
                    if isinstance(deduction, Deduction):
                        print(f"Warning: Deduction '{deduction.text}' has no valid parents (all references were invalid)")
                    elif isinstance(deduction, Conflict):
                        print(f"Warning: Conflict has no valid parents (all references were invalid)")
            
            # Determine final decision level
            if decision_level is not None:
                # Use explicit override (for testing/examples)
                final_decision_level = decision_level
            elif computed_decision_level == 0:
                final_decision_level = self.curr_decision_level
            else:
                final_decision_level = computed_decision_level
            
            # Check for duplicate deductions
            if isinstance(deduction, Deduction):
                duplicate_found = False
                for existing_node in self.nodes.values():
                    if existing_node.text == deduction.text:
                        print(f"Warning: Duplicate deduction skipped: '{deduction.text}'")
                        duplicate_found = True
                        break
                if duplicate_found:
                    continue
                
                is_decision_node = is_decision if is_decision is not None else False
                node = Node(self.id, deduction.text, parents, final_decision_level, is_decision_node)
                
            elif isinstance(deduction, Decision):
                # Check for duplicate decisions too
                duplicate_found = False
                for existing_node in self.nodes.values():
                    if existing_node.text == deduction.text:
                        print(f"Warning: Duplicate decision skipped: '{deduction.text}'")
                        duplicate_found = True
                        break
                if duplicate_found:
                    continue
                
                if is_decision is not None:
                    is_decision_node = is_decision
                    final_decision_level = decision_level if decision_level is not None else self.curr_decision_level + 1
                else:
                    is_decision_node = True
                    final_decision_level = self.curr_decision_level + 1
                    self.curr_decision_level += 1
                    
                node = Node(self.id, deduction.text, [], final_decision_level, is_decision_node)
                
            elif isinstance(deduction, Conflict):
                node = Node(self.id, "CONFLICT", parents, final_decision_level, False)
                self.conflict_id = self.id
            else:
                continue  # Unknown type, skip
                
            self.nodes[self.id] = node
            self.id += 1
        
        return

    def remove_nodes(self, backjump_level: int):
        self.conflict_id = None  # Reset conflict state after backjump
        self.curr_decision_level = backjump_level if backjump_level > 0 else 1
        # gracefully remove every node with decision_level after backjump_level
        nodes_to_remove = []
        for node_id in self.nodes:
            node = self.nodes[node_id]
            if node.decision_level > backjump_level:
                nodes_to_remove.append(node_id)
        
        for node_id in nodes_to_remove:
            node = self.nodes[node_id]
            del self.nodes[node_id]
            for parent in node.parents:
                self.graph[parent].remove(node_id)
        
        return

    def __str__(self):
        if not self.nodes:
            return "Tree is empty."
        
        output = []
        # Group nodes by decision level
        levels = defaultdict(list)
        for node in self.nodes.values():
            levels[node.decision_level].append(node)
            
        for level in sorted(levels.keys()):
            output.append(f"Decision Level {level}:")
            for node in sorted(levels[level], key=lambda n: n.id):
                node_type = "DECISION" if node.is_decision else "IMPLICATION"
                if node.id == self.conflict_id:
                    node_type = "CONFLICT"
                
                parents_info = f", Parents: {node.parents}" if node.parents else ""
                output.append(f"  [{node.id}] {node_type}: {node.text}{parents_info}")
            output.append("")
            
        return "\n".join(output)