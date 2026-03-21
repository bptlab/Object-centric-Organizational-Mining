# This script creates the object type DFGs of all object types of the OCEL specified as input. Note that the script can
# have a long runtime when the OCEL has a large file size.

import xml.etree.ElementTree as ET
from datetime import datetime
import networkx as nx
from pathlib import Path

# 1. Read the XML file
ocel_path = Path(__file__).parent.parent.parent / "Event Logs" / "Hospital_Patient_Lifecycle_original.xml"
tree = ET.parse(ocel_path)
root = tree.getroot()

# Extract the base name from the input file (everything before _original or _adapted)
input_stem = ocel_path.stem 
if "_original" in input_stem:
    base_name = input_stem.split("_original")[0]
elif "_adapted" in input_stem:
    base_name = input_stem.split("_adapted")[0]
else:
    base_name = input_stem  

# 2. Extract all object types
object_types = [ot.get("name") for ot in root.findall(".//object-type")]
print(f"Found object types: {object_types}")

# 3. Build the object type DFG for each object type
for object_type in object_types:
    print(f"\n=== Processing object type: {object_type} ===")

    # Collect all objects of this type
    objects = {obj.get("id") for obj in root.findall(f".//object[@type='{object_type}']")}
    print(f"Found objects: {len(objects)}")

    # Create an empty directed graph
    G = nx.DiGraph()

    for obj_id in objects:
        # Collect all events related to this object
        obj_events = []
        for event in root.findall(".//event"):
            event_type = event.get("type")
            timestamp_str = event.get("time")
            if not timestamp_str:
                continue
            timestamp = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))

            # Check if the event is linked to the object
            rel_object_ids = [rel.get("object-id") for rel in event.findall("objects/relationship")]
            if obj_id in rel_object_ids:
                obj_events.append((timestamp, event_type))

        # Sort events by time
        obj_events.sort(key=lambda x: x[0])

        # Create edges for this objects object type DFG
        for i in range(len(obj_events) - 1):
            src_type = obj_events[i][1]
            tgt_type = obj_events[i + 1][1]

            # Add nodes if not already present
            if src_type not in G:
                G.add_node(src_type)
            if tgt_type not in G:
                G.add_node(tgt_type)

            # Add edge or increment weight if it exists
            if G.has_edge(src_type, tgt_type):
                G[src_type][tgt_type]["weight"] += 1
            else:
                G.add_edge(src_type, tgt_type, weight=1)

    # 4. Save the object type DFG as a .gexf file
    output_file = f"Object_Type_DFG_{base_name}_{object_type}.gexf"
    nx.write_gexf(G, output_file)
    print(f"Object type DFG for '{object_type}' saved as {output_file}")

print("\nAll object type DFGs have been created.")