#  HTN Engine  –  recursive task decomposition
from domain import PRIMITIVES, METHODS


class TreeNode:
    """One node in the decomposition tree."""
    def __init__(self, name, kind="compound", method=None):
        self.name     = name
        self.kind     = kind     # "compound" | "primitive"
        self.method   = method   # method name chosen (compound only)
        self.children = []

    def add_child(self, node):
        self.children.append(node)


def htn_plan(tasks, state, parent_node=None):
    """
    Recursively decompose `tasks` given `state`.

    Returns (plan, final_state)  — list of primitive names + resulting state,
    or (None, None) on failure.

    Builds the decomposition tree rooted at parent_node as a side-effect.
    Each task node is attached to the parent that logically owns it.

    Backtracking: if a chosen method's subtasks fail, the node is removed
    and the next method is tried.
    """
    if not tasks:
        return [], state

    task = tasks[0]
    rest = tasks[1:]

    # ── Primitive task ────────────────────────────────────────────────────
    if task in PRIMITIVES:
        node = TreeNode(task, kind="primitive")
        if parent_node is not None:
            parent_node.add_child(node)

        success, new_state = PRIMITIVES[task](state)
        if not success:
            return None, None

        # rest tasks belong to the SAME parent (siblings, not children)
        plan_rest, final_state = htn_plan(rest, new_state, parent_node)
        if plan_rest is None:
            return None, None

        return [task] + plan_rest, final_state

    # ── Compound task ─────────────────────────────────────────────────────
    if task in METHODS:
        for method_name, precondition, subtasks in METHODS[task]:
            if precondition(state):
                node = TreeNode(task, kind="compound", method=method_name)
                if parent_node is not None:
                    parent_node.add_child(node)

                # subtasks → children of THIS compound node
                # rest     → siblings, attach to parent_node (not node)
                # This separation is critical for correct tree structure.
                plan_sub, mid_state = htn_plan(subtasks, state, node)
                if plan_sub is None:
                    # undo: remove the node we just added
                    if parent_node is not None:
                        parent_node.children.remove(node)
                    continue

                plan_rest, final_state = htn_plan(rest, mid_state, parent_node)
                if plan_rest is None:
                    if parent_node is not None:
                        parent_node.children.remove(node)
                    continue

                return plan_sub + plan_rest, final_state

        return None, None   # no method worked

    return None, None       # unknown task
