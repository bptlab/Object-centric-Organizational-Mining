# This script analyzes the cluster tendency of all attributes of all object types except the currently analyzed resource object type by computing
# the Hopkins statistics value per attribute.
# It only calculates a value if the objects of the resource object type are connected to objects of the currently analyzed object type.


import xml.etree.ElementTree as ET
import numpy as np
from sklearn.preprocessing import StandardScaler
from sklearn.neighbors import NearestNeighbors
from pathlib import Path
import pandas as pd
import networkx as nx

# Specify rtesource object type that should be analyzed in role discovery
analyzed_resource_object_type = "Employee"  
input_file = Path(__file__).parent.parent.parent / "Event Logs" / "Order_Management_adapted.xml"

# Hopkins score function
def hopkins_statistic(data, n_samples=None, random_state=None):
    rng = np.random.default_rng(random_state)

    if len(data) < 10:
        return np.nan

    X = data.reshape(-1, 1)
    X = StandardScaler().fit_transform(X)
    n = X.shape[0]

    if n_samples is None:
        n_samples = min(max(int(0.1 * n), 20), n - 1)

    nn = NearestNeighbors(n_neighbors=2).fit(X)

    idx = rng.choice(n, size=n_samples, replace=False)
    xi = [nn.kneighbors(X[i].reshape(1, -1), 2)[0][0][1] for i in idx]

    mins = X.min(axis=0)
    maxs = X.max(axis=0)
    random_X = rng.uniform(mins, maxs, size=(n_samples, X.shape[1]))
    yi = [nn.kneighbors(pt.reshape(1, -1), 1)[0][0][0] for pt in random_X]

    return np.sum(yi) / (np.sum(xi) + np.sum(yi))


# Load OCEL
tree = ET.parse(Path(input_file))
root = tree.getroot()

objects_section = root.find("objects")
events_section = root.find("events")
current_target_object_types_section = root.find("object-types")

if objects_section is None:
    raise RuntimeError("No <objects> section found.")

if current_target_object_types_section is None:
    raise RuntimeError("No <object-types> section found.")


# Extract object types whose attributes should be analyzed
all_current_target_object_types = [
    ot.get("name") for ot in current_target_object_types_section.findall("object-type")
]

target_current_target_object_types = [
    t for t in all_current_target_object_types if t != analyzed_resource_object_type
]


# Extract objects and their attributes
current_target_object_types = {}
object_attributes = {}

for obj in objects_section.findall("object"):
    oid = obj.get("id")
    current_target_object_types[oid] = obj.get("type")

    attrs = {}
    attrs_xml = obj.find("attributes")
    if attrs_xml is not None:
        for a in attrs_xml.findall("attribute"):
            attrs[a.get("name")] = a.text

    object_attributes[oid] = attrs


# Build O2O graoh
O2O = nx.Graph()

for obj in objects_section.findall("object"):
    oid = obj.get("id")
    O2O.add_node(oid, type=obj.get("type"))

for obj in objects_section.findall("object"):
    oid = obj.get("id")
    inner = obj.find("objects")

    if inner is not None:
        for rel in inner.findall("relationship"):
            target = rel.get("object-id")
            if target in O2O:
                O2O.add_edge(oid, target)


# Loop over all object types
for current_target_object_type in target_current_target_object_types:

    print("\n---------------------------------")
    print(f"Processing object type: {current_target_object_type}")

    # Find out if objects of resource object type is connected to objects of the current_target_object_type in O2O graph
    o2o_pairs = []

    for u, v in O2O.edges():
        tu = O2O.nodes[u]["type"]
        tv = O2O.nodes[v]["type"]

        if tu == analyzed_resource_object_type and tv == current_target_object_type:
            o2o_pairs.append((u, v))
        elif tu == current_target_object_type and tv == analyzed_resource_object_type:
            o2o_pairs.append((v, u))

    event_pairs = []

    # Find out if objects of resource object type is connected to objects of the current_target_object_type via event-based relationships
    for ev in events_section.findall("event"):
        rels = ev.find("objects")
        if rels is None:
            continue

        resources = set()
        targets = set()

        for rel in rels.findall("relationship"):
            oid = rel.get("object-id")
            otype = current_target_object_types.get(oid)

            if otype == analyzed_resource_object_type:
                resources.add(oid)
            elif otype == current_target_object_type:
                targets.add(oid)

        for r in resources:
            for t in targets:
                event_pairs.append((r, t))

    # Store connected objects
    all_pairs = set(o2o_pairs + event_pairs)
    connected_objects = {obj for _, obj in all_pairs}

    # Find the numeric attributes of the current_target_object_type
    numeric_attributes = set()

    for oid, attrs in object_attributes.items():
        if current_target_object_types.get(oid) != current_target_object_type:
            continue
        if oid not in connected_objects:
            continue

        for k, v in attrs.items():
            try:
                float(v)
                numeric_attributes.add(k)
            except (TypeError, ValueError):
                pass

    numeric_attributes = sorted(numeric_attributes)

    print("Numeric attributes:")
    for attr in numeric_attributes:
        print("-", attr)

    # Collect values of numeric attributes
    attribute_values = {attr: [] for attr in numeric_attributes}

    for oid, attrs in object_attributes.items():
        if current_target_object_types.get(oid) != current_target_object_type:
            continue

        # If object not connected to any object  of analyzed resource object type, skip --> prevents that Hopkins statistics in computed 
        # for object types whose objects are not connected to the analyzed resource object type
        if oid not in connected_objects:
            continue

        for attr in numeric_attributes:
            val = attrs.get(attr)
            if val is None:
                continue

            try:
                attribute_values[attr].append(float(val))
            except ValueError:
                continue

    # Calculate Hopkins statistic value
    print("\n--- Hopkins Coefficient per Attribute ---")

    results = []

    for attr, values in attribute_values.items():
        values_array = np.array(values)

        if len(values_array) < 10:
            print(f"{attr}: skipped ({len(values_array)} datapoints)")
            results.append((attr, np.nan))
            continue

        H = hopkins_statistic(values_array, random_state=42)
        results.append((attr, H))

        print(f"{attr}: Hopkins = {H:.4f}")

    summary = (
        pd.DataFrame(results, columns=["attribute", "hopkins"])
        .sort_values("hopkins", ascending=False, na_position="last")
    )

    print("\n=== Summary ===")
    print(summary)