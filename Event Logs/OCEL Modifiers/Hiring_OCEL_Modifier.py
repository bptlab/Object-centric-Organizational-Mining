# This script modifies the original Hiring Lifecycle OCEL. It defines a new object type called "HR Employee" that includes the objects of the "Recruiter", "HiringManager", and "Interviewer"
# object types. These three object types then are deleted and the number of objects for the hiring managers is reduced to three, the number of 
# interviewers to six, and all recruiters are kept. To keep all events,
# the original objects of those former three object types are replaced with a corresponding remaining object. 
# HM010 thus is replaced with HM002 for instance.
# Moreover, the new attribute "Entry Level" is introduced for the "Candidate" object type, with possible values of "Associate" and "Senior".
# Based on occurences in the same events, all candidates that are handled by "Senior" recruiters get an entry level of "Senior".
# All candidates that are handled by "Junior" recruiters get an entry level of "Associate".

import xml.etree.ElementTree as ET
import random
from pathlib import Path

input_file = Path(__file__).parent.parent / "Hiring_original.xml"

input_path = Path(input_file)
output_file = input_path.parent / f"{input_path.stem.replace('original', 'adapted')}.xml"

candidate_objectType = "Candidate"

# Recruiter levels
recruiter_levels = {
    "R001": "Junior",
    "R002": "Senior",
    "R003": "Junior",
    "R004": "Senior",
    "R005": "Senior",
    "R006": "Junior",
    "R007": "Junior",
    "R008": "Senior",
    "R009": "Senior",
    "R010": "Senior",
}

# Mapping from recruiter level to Entry Level attribute
recruiter_level_mapping = {
    "Senior": "Senior",
    "Junior": "Associate"
}

# Object types to merge into HR Employee
types_to_replace = {"Recruiter", "HiringManager", "Interviewer"}
new_object_type = "HR Employee"

# Allowed IDs of remaining objects of each type
allowed_object_IDs = {
    "HiringManager": [f"HM00{i}" for i in range(1, 4)],
    "Interviewer": [f"I00{i}" for i in range(1, 7)],
    "Recruiter": [f"R{i:03d}" for i in range(1, 11)]
}

# Flatten allowed IDs, so they have no keys anymore
allowed_IDs_without_keys = [oid for sublist in allowed_object_IDs.values() for oid in sublist]

# Load OCEL
tree = ET.parse(input_file)
root = tree.getroot()

object_types_section = root.find("object-types")
objects_section = root.find("objects")
events_section = root.find("events")

if object_types_section is None or objects_section is None or events_section is None:
    raise RuntimeError("Invalid OCEL structure")

# 1. Update object-types section: merge HR roles
for obj_type in list(object_types_section.findall("object-type")):
    if obj_type.get("name") in types_to_replace:
        object_types_section.remove(obj_type)

if not any(ot.get("name") == new_object_type for ot in object_types_section.findall("object-type")):
    new_type_elem = ET.SubElement(object_types_section, "object-type", {"name": new_object_type})
    ET.SubElement(new_type_elem, "attributes")

# 2. Add Entry Level to Candidate object-type definition
for ot in object_types_section.findall("object-type"):
    if ot.get("name") != candidate_objectType:
        continue
    attrs = ot.find("attributes")
    if attrs is None:
        attrs = ET.SubElement(ot, "attributes")
    existing_attrs = {attr.get("name") for attr in attrs.findall("attribute")}
    if "Entry Level" not in existing_attrs:
        ET.SubElement(attrs, "attribute", name="Entry Level", type="string")

# 3. Update type of allowed objects (see allowed_object_IDs) to HR Employee and delete objects with too high ID
objects_by_id = {}
object_types = {}

for obj in list(objects_section.findall("object")):
    oid = obj.get("id")
    otype = obj.get("type")
    objects_by_id[oid] = obj
    object_types[oid] = otype

    if otype in types_to_replace:
        if oid in allowed_IDs_without_keys:
            obj.set("type", new_object_type)
            object_types[oid] = new_object_type
        else:
            objects_section.remove(obj)
            object_types.pop(oid, None)
            objects_by_id.pop(oid, None)

# 4. If an E2O relationship connected the event to an object with a removed ID, randomly replace it with an allowed ID from the same former object type (interviewer replaced with interviewer)
# Create a mapping for the ID prefixes used in the XML
id_prefix_map = {
    "HiringManager": "HM",
    "Recruiter": "R",
    "Interviewer": "I"
}

# 4. Repair event references
for event in events_section.findall("event"):
    rels = event.find("objects")
    if rels is None:
        continue
    for rel in rels.findall("relationship"):
        oid = rel.get("object-id")
        
        # Determine if this ID needs to be replaced
        for type_name, pool in allowed_object_IDs.items():
            shorthand = id_prefix_map[type_name]
            
            # Check if it starts with HM, R, or I
            if oid.startswith(shorthand):
                if oid not in allowed_IDs_without_keys:
                    new_id = random.choice(pool)
                    rel.set("object-id", new_id)
                break

# 5. Assign Entry Level to candidates based on recruiter levels
for event in events_section.findall("event"):
    rels = event.find("objects")
    if rels is None:
        continue
    candidate_ids = set()
    recruiter_ids = set()
    for rel in rels.findall("relationship"):
        oid = rel.get("object-id")
        otype = object_types.get(oid)
        if otype == candidate_objectType:
            candidate_ids.add(oid)
        elif otype == "HR Employee":
            recruiter_ids.add(oid)
    if not candidate_ids or not recruiter_ids:
        continue
    for candidate_id in candidate_ids:
        candidate_obj = objects_by_id[candidate_id]
        attrs_xml = candidate_obj.find("attributes")
        if attrs_xml is None:
            attrs_xml = ET.SubElement(candidate_obj, "attributes")
        for rid in recruiter_ids:
            recruiter_level = recruiter_levels.get(rid)
            if recruiter_level is None:
                continue
            entry_level = recruiter_level_mapping[recruiter_level]
            existing_entry = None
            for attr in attrs_xml.findall("attribute"):
                if attr.get("name") == "Entry Level":
                    existing_entry = attr
                    break
            if existing_entry is None:
                entry_attr = ET.SubElement(attrs_xml, "attribute", name="Entry Level")
                entry_attr.text = entry_level
            else:
                existing_entry.text = entry_level
            break

# 6. Replace remaining type references in XML
for elem in root.iter():
    if elem.get("type") in types_to_replace:
        elem.set("type", new_object_type)
    if elem.text in types_to_replace:
        elem.text = new_object_type

# 7. Save modified OCEL
tree.write(output_file, encoding="UTF-8", xml_declaration=True)
print(f"Processing complete. File saved to: {output_file}")