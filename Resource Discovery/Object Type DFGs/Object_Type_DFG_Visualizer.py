# This script visualizes an Object Type DFG .gexf file

import matplotlib.pyplot as plt
import networkx as nx
import numpy as np
from pathlib import Path

# Load GEXF file
file = "Object_Type_DFG_Hiring_Assessment.gexf"
G = nx.read_gexf(file)

pos = nx.circular_layout(G)
plt.figure(figsize=(10, 8))

# Draw nodes
nx.draw_networkx_nodes(
    G, pos,
    node_size=800,
    node_color="#5DADE2",
    alpha=0.9,
    edgecolors="black"
)

# Draw node labels slightly below the nodes
label_offset = 0.08  # downward offset
for node, (x, y) in pos.items():
    plt.text(
        x, y - label_offset,
        node,
        fontsize=10,
        color="black",
        ha="center",
        va="top"
    )

# Draw directed, curved edges with larger arrowheads
rad = 0.15
nx.draw_networkx_edges(
    G, pos,
    edge_color="#7B7D7D",
    width=1.5,
    alpha=0.8,
    arrows=True,
    arrowsize=25,
    arrowstyle='-|>',
    connectionstyle=f"arc3,rad={rad}"
)

# Draw edge weights along the curve including self-loops
for u, v, data in G.edges(data=True):
    if "weight" not in data or data["weight"] in [None, "", 0]:
        continue

    # Positions
    x1, y1 = pos[u]
    x2, y2 = pos[v]

    if u == v:
        # Self-loop placement slightly above and to the right
        loop_radius = 0.15
        angle = np.pi / 4
        xn = x1 + loop_radius * np.cos(angle)
        yn = y1 + loop_radius * np.sin(angle)

        plt.text(
            xn, yn,
            f"{data['weight']}",
            fontsize=8,
            color="red",
            ha="center",
            va="center",
            bbox=dict(boxstyle="round,pad=0.2", fc="white", ec="none", alpha=0.7)
        )
    else:
        # Midpoint of the edge
        xm, ym = (x1 + x2) / 2, (y1 + y2) / 2

        dx = x2 - x1
        dy = y2 - y1
        d = np.sqrt(dx**2 + dy**2)

        offset = max(0.2, min(0.15, d * 0.25))
        xn = xm - dy / d * offset
        yn = ym + dx / d * offset

        plt.text(
            xn, yn,
            f"{data['weight']}",
            fontsize=8,
            color="red",
            ha="center",
            va="center",
            bbox=dict(boxstyle="round,pad=0.2", fc="white", ec="none", alpha=0.7)
        )

# Display settings
plt.axis("off")
plt.title(Path(file).stem, fontsize=14)
plt.tight_layout()
plt.show()