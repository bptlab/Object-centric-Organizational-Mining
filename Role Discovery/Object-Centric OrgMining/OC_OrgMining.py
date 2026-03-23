# This script implements the two stage Object-Centric OrgMining approach for the discovery of roles in OCELs
# Analysts need to specify the resource object type for which roles should be found, the input file, and the case types
# with ranges and labels (the case types for the example OCELs are already specified based on the preparatory steps). For categorical attributes, just use the category label as 
# ranges: ("Associate", "Associate", "Associate")
# The matrices for both stages are stored in the same folder as csv files.
# the first dendrogram shpows the general roles. Based on the defined cut-off score in row 203, the general roles are defined and
# analyzed in-depth in the second stage. Here, one dendrogram is plotted for each general role. Analysts can define subroles
# based on these dendrograms and their own cut-off scores.


import xml.etree.ElementTree as ET
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from collections import defaultdict, Counter
from sklearn.preprocessing import normalize
from scipy.cluster.hierarchy import linkage, dendrogram, fcluster
from pathlib import Path


resource_object_type = "Employee"
input_file = Path(__file__).parent.parent.parent / "Event Logs" / "Order_Management_adapted.xml"
case_types = {
    # Case types for Order Management OCEL
    "Order": {
        "price": [
            (1.25, 99.86, "cheap"),
            (10001.37, 11998.77, "luxury"),
        ]
    },  
    "Package": {
        "weight": [
            (0.11, 4.9, "light"),
            (10.11, 20, "heavy"),
        ]
    },  

    # Case types for Logistics OCEL
    # "Container": {
    #     "Weight": [
    #         (1.03,  49.81, "light"),
    #         (200.64,  399.08, "medium"),
    #         (700.01,  899.9, "heavy"),
    #         ]
    #         }, 

    # Case types for Hiring OCEL
    # "Candidate": {
    #     "Entry Level": [
    #         ("Associate", "Associate", "Associate"),
    #         ("Senior", "Senior", "Senior"),
    #         ]
    #         }, 
}

# Map attribute value to case type
def map_to_case_type(value, ranges):
    if value is None:
        return "NaN"
    
    # If value is already textual, check for a direct match in the categories
    for lower, upper, label in ranges:
        if isinstance(value, str):
            if value == label:
                return label
        else:
            # Otherwise, handle numeric intervals 
            try:
                value_num = float(value)
                l = float(lower) if lower is not None else -np.inf
                u = float(upper) if upper is not None else np.inf
                if l <= value_num <= u:
                    return label
            except (TypeError, ValueError):
                continue
    return "NaN"

# Load and extract data
tree = ET.parse(input_file)
root = tree.getroot()

# Extract objects and events sections
objects_section = root.find("objects")
events_section = root.find("events")

resource_ids = set()
object_types = {}
object_attributes = {}

# Extract objects and their attributes
for obj in objects_section.findall("object"):
    oid, otype = obj.get("id"), obj.get("type")
    object_types[oid] = otype
    attrs = {}
    attrs_xml = obj.find("attributes")
    if attrs_xml is not None:
        for attr in attrs_xml.findall("attribute"):
            try: attrs[attr.get("name")] = float(attr.text)
            except: attrs[attr.get("name")] = attr.text
    object_attributes[oid] = attrs
    # Identify resource objects
    if otype == resource_object_type:
        resource_ids.add(oid)



# Resource x Execution Mode matrix computation:

# Initialize execution mode dictionaries:
# For every resource object, store execution modes with counts
execution_modes_stage2 = defaultdict(Counter)
execution_modes_stage1 = defaultdict(Counter)

# Iterate over all events
for ev in events_section.findall("event"):
    event_type = ev.get("type")
    rels = ev.find("objects")

    # Skip events without relationships
    if rels is None: continue

    # Initialize case dimensions with default values
    case_dimensions = {f"{ot}.{an}": "NaN" for ot, atts in case_types.items() for an in atts}
    
    for rel in rels.findall("relationship"):
        oid = rel.get("object-id")
        otype = object_types.get(oid)
        if otype in case_types:
            for attr_name, ranges in case_types[otype].items():
                label = map_to_case_type(object_attributes.get(oid, {}).get(attr_name), ranges)
                case_dimensions[f"{otype}.{attr_name}"] = label

    case_dimension = " | ".join(f"{d}={v}" for d, v in sorted(case_dimensions.items()))

    for rel in rels.findall("relationship"):
        rid = rel.get("object-id")
        if rid in resource_ids:
            rel_type = rel.get("qualifier", "NoQualifier")
            relation_type = f"{rel_type}.{event_type}"
            execution_modes_stage1[rid][(relation_type, event_type)] += 1
            execution_modes_stage2[rid][(case_dimension, relation_type, event_type)] += 1

# Transform execution_modes_stage1 and execution_modes_stage2 in Data Frames for further analysis and excel output
df_stage1 = pd.DataFrame.from_dict(execution_modes_stage1, orient="index").fillna(0)
df_stage2 = pd.DataFrame.from_dict(execution_modes_stage2, orient="index").fillna(0)


