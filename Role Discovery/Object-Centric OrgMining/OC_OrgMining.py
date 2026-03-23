# 


import xml.etree.ElementTree as ET
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from collections import defaultdict, Counter
from sklearn.preprocessing import normalize
from scipy.cluster.hierarchy import linkage, dendrogram, fcluster
from pathlib import Path


resource_object_type = "Hospital Personal"
input_file = Path(__file__).parent.parent.parent / "Event Logs" / "Hospital_Patient_Lifecycle_adapted.xml"
case_types = {
    # "Order": {
    #     "price": [
    #         (1.25, 99.86, "cheap"),
    #         (10001.37, 11998.77, "luxury"),
    #     ]
    # },  
    # "Package": {
    #     "weight": [
    #         (0.11, 4.9, "light"),
    #         (10.11, 20, "heavy"),
    #     ]
    # },  
    # "Container": {
    #     "Weight": [
    #         (1.03,  49.81, "light"),
    #         (200.64,  399.08, "medium"),
    #         (700.01,  899.9, "heavy"),
    #         ]
    #         }, 
    # "Candidate": {
    #     "Entry Level": [
    #         ("Associate", "Associate", "Associate"),
    #         ("Senior", "Senior", "Senior"),
    #         ]
    #         }, 
}


def map_to_case_type(value, ranges):
    if value is None:
        return "NaN"
    
    # Falls Wert bereits textuell, prüfe auf Match in den Kategorien
    for lower, upper, label in ranges:
        # Für kategoriale Werte setzen wir lower == upper == label
        if isinstance(value, str):
            if value == label:
                return label
        else:
            # sonst wie bisher für numerische Intervalle
            try:
                value_num = float(value)
                l = float(lower) if lower is not None else -np.inf
                u = float(upper) if upper is not None else np.inf
                if l <= value_num <= u:
                    return label
            except (TypeError, ValueError):
                continue
    return "NaN"

# Load & extract data
tree = ET.parse(input_file)
root = tree.getroot()

# Extract objects and events sections
objects_section = root.find("objects")
events_section = root.find("events")

resource_ids = set()
object_types = {}
object_attributes = {}

# Extract objects and attributes
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

# Initialize execution mode dictionary: For every resource object store exectuion modes with count
execution_modes_full = defaultdict(Counter)
execution_modes_act = defaultdict(Counter)

# Go over all events
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
            execution_modes_act[rid][(relation_type, event_type)] += 1
            execution_modes_full[rid][(case_dimension, relation_type, event_type)] += 1

df_act = pd.DataFrame.from_dict(execution_modes_act, orient="index").fillna(0)
df_full = pd.DataFrame.from_dict(execution_modes_full, orient="index").fillna(0)


# OUTPUT DIRECTORY (same folder as input file)
output_dir = Path(__file__).resolve().parent
# File names (adapted from input file name)
base_name = input_file.stem  # e.g., "Order_Management_adapted"

act_file = output_dir / f"{base_name}_ResourceXExecMode_stage1.csv"
full_file = output_dir / f"{base_name}_ResourceXExecMode_stage2.csv"

# Save matrices
df_act.to_csv(act_file)
df_full.to_csv(full_file)

print(f"Saved activity matrix to: {act_file}")
print(f"Saved full matrix to: {full_file}")

#print(df_act.to_string())


# STUFE 1: DENDROGRAMM MIT SICHTBARKEITS-FIX & DEINEM STYLE
Z_act = linkage(df_act, method='average', metric='cosine')

# Epsilon für die Log-Skala (verhindert das Verschwinden von 0-Distanzen)
epsilon_vis = 1e-7

# Erstelle eine Kopie für die Visualisierung mit minimalem Offset
Z_act_vis = Z_act.copy()
Z_act_vis[:, 2] = Z_act[:, 2] + epsilon_vis

plt.figure(figsize=(8, 4))

