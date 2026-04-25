#  Decomposition Tree Visualizer
#  Libraries used: networkx, matplotlib  (both allowed by assignment)
#  Exports: build_graph, hierarchy_pos, draw_tree_on_ax, print_tree
import networkx as nx
import matplotlib.patches as mpatches

# node fill colours
NODE_COLOR = {
    "goal":      "#3B82F6",   # blue   – root GOAL
    "compound":  "#F59E0B",   # orange – compound tasks
    "primitive": "#22C55E",   # green  – primitive actions
    "active":    "#FFFFFF",   # white  – currently executing
}


def build_graph(root_node):
    """Walk a TreeNode tree → nx.DiGraph with label/kind attributes."""
    G = nx.DiGraph()

    def _walk(node, parent_id, counter):
        nid = counter[0]
        counter[0] += 1
        if node.kind == "compound" and node.method and node.method != "root":
            label = f"{node.name}\n[{node.method}]"
        else:
            label = node.name.replace("_", "\n")
        G.add_node(nid, label=label, kind=node.kind)
        if parent_id is not None:
            G.add_edge(parent_id, nid)
        for child in node.children:
            _walk(child, nid, counter)

    _walk(root_node, None, [0])
    return G


def hierarchy_pos(G, root=0, width=1.8, vert_gap=0.32):
    """Pure-Python top-down layout — no scipy needed.
    Recursively divides horizontal space evenly among siblings.
    """
    pos = {}

    def _recurse(node, left, right, depth):
        children = list(G.successors(node))
        pos[node] = ((left + right) / 2, -depth * vert_gap)
        if children:
            step = (right - left) / len(children)
            for i, child in enumerate(children):
                _recurse(child, left + i * step, left + (i + 1) * step, depth + 1)

    _recurse(root, 0.0, width, 0)
    return pos


def draw_tree_on_ax(G, pos, ax, title,
                    panel_bg="#2A2A3E", text_color="white", border="#3F3F6E",
                    active_nid=None):
    """
    Render the decomposition tree on *ax*.
    active_nid: node id to highlight white (currently executing step).

    Labels are drawn one node at a time to work around a matplotlib
    limitation where font_color cannot be a list in newer versions.
    """
    ax.clear()
    ax.set_facecolor(panel_bg)
    ax.axis("off")

    node_colors, node_sizes, edge_colors, linewidths = [], [], [], []
    labels = {}

    for nid, data in G.nodes(data=True):
        labels[nid] = data["label"]
        if nid == active_nid:
            node_colors.append(NODE_COLOR["active"])
            node_sizes.append(3600)
            edge_colors.append("#7C3AED")   # purple ring on active node
            linewidths.append(4)
        elif nid == 0:
            node_colors.append(NODE_COLOR["goal"])
            node_sizes.append(3200)
            edge_colors.append("#888888")
            linewidths.append(1.5)
        elif data["kind"] == "compound":
            node_colors.append(NODE_COLOR["compound"])
            node_sizes.append(2800)
            edge_colors.append("#888888")
            linewidths.append(1.5)
        else:
            node_colors.append(NODE_COLOR["primitive"])
            node_sizes.append(2400)
            edge_colors.append("#888888")
            linewidths.append(1.5)

    # edges
    nx.draw_networkx_edges(
        G, pos, ax=ax,
        edge_color="#555577", width=2,
        arrows=True, arrowsize=16,
        arrowstyle="-|>",
        connectionstyle="arc3,rad=0.0",
    )

    # nodes
    nx.draw_networkx_nodes(
        G, pos, ax=ax,
        node_color=node_colors,
        node_size=node_sizes,
        linewidths=linewidths,
        edgecolors=edge_colors,
    )

    # labels — drawn one at a time so each gets its own font_color string
    # (networkx rejects a list for font_color in newer matplotlib versions)
    for nid, label in labels.items():
        fc = "#1E1E2E" if nid == active_nid else text_color
        nx.draw_networkx_labels(
            G, pos, {nid: label}, ax=ax,
            font_size=7.5, font_weight="bold", font_color=fc,
        )

    # legend
    handles = [
        mpatches.Patch(color=NODE_COLOR["goal"],      label="Goal"),
        mpatches.Patch(color=NODE_COLOR["compound"],  label="Compound Task"),
        mpatches.Patch(color=NODE_COLOR["primitive"], label="Primitive Action"),
    ]
    if active_nid is not None:
        handles.append(mpatches.Patch(color=NODE_COLOR["active"], label="Executing"))

    ax.legend(handles=handles, loc="lower right", fontsize=8,
              facecolor="#1E1E2E", labelcolor=text_color, edgecolor=border)
    ax.set_title(title, color=text_color, fontsize=11, fontweight="bold", pad=10)


def print_tree(node, prefix="", is_last=True):
    """ASCII decomposition tree — used by terminal fallback."""
    connector = "\\-- " if is_last else "+-- "
    branch    = "    " if is_last else "|   "
    if node.kind == "compound":
        label = f"{node.name}  [compound | method: {node.method}]"
    else:
        label = f"{node.name}  [primitive]"
    print((prefix[:-4] + connector + label) if prefix else label)
    child_prefix = prefix + branch
    for i, child in enumerate(node.children):
        print_tree(child, child_prefix, i == len(node.children) - 1)
