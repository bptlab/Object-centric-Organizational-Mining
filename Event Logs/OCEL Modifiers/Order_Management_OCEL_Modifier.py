# This script modifies the original Order Management OCEL and does the following adaptions:
# - Adds a new object type "Truck" and 6 truck objects.
# - Randomly assigns trucks to send package events.
# - Assigns trucks to failed delivery and package delivered events (by keeping the connection between package-truck based on previous assignment to send package events).
# - Removes all product objects and any references to them.
# - Adds customer relationships to pay order events.
# - Adds driver relationships to trucks and updates the OCEL schema.
# - Adds sender relationships to payment reminder events and updates the OCEL schema.
# - Adjusts order prices based on employee groups.
# - Adjusts package weights based on employee involvement in specific events.

# Note that after the modification, the object type and event type names were changed manually. 
# All event type names were changed from lowercase to title case: for instance, "send package" to "Send Package"
# All object type names were changed from lowercase and plural to the capitalized singular form: for instance, "employees" to "Employee"

import xml.etree.ElementTree as ET
import random
from pathlib import Path
import networkx as nx


input_file = Path(__file__).parent.parent / "Order_Management_original.xml"
input_path = Path(input_file)
output_file = input_path.parent / f"{input_path.stem.replace('original', 'adapted1')}.xml"

truck_IDs = [f"Truck{i}" for i in range(1, 7)]

# Employee price groups
low_price_employees = {"Christine von Dobbert", "Jan Niklas Adams"}
high_price_employees = {"Mara Nitschke", "Istvan Koren", "Wil van der Aalst"}

# Employees for heavy packages
target_heavy_employees = {"Detlef Wetzeler", "Christopher Schwanen", "Benedikt Knopp"}
heavy_events = {"create package", "send package"}


# Load XML
tree = ET.parse(input_file)
root = tree.getroot()
objects_section = root.find("objects")
events_section = root.find("events")


# 1. Add object-type "trucks"

object_types_section = root.find("object-types")
truck_type = ET.SubElement(object_types_section, "object-type", {"name": "trucks"})
ET.SubElement(truck_type, "attributes")  # empty attributes


# 2. Add truck objects

for truck_id in truck_IDs:
    truck_obj = ET.SubElement(objects_section, "object", {"id": truck_id, "type": "trucks"})
    ET.SubElement(truck_obj, "attributes")
    ET.SubElement(truck_obj, "objects")


# 3. Assign trucks to "send package" events

for event in events_section.findall("event"):
    if event.get("type") == "send package":
        chosen_truck = random.choice(truck_IDs)
        event_objects = event.find("objects")
        if event_objects is None:
            event_objects = ET.SubElement(event, "objects")
        ET.SubElement(event_objects, "relationship", {"object-id": chosen_truck, "qualifier": "truck"})


# 4. Propagate truck assignments to package and delivery events

package_to_truck = {}
for event in events_section.findall("event"):
    if event.get("type") == "send package":
        event_objects = event.find("objects")
        if event_objects is None:
            continue
        package_id = truck_id = None
        for rel in event_objects.findall("relationship"):
            if rel.get("qualifier") in {"shipped package", "package"}:
                package_id = rel.get("object-id")
            elif rel.get("qualifier") == "truck":
                truck_id = rel.get("object-id")
        if package_id:
            if truck_id is None:
                truck_id = random.choice(truck_IDs)
                ET.SubElement(event_objects, "relationship", {"object-id": truck_id, "qualifier": "truck"})
            package_to_truck[package_id] = truck_id

for event in events_section.findall("event"):
    if event.get("type") in {"failed delivery", "package delivered"}:
        event_objects = event.find("objects")
        if event_objects is None:
            continue
        package_id = None
        for rel in event_objects.findall("relationship"):
            if rel.get("qualifier") in {"shipped package", "package"}:
                package_id = rel.get("object-id")
                break
        if package_id in package_to_truck:
            truck_id = package_to_truck[package_id]
            if not any(r.get("qualifier") == "truck" for r in event_objects.findall("relationship")):
                ET.SubElement(event_objects, "relationship", {"object-id": truck_id, "qualifier": "truck"})

# Assign trucks to package objects
for obj in objects_section.findall("object"):
    if obj.get("type") == "packages":
        pid = obj.get("id")
        if pid in package_to_truck:
            truck_id = package_to_truck[pid]
            obj_objects = obj.find("objects")
            if obj_objects is None:
                obj_objects = ET.SubElement(obj, "objects")
            if not any(r.get("qualifier") == "truck" for r in obj_objects.findall("relationship")):
                ET.SubElement(obj_objects, "relationship", {"object-id": truck_id, "qualifier": "truck"})