# Plot the dendrogram
dend = dendrogram(
    Z_act_vis,
    labels=df_act.index.tolist(),
)

# Logarithmische Skalierung
plt.yscale("log")

# Limits setzen: Untergrenze ist unser epsilon_vis, Obergrenze 1.0
plt.ylim(epsilon_vis, 1.0)

# Ticks setzen (der unterste Tick wird als "0" beschriftet, obwohl er technisch epsilon ist)
plt.yticks(
            [1e-6, 1e-5, 1e-4, 1e-3, 1e-2, 1e-1, 1], 
            ["1e-6", "1e-5", "1e-4", "0.001", "0.01", "0.1", "1"], 
            fontsize=14
)

plt.xticks(fontsize=14, rotation=90)
plt.ylabel("Cosine Distance", fontsize=14)


# Linienstärke für die Verbindungen (Zweige)
plt.setp(plt.gca().get_lines(), linewidth=4)

# Linienstärke für die vertikalen Linien am Boden (Collections)
for coll in plt.gca().collections:
    coll.set_linewidth(4)
# --------------------

plt.tight_layout()
plt.show()

base_clusters = fcluster(Z_act, t=0.4, criterion='distance')
df_full["Base_Cluster"] = base_clusters



# STUFE 2: SUB-CLUSTERING MIT GEWICHTETEN SUB-ROLLEN-SPALTEN
unique_base_clusters = np.unique(base_clusters)
all_sub_max = []  # globales Maximum sammeln
feature_cols = [c for c in df_full.columns if c not in ["Base_Cluster", "Final_Cluster"]]

# Zuerst alle Sub-Cluster Distanzen sammeln
for bc in unique_base_clusters:
    resources_in_bc = df_full[df_full["Base_Cluster"] == bc].index
    if len(resources_in_bc) > 1:
        sub_df = df_full.loc[resources_in_bc, feature_cols].copy()
        
        
        subrolle_spalten_indices = [
            i for i, col in enumerate(sub_df.columns)
            if (sub_df[col] == 0).any() and (sub_df[col] > 0).any()
        ]
        
        weights = np.ones(sub_df.shape[1])
        weights[subrolle_spalten_indices] = 10
        
        X_weighted = sub_df.values * weights
        
        Z_sub = linkage(X_weighted, method='average', metric='cosine')
        all_sub_max.append(np.max(Z_sub[:, 2]))

# 2Globales Maximum
global_max = max(all_sub_max)
epsilon = 1e-6  # gegen log(0)

# Nun Plot & Cluster-Zuweisung für jeden Sub-Cluster
for bc in unique_base_clusters:
    resources_in_bc = df_full[df_full["Base_Cluster"] == bc].index
    if len(resources_in_bc) > 1:
        sub_df = df_full.loc[resources_in_bc, feature_cols].copy()
        
        
        
        subrolle_spalten_indices = [
            i for i, col in enumerate(sub_df.columns)
            if (sub_df[col] == 0).any() and (sub_df[col] > 0).any()
        ]
        
        weights = np.ones(sub_df.shape[1])
        weights[subrolle_spalten_indices] = 10
        
        X_weighted = sub_df.values * weights
        X_norm = normalize(X_weighted, axis=1)
        
        
        Z_sub = linkage(X_norm, method='average', metric='cosine')
        

        # Dendrogramm Plot
        plt.figure(figsize=(8, 4))
        dendrogram(
            Z_sub,
            labels=resources_in_bc.tolist(),
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
        

        # Cluster-Zuweisung auf ORIGINAL-Distanzen
        sub_labels = fcluster(Z_sub, t=0.1, criterion='distance')
        for i, rid in enumerate(resources_in_bc):
            df_full.at[rid, "Final_Cluster"] = f"{bc}.{sub_labels[i]}"
    else:
        df_full.at[resources_in_bc[0], "Final_Cluster"] = f"{bc}.0"