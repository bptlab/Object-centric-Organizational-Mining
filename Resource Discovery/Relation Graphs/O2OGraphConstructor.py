# This script creates the O2O (Object-to-Object) graph of an OCEL
# and exports it as a .gexf file for visualization in Gephi Lite

from pathlib import Path
import xml.etree.ElementTree as ET
import networkx as nx

# Specify OCEL file (relative to this script's location)
infile = Path(__file__).resolve().parent.parent.parent / "Event Logs" / "Order_Management_adapted.xml"

# Parse the XML file
tree = ET.parse(str(infile))
root = tree.getroot()

# Create an undirected graph
G = nx.Graph()
print("Starting O2O graph creation...")

# Get the objects section
objects_section = root.find("objects")
if objects_section is None:
    raise RuntimeError("No <objects> section found.")

# Add nodes (objects) with their attributes
for obj in objects_section.findall("object"):
    oid = obj.get("id")
    otype = obj.get("type")
    attrs = {}
    atts_root = obj.find("attributes")
    if atts_root is not None:
        for att in atts_root.findall("attribute"):
            attrs[att.get("name")] = att.text
    G.add_node(oid, type=otype, **attrs)

# Add edges between objects
for obj in objects_section.findall("object"):
    oid = obj.get("id")
    inner_objects = obj.find("objects")
    if inner_objects is not None:
        for rel in inner_objects.findall("relationship"):
            target = rel.get("object-id")
            qualifier = rel.get("qualifier")
            if target in G:  # only edges between existing objects
                G.add_edge(oid, target, qualifier=qualifier)

print(f"Graph created: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")

# Save graph as GEXF, including input filename in output
output_path = Path(__file__).parent / f"O2O_Graph_{infile.stem}.gexf"
nx.write_gexf(G, output_path)
print(f"Graph saved as: {output_path.resolve()}")