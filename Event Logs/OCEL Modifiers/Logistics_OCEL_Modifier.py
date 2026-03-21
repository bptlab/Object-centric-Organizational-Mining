# This script modifies the original Logistics OCEL. It modifies the values of the "Weight" attribute of the "Container" object type based on a defined
# mapping from trucks to their allowed container weight range. 

import xml.etree.ElementTree as ET
import random
from pathlib import Path
from collections import defaultdict

input_file = Path(__file__).parent.parent / "Logistics_original.xml"

input_path = Path(input_file)
output_file = input_path.parent / f"{input_path.stem.replace('original', 'adapted')}.xml"

# Truck to container weight rules (min, max) per truck
truck_weight_rules = {
    "tr1": (1, 50),
    "tr2": (1, 50),
    "tr3": (200, 400),
    "tr4": (200, 400),
    "tr5": (700, 900),
    "tr6": (700, 900),
}

# Load ocel
tree = ET.parse(input_file)  # Parse xml
root = tree.getroot()

objects_section = root.find("objects")  # Get objects section
if objects_section is None:
    raise RuntimeError("No <objects> section found in OCEL log")

# Index objects
objects_by_id = {}  
object_types = {}   

for obj in objects_section.findall("object"):
    oid = obj.get("id")
    otype = obj.get("type")
    objects_by_id[oid] = obj
    object_types[oid] = otype

print(f"Loaded {len(objects_by_id)} objects.")

# Build truck to container mapping
truck_to_containers = defaultdict(set)  # Truck id --> set of container ids

for obj in objects_section.findall("object"):
    if obj.get("type") != "Truck":
        continue  # Skip non-truck objects

    truck_id = obj.get("id")
    rels = obj.find("objects")  # Get related objects
    if rels is None:
        continue

    for rel in rels.findall("relationship"):
        oid = rel.get("object-id")
        if object_types.get(oid) == "Container":
            truck_to_containers[truck_id].add(oid)

# Update second (latest) container weight
for truck_id, container_ids in truck_to_containers.items():

    low, high = truck_weight_rules[truck_id]

    for cr_id in container_ids:
        container_obj = objects_by_id.get(cr_id)
        if container_obj is None:
            continue

        attrs_xml = container_obj.find("attributes")  # Get attributes
        if attrs_xml is None:
            continue

        # Collect all weight attributes
        weight_attrs = [
            attr for attr in attrs_xml.findall("attribute")
            if attr.get("name") == "Weight"
        ]

        if not weight_attrs:
            continue  # Skip containers without weight

        # Modify only the last weight attribute 
        target_weight_attr = weight_attrs[-1]

        # Generate random weight within specified range
        if high is None:
            new_weight = random.uniform(low, low + 500)
        else:
            new_weight = random.uniform(low, high)

        target_weight_attr.text = f"{new_weight:.2f}"  # Update xml

# Save modified ocel
tree.write(output_file, encoding="utf-8", xml_declaration=True)
print(f"\nUpdated OCEL written to: {output_file}")