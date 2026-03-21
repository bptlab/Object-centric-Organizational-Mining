# This script creates the E2O (Event-to-Object) graph of an OCEL
# and exports it as a .gexf file for visualization in Gephi Lite

from pathlib import Path
import xml.etree.ElementTree as ET
import networkx as nx

# Specify OCEL file (relative to this script's location)
infile = Path(__file__).resolve().parent.parent.parent / "Event Logs" / "Order_Management_adapted.xml"

# Parse XML file
tree = ET.parse(infile)
root = tree.getroot()

# Create an undirected graph (E2O Graph)
G = nx.Graph()

# Add objects as nodes
objects_section = root.find("objects")
if objects_section is None:
    raise RuntimeError("No <objects> section found.")

for obj in objects_section.findall("object"):
    oid = obj.get("id")
    otype = obj.get("type")
    G.add_node(oid, type=otype)

# Read events and create Event-to-Object edges
events_section = root.find("events")
if events_section is None:
    raise RuntimeError("No <events> section found.")

for ev in events_section.findall("event"):
    eid = ev.get("id")
    etype = ev.get("type")
    time = ev.get("time")

    G.add_node(eid, type="event", event_type=etype, time=time)

    # Event-to-Object relationships
    objects = ev.find("objects")
    if objects is not None:
        for rel in objects.findall("relationship"):
            oid = rel.get("object-id")
            qualifier = rel.get("qualifier")

            if not G.has_node(oid):
                G.add_node(oid, type="unknown")

            G.add_edge(eid, oid, qualifier=qualifier)

# Output path (same folder as script), include input filename
output_path = Path(__file__).parent / f"E2O_Graph_{infile.stem}.gexf"

# Export graph
nx.write_gexf(G, output_path)

print(f"Event-to-Object graph successfully exported to: {output_path.resolve()}")