# Output directory for matrices (same folder as this script)
output_dir = Path(__file__).resolve().parent

base_name = input_file.stem 

act_file = output_dir / f"{base_name}_ResourceXExecMode_stage1.csv"
full_file = output_dir / f"{base_name}_ResourceXExecMode_stage2.csv"

# Save matrices to CSV files
df_stage1.to_csv(act_file)
df_stage2.to_csv(full_file)

print(f"Saved activity matrix to: {act_file}")
print(f"Saved full matrix to: {full_file}")

# print(df_stage1.to_string())



# --------------- Stage 1 OC OrgMining ---------------

# Configuration of AHC, run on df_stage1 (abstracted resource x execution mode matrix with only activity and relation types)
Z_act = linkage(df_stage1, method='average', metric='cosine')

# Epsilon for log scale (prevents disappearance of near zero distances)
epsilon_vis = 1e-7
Z_act_vis = Z_act.copy()
Z_act_vis[:, 2] = Z_act[:, 2] + epsilon_vis

# Size of dendrogram
plt.figure(figsize=(14, 10))

# Plot dendrogram
dend = dendrogram(
    Z_act_vis,
    labels=df_stage1.index.tolist(),
)

# Logarithmic scaling
plt.yscale("log")

# Set limits: lower bound is epsilon_vis, upper bound is 1.0
plt.ylim(epsilon_vis, 1.0)

# Set ticks on y-axis
plt.yticks(
            [1e-6, 1e-5, 1e-4, 1e-3, 1e-2, 1e-1, 1], 
            ["1e-6", "1e-5", "1e-4", "0.001", "0.01", "0.1", "1"], 
            fontsize=14
)

plt.xticks(fontsize=14, rotation=90)
plt.ylabel("Cosine Distance", fontsize=14)

# Line width for dendrogram branches
plt.setp(plt.gca().get_lines(), linewidth=4)

for coll in plt.gca().collections:
    coll.set_linewidth(4)

plt.tight_layout()
plt.show()

# Assign clusters after stage 1 --> t = Cut-off score for dendrogram that causes split into clusters below that score
stage1_clusters = fcluster(Z_act, t=0.4, criterion='distance')
df_stage2["Stage1_Cluster"] = stage1_clusters



# --------------- Stage 2 OC OrgMining ---------------
# unique_stage1_clusters = number of general role clusters after stage 1
unique_stage1_clusters = np.unique(stage1_clusters)
# Select only feature columns with execution mode counts
feature_cols = [c for c in df_stage2.columns if c not in ["Stage1_Cluster", "Final_Cluster"]]

# Loop over each stage 1 general role cluster
for cluster in unique_stage1_clusters:
    # Get resource objects of current cluster
    resources_in_cluster = df_stage2[df_stage2["Stage1_Cluster"] == cluster].index

    # Only proceed if more than 1 resource object in cluster
    if len(resources_in_cluster) > 1:
        # Build horizontal sub matrix with only rows for resource objects that are in current cluster
        sub_df = df_stage2.loc[resources_in_cluster, feature_cols].copy()
        
        # Identify important columns where at least one resource has a zero and another >0 (columns with both 0 and >0 values)
        important_column_indices = [
            i for i, col in enumerate(sub_df.columns)
            if (sub_df[col] == 0).any() and (sub_df[col] > 0).any()
        ]
        
        # Create weights for important columns
        weights = np.ones(sub_df.shape[1])
        weights[important_column_indices] = 10
        # Apply weights
        X_weighted = sub_df.values * weights
        
        # Perform AHC with weighted columns
        Z_sub = linkage(X_weighted, method='average', metric='cosine')

        epsilon = 1e-6  # avoid log(0)

        # Plot dendrogram
        plt.figure(figsize=(14, 10))
        dendrogram(
            Z_sub,
            labels=resources_in_cluster.tolist(),
            leaf_rotation=90
        )
        plt.yscale("log")
        plt.ylim(epsilon, 1)
        plt.yticks(
            [1e-6, 1e-5, 1e-4, 1e-3, 1e-2, 1e-1, 1], 
            ["1e-6", "1e-5", "1e-4", "0.001", "0.01", "0.1", "1"], 
            fontsize=14
        )
        plt.ylabel("Cosine Distance", fontsize=14)
        plt.xticks(fontsize=14) 
        
        plt.setp(plt.gca().get_lines(), linewidth=4)
        for coll in plt.gca().collections:
            coll.set_linewidth(4)
        
        plt.tight_layout()
        plt.show()
        
    #     # Cluster assignment based on original distances
    #     sub_labels = fcluster(Z_sub, t=0.1, criterion='distance')
    #     for i, rid in enumerate(resources_in_cluster):
    #         df_stage2.at[rid, "Final_Cluster"] = f"{cluster}.{sub_labels[i]}"
    # else:
    #     df_stage2.at[resources_in_cluster[0], "Final_Cluster"] = f"{cluster}.0"