# 5. Remove products

for obj_types in root.findall(".//object-types"):
    for obj_type in list(obj_types):
        if obj_type.attrib.get("name") == "products":
            obj_types.remove(obj_type)

product_ids = {obj.get("id") for obj in objects_section.findall("object") if obj.get("type") == "products"}
for parent in root.findall(".//objects"):
    for obj in list(parent):
        if obj.tag == "object" and obj.get("type") == "products":
            parent.remove(obj)
    for rel in list(parent):
        if rel.tag == "relationship" and (rel.get("qualifier") == "product" or rel.get("object-id") in product_ids):
            parent.remove(rel)

for event in events_section.findall("event"):
    for objs in event.findall("objects"):
        for rel in list(objs):
            if rel.tag == "relationship" and (rel.get("qualifier") == "product" or rel.get("object-id") in product_ids):
                objs.remove(rel)


# 6. Add customer relations to pay order events

order_to_customer = {}
for obj in objects_section.findall("object"):
    if obj.get("type") == "customers":
        cid = obj.get("id")
        rels = obj.find("objects")
        if rels is not None:
            for rel in rels.findall("relationship"):
                oid = rel.get("object-id")
                if oid:
                    order_to_customer[oid] = cid

for etype in root.findall(".//event-type"):
    if etype.get("name") == "pay order":
        objs = etype.find("objects")
        if objs is None:
            objs = ET.SubElement(etype, "objects")
        if not any(r.get("object-type") == "customers" for r in objs.findall("relationship")):
            ET.SubElement(objs, "relationship", {"object-type": "customers", "qualifier": "customer"})

for event in events_section.findall("event"):
    if event.get("type") != "pay order":
        continue
    objs = event.find("objects")
    if objs is None:
        continue
    order_id = next((r.get("object-id") for r in objs.findall("relationship") if r.get("qualifier") == "order"), None)
    if order_id and order_id in order_to_customer:
        customer_id = order_to_customer[order_id]
        if not any(r.get("object-id") == customer_id for r in objs.findall("relationship")):
            ET.SubElement(objs, "relationship", {"object-id": customer_id, "qualifier": "customer"})


# 7. Add driver relations to trucks

truck_to_drivers = {}
for event in events_section.findall("event"):
    if event.get("type") != "send package":
        continue
    objs = event.find("objects")
    if objs is None:
        continue
    truck_id = None
    drivers = []
    for rel in objs.findall("relationship"):
        if rel.get("qualifier") == "truck":
            truck_id = rel.get("object-id")
        elif rel.get("qualifier") == "shipper":
            drivers.append(rel.get("object-id"))
    if truck_id and drivers:
        truck_to_drivers.setdefault(truck_id, set()).update(drivers)

for ot in root.findall(".//object-type"):
    if ot.get("name") == "trucks":
        objs = ot.find("objects") or ET.SubElement(ot, "objects")
        if not any(r.get("object-type") == "employees" for r in objs.findall("relationship")):
            ET.SubElement(objs, "relationship", {"object-type": "employees", "qualifier": "driver"})

for obj in objects_section.findall("object"):
    if obj.get("type") != "trucks":
        continue
    tid = obj.get("id")
    drivers = truck_to_drivers.get(tid)
    if not drivers:
        continue
    obj_objects = obj.find("objects") or ET.SubElement(obj, "objects")
    existing = {r.get("object-id") for r in obj_objects.findall("relationship")}
    for d in drivers:
        if d not in existing:
            ET.SubElement(obj_objects, "relationship", {"object-id": d, "qualifier": "driver"})


# 8. Add sender relations to payment reminder events

order_to_sales = {}
for event in events_section.findall("event"):
    if event.get("type") != "confirm order":
        continue
    objs = event.find("objects")
    if objs is None:
        continue
    order_id = None
    employee_id = None
    for rel in objs.findall("relationship"):
        if rel.get("qualifier") == "order":
            order_id = rel.get("object-id")
        elif rel.get("qualifier") == "sales person":
            employee_id = rel.get("object-id")
    if order_id and employee_id:
        order_to_sales[order_id] = employee_id

for etype in root.findall(".//event-type"):
    if etype.get("name") == "payment reminder":
        objs = etype.find("objects") or ET.SubElement(etype, "objects")
        if not any(r.get("object-type") == "employees" and r.get("qualifier") == "sender" for r in objs.findall("relationship")):
            ET.SubElement(objs, "relationship", {"object-type": "employees", "qualifier": "sender"})

