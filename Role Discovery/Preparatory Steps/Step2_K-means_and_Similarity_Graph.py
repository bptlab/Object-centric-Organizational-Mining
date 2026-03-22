import xml.etree.ElementTree as ET
from pathlib import Path
import networkx as nx
import pandas as pd
import numpy as np
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import silhouette_score
from sklearn.metrics.pairwise import cosine_similarity
import matplotlib.pyplot as plt
from itertools import combinations


analyzed_resource_object_type = "Employee"
target_object_type = "Package"
target_object_type_attribute = "weight"      
input_file = Path(__file__).parent.parent.parent / "Event Logs" / "Order_Management_adapted.xml"
threshold = 0.97  


# Load OCEL
tree = ET.parse(input_file)
root = tree.getroot()
objects_section = root.find("objects")
events_section = root.find("events")

# Extract object types + attributes
object_types = {}
object_attributes = {}

for obj in objects_section.findall("object"):
    oid = obj.get("id")
    otype = obj.get("type")
    object_types[oid] = otype

    attrs = {}
    attrs_xml = obj.find("attributes")
    if attrs_xml is not None:
        for a in attrs_xml.findall("attribute"):
            attrs[a.get("name")] = a.text
    object_attributes[oid] = attrs

# Build O2O graph
O2O = nx.Graph()
for obj in objects_section.findall("object"):
    oid = obj.get("id")
    O2O.add_node(oid, type=obj.get("type"))

for obj in objects_section.findall("object"):
    oid = obj.get("id")
    inner = obj.find("objects")
    if inner:
        for rel in inner.findall("relationship"):
            target = rel.get("object-id")
            if target in O2O:
                O2O.add_edge(oid, target)

# Find relations between objects of analyzed_resource_object_type and objects of target_object_type via O2O relations or event-based relationships
o2o_pairs = []
for u, v in O2O.edges():
    type_u = O2O.nodes[u]["type"]
    type_v = O2O.nodes[v]["type"]
    if type_u == analyzed_resource_object_type and type_v == target_object_type:
        o2o_pairs.append((u, v))
    elif type_u == target_object_type and type_v == analyzed_resource_object_type:
        o2o_pairs.append((v, u))

event_pairs = []
for ev in events_section.findall("event"):
    rels = ev.find("objects")
    if rels is None:
        continue
    employees = set()
    orders = set()
    for rel in rels.findall("relationship"):
        oid = rel.get("object-id")
        otype = object_types.get(oid)
        if otype == analyzed_resource_object_type:
            employees.add(oid)
        elif otype == target_object_type:
            orders.add(oid)
    for emp in employees:
        for order in orders:
            event_pairs.append((emp, order))

all_pairs = set(o2o_pairs + event_pairs)

# Build Data Frame: one row per resource object-to-object inclusive value datapoint
rows = []
for emp, order in all_pairs:
    val = object_attributes.get(order, {}).get(target_object_type_attribute)
    if val is not None:
        rows.append([emp, order, val])

df = pd.DataFrame(rows, columns=["resource_object", "target_object", target_object_type_attribute])
print("\nData points used for clustering")
print(df)

# Elbow method to determine optimal k
def determine_optimal_k(data, max_k=10):
    max_k = min(max_k, data.shape[0])
    distortions = []
    K = range(1, max_k + 1)
    for k in K:
        kmeans = KMeans(n_clusters=k, n_init="auto", random_state=42).fit(data)
        distortions.append(kmeans.inertia_)
    y_norm = (np.array(distortions) - min(distortions)) / (max(distortions) - min(distortions))
    line = np.linspace(y_norm[0], y_norm[-1], len(y_norm))
    distances = np.abs(y_norm - line)
    elbow_k = np.argmax(distances) + 1
    return elbow_k, distortions

# K-Means clustering for attribute values
try:
    df[target_object_type_attribute] = df[target_object_type_attribute].astype(float)
    is_numeric = True
except ValueError:
    is_numeric = False

if is_numeric:
    # numeric: StandardScaler + KMeans
    X = df[[target_object_type_attribute]].values
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    optimal_k, distortions = determine_optimal_k(X_scaled)
    print(f"\nOptimal k (elbow): {optimal_k}")

    kmeans = KMeans(n_clusters=optimal_k, n_init="auto", random_state=42)
    df["cluster"] = kmeans.fit_predict(X_scaled)

    if optimal_k > 1:
        sil = silhouette_score(X_scaled, df["cluster"])
        print(f"\nSilhouette score (k={optimal_k}): {sil}")
    else:
        print("\nSilhouette score not available for k=1.")
