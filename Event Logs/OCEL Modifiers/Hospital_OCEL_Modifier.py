# This script modifies the original Hospital Patient Lifecycle OCEL. It defines a new object type called "Hospital Personal" that includes the objects of the "Physician", "Nurse", and "LabTechnician"
# object types. These three object types then are deleted and the number of objects for each former type is reduced to six. To keep all events,
# the original objects of those former three object types are replaced with a corresponding remaining object. 
# nurse_55 thus is replaced with nurse_2 for instance.

import xml.etree.ElementTree as ET
import random
from pathlib import Path

# Specify input file here
input_file = Path(__file__).parent.parent / "Hospital_Patient_Lifecycle_original.xml"

# Process OCEL step by step
def process_ocel(input_file):

    # Generate output file automatically
    input_path = Path(input_file)
    output_file = input_path.parent / f"{input_path.stem.replace('original', 'adapted')}.xml"

    # Load XML file
    tree = ET.parse(input_file)
    root = tree.getroot()

    # Define types to merge
    types_to_replace = {"Physician", "Nurse", "LabTechnician"}
    new_type_name = "Hospital Personal"

    # Define allowed IDs for pruning
    allowed_ids = {
        "Physician": [f"physician_{i}" for i in range(1, 7)],
        "Nurse": [f"nurse_{i}" for i in range(1, 7)],
        "LabTechnician": [f"labtechnician_{i}" for i in range(1, 7)]
    }

    # Flatten allowed IDs
    all_allowed = [oid for sublist in allowed_ids.values() for oid in sublist]

    # Step 1: Update object-types section
    obj_types_section = root.find("object-types")
    if obj_types_section is not None:
        for obj_type in list(obj_types_section.findall("object-type")):
            if obj_type.get("name") in types_to_replace:
                obj_types_section.remove(obj_type)

        if not any(ot.get("name") == new_type_name for ot in obj_types_section.findall("object-type")):
            new_type_elem = ET.SubElement(obj_types_section, "object-type", {"name": new_type_name})
            ET.SubElement(new_type_elem, "attributes")

    # Step 2: Update and prune objects
    objects_section = root.find("objects")
    if objects_section is not None:
        for obj in list(objects_section.findall("object")):
            oid = obj.get("id")
            otype = obj.get("type")

            if otype in types_to_replace:
                if oid in all_allowed:
                    obj.set("type", new_type_name)
                else:
                    objects_section.remove(obj)

    # Step 3: Repair event references
    events_section = root.find("events")
    if events_section is not None:
        for ev in events_section.findall("event"):
            rels = ev.find("objects")
            if rels is None:
                continue

            for rel in rels.findall("relationship"):
                oid = rel.get("object-id")

                for prefix, pool in allowed_ids.items():
                    if oid.startswith(f"{prefix}_") and oid not in all_allowed:
                        new_id = random.choice(pool)
                        rel.set("object-id", new_id)
                        break

    # Step 4: Replace remaining type references in XML
    for elem in root.iter():
        if elem.get("type") in types_to_replace:
            elem.set("type", new_type_name)
        if elem.text in types_to_replace:
            elem.text = new_type_name

    # Save modified XML
    tree.write(output_file, encoding="UTF-8", xml_declaration=True)
    print(f"Processing complete. File saved to: {output_file}")


# Run script with input file specified at the top
process_ocel(input_file)