for event in events_section.findall("event"):
    if event.get("type") != "payment reminder":
        continue
    objs = event.find("objects")
    if objs is None:
        continue
    order_id = next((r.get("object-id") for r in objs.findall("relationship") if r.get("qualifier") == "order"), None)
    if order_id and order_id in order_to_sales:
        emp_id = order_to_sales[order_id]
        if not any(r.get("object-id") == emp_id for r in objs.findall("relationship")):
            ET.SubElement(objs, "relationship", {"object-id": emp_id, "qualifier": "sender"})


# 9. Adjust order prices

# Build O2O graph to map employees to orders
O2O = nx.Graph()
# Dictionary to store object types for quick lookup
object_types_map = {}

for obj in objects_section.findall("object"):
    oid, otype = obj.get("id"), obj.get("type")
    O2O.add_node(oid, type=otype)
    object_types_map[oid] = otype

# Build edges from object relationships
for obj in objects_section.findall("object"):
    oid = obj.get("id")
    # Corrected: Search within the 'objects' tag for 'relationship' tags
    inner = obj.find("objects")
    if inner is not None:
        for rel in inner.findall("relationship"):
            target = rel.get("object-id")
            if target in O2O:
                O2O.add_edge(oid, target)

employee_orders = {}
# Populate from O2O Graph
for u, v in O2O.edges():
    type_u = O2O.nodes[u]["type"]
    type_v = O2O.nodes[v]["type"]
    if type_u == "employees" and type_v == "orders":
        employee_orders.setdefault(u, set()).add(v)
    elif type_v == "employees" and type_u == "orders":
        employee_orders.setdefault(v, set()).add(u)

# Populate from Events (to capture temporal relationships not in O2O)
for event in events_section.findall("event"):
    event_objs = event.find("objects")
    if event_objs is None:
        continue
    
    event_employees = set()
    event_orders = set()
    
    for rel in event_objs.findall("relationship"):
        oid = rel.get("object-id")
        otype = object_types_map.get(oid)
        if otype == "employees":
            event_employees.add(oid)
        elif otype == "orders":
            event_orders.add(oid)
            
    for emp in event_employees:
        if emp not in employee_orders:
            employee_orders[emp] = set()
        employee_orders[emp].update(event_orders)

# Assign prices
for obj in objects_section.findall("object"):
    if obj.get("type") != "orders":
        continue
    oid = obj.get("id")
    
    # Check which employees are linked to this specific order ID
    linked_employees = [emp for emp, orders in employee_orders.items() if oid in orders]
    
    if not linked_employees:
        continue
        
    # Use the first linked employee to determine the price bracket
    emp_id = linked_employees[0]
    if emp_id in low_price_employees:
        new_price = round(random.uniform(1, 100), 2)
    elif emp_id in high_price_employees:
        new_price = round(random.uniform(10000, 12000), 2)
    else:
        continue

    attrs = obj.find("attributes")
    if attrs is not None:
        price_attr = next((a for a in attrs.findall("attribute") if a.get("name") == "price"), None)
        if price_attr is not None:
            price_attr.text = str(new_price)


# 10. Adjust package weights

objects_by_id = {obj.get("id"): obj for obj in objects_section.findall("object")}
heavy_packages = set()

for event in events_section.findall("event"):
    if event.get("type") not in heavy_events:
        continue
    
    # Corrected: Use 'objects' container and 'relationship' children
    rels_container = event.find("objects")
    if rels_container is None:
        continue
        
    all_rels = rels_container.findall("relationship")
    linked_emps = {r.get("object-id") for r in all_rels if object_types_map.get(r.get("object-id")) == "employees"}
    linked_pkgs = {r.get("object-id") for r in all_rels if object_types_map.get(r.get("object-id")) == "packages"}
    
    # Intersection check against IDs (assuming IDs match employee names or are mapped)
    if linked_emps & target_heavy_employees:
        heavy_packages.update(linked_pkgs)

for pkg_id, pkg_obj in objects_by_id.items():
    if object_types_map.get(pkg_id) != "packages":
        continue
        
    heavy = pkg_id in heavy_packages
    attrs_xml = pkg_obj.find("attributes") or ET.SubElement(pkg_obj, "attributes")
    weight_attr = next((a for a in attrs_xml.findall("attribute") if a.get("name") == "weight"), None)
    
    if weight_attr is None:
        weight_attr = ET.SubElement(attrs_xml, "attribute", name="weight")
    
    weight_attr.text = f"{random.uniform(10.1, 20):.2f}" if heavy else f"{random.uniform(0.1, 4.9):.2f}"

tree.write(output_file, encoding="utf-8", xml_declaration=True)
print("All modifications applied. Final OCEL saved as:", output_file)