else:
    # categorical: each category = cluster
    df["cluster"] = df[target_object_type_attribute].astype(str)
    print(f"\nClusters assigned directly from categories: {df[target_object_type_attribute].unique()}")



# Count distinct data points per cluster
cluster_counts = df.groupby("cluster")[["resource_object", "target_object"]].nunique()
print("\nDistinct data points per cluster")
for c in cluster_counts.index:
    emp_count = cluster_counts.loc[c, "resource_object"]
    order_count = cluster_counts.loc[c, "target_object"]
    print(f"Cluster {c}: {emp_count} employees, {order_count} orders")

# Compute cluster-wise distribution per object of resource object type
emp_cluster_counts = (
    df.groupby(["resource_object", "cluster"])
      .size()
      .reset_index(name="count")
)
emp_totals = (
    df.groupby("resource_object")
      .size()
      .reset_index(name="total")
)
emp_stats = emp_cluster_counts.merge(emp_totals, on="resource_object")
emp_stats["percent"] = 100 * emp_stats["count"] / emp_stats["total"]
emp_stats = emp_stats.sort_values(["resource_object", "cluster"])

# Pivot table for cosine similarity
emp_stats_pivot = emp_stats.pivot(
    index="resource_object",
    columns="cluster",
    values="percent"
).fillna(0)

print("\nCluster-wise distribution per resource object (in percent)")
print(emp_stats_pivot)
# Compute min and max per cluster
cluster_stats = df.groupby("cluster")[target_object_type_attribute].agg(["min", "max", "count"]).reset_index()
print("\nCluster value ranges:")
for _, row in cluster_stats.iterrows():
    c = row["cluster"]
    mn = row["min"]
    mx = row["max"]
    n = row["count"]
    print(f"Cluster {c}: min={mn}, max={mx}, count of sitinct target objects={n}")

# Resource Similarity Graph
resource_ids = emp_stats_pivot.index.tolist()
resource_vectors = emp_stats_pivot.values
cos_sim_matrix = cosine_similarity(resource_vectors)

import pandas as pd
pd.set_option("display.precision", 3)   # 3 Nachkommastellen
cos_sim_df = pd.DataFrame(cos_sim_matrix, index=resource_ids, columns=resource_ids)
print("\nCosine Similarity Matrix")
print(cos_sim_df)

G = nx.Graph()
for i, res_id in enumerate(resource_ids):
    G.add_node(res_id)
for i, j in combinations(range(len(resource_ids)), 2):
    sim = cos_sim_matrix[i, j]
    if sim >= threshold:
        G.add_edge(resource_ids[i], resource_ids[j], attribute_value=sim)

print(f"\nGraph built with {G.number_of_nodes()} nodes and {G.number_of_edges()} edges (threshold={threshold})")

# Connected components = roles
components = list(nx.connected_components(G))
num_roles = len(components)
print(f"\nDetected {num_roles} subgroups based on resource similarity:")

role_summary = []
for idx, comp in enumerate(components, 1):
    comp_list = sorted(comp)
    print(f" Role {idx}: {comp_list}")
    role_orders = df[df["resource_object"].isin(comp_list)]
    min_max_per_cluster = role_orders.groupby("cluster")[target_object_type_attribute].agg(["min", "max"]).reset_index()
    print(f"  Cluster boundaries:")
    print(min_max_per_cluster)
    role_summary.append((comp_list, min_max_per_cluster))


# 9. Visualization
plt.figure(figsize=(12, 7))
pos = nx.spring_layout(G, seed=42)
nx.draw_networkx_nodes(G, pos, node_size=500, node_color="skyblue")
edges = G.edges(data=True)
nx.draw_networkx_edges(
    G,
    pos,
    edgelist=[(u, v) for u, v, d in edges],
    width=[d["attribute_value"] * 5 for u, v, d in edges],
    alpha=0.7
)
nx.draw_networkx_labels(G, pos, font_size=10)
edge_labels = {(u, v): f"{d['attribute_value']:.2f}" for u, v, d in edges}
nx.draw_networkx_edge_labels(G, pos, edge_labels=edge_labels, font_size=8)
plt.title(f"Resource Similarity Graph (Edges: cosine similarity ≥ {threshold})")
plt.axis("off")
plt.show()