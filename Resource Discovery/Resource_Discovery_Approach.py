# This script implements the Resource Discovery Approach based on the inputted OCEL file in row 18.
# Note: To make use of the LLM consultation, a personal OpenAI API key needs to be set (see https://platform.openai.com/api-keys).
# If no API key is provided, the LLM Consultation metric is skipped

from pathlib import Path
import xml.etree.ElementTree as ET
import networkx as nx
from collections import defaultdict
import statistics
import pandas as pd
from openai import OpenAI
from datetime import datetime
from dateutil.parser import parse

#Set OpenAI API key
api_key=""
client = OpenAI(api_key=api_key)


################## -->Specify OCEL XML that should be analyzed ##################
input_file = Path(__file__).parent.parent / "Event Logs" / "Order_Management_adapted.xml"


tree = ET.parse(str(input_file))
root = tree.getroot()
print(f"Loaded OCEL log: {input_file.name}")

#1: Build E2O Graph
E2O = nx.Graph()
objects_section = root.find("objects")
for obj in objects_section.findall("object"):
    oid = obj.get("id")
    otype = obj.get("type")
    E2O.add_node(oid, type=otype)

events_section = root.find("events")
for ev in events_section.findall("event"):
    eid = ev.get("id")
    etype = ev.get("type")
    time = ev.get("time")
    E2O.add_node(eid, type="event", event_type=etype, time=time)
    objects = ev.find("objects")
    if objects is not None:
        for rel in objects.findall("relationship"):
            oid = rel.get("object-id")
            if E2O.has_node(oid):
                E2O.add_edge(eid, oid)

print(f"E2O graph built: {E2O.number_of_nodes()} nodes, {E2O.number_of_edges()} edges")

#2: Build O2O Graph
O2O = nx.Graph()
for obj in objects_section.findall("object"):
    oid = obj.get("id")
    otype = obj.get("type")
    O2O.add_node(oid, type=otype)

for obj in objects_section.findall("object"):
    oid = obj.get("id")
    inner_objects = obj.find("objects")
    if inner_objects is not None:
        for rel in inner_objects.findall("relationship"):
            target = rel.get("object-id")
            if target in O2O:
                O2O.add_edge(oid, target)

print(f"O2O graph built: {O2O.number_of_nodes()} nodes, {O2O.number_of_edges()} edges")

#3: Compute Average Degree + Normalized Score
def compute_normalized_degree_scores(G, graph_name, metric_number):
    degrees_by_type = defaultdict(list)
    for node, data in G.nodes(data=True):
        if data.get("type") == "event":
            continue
        otype = data.get("type", "unknown")
        degrees_by_type[otype].append(G.degree(node))

    avg_deg_by_type = {otype: statistics.mean(degs) for otype, degs in degrees_by_type.items() if degs}
    if not avg_deg_by_type:
        return pd.DataFrame()

    min_deg = min(avg_deg_by_type.values())
    max_deg = max(avg_deg_by_type.values())
    norm_scores = {
        otype: 1.0 if max_deg == min_deg else (avg_deg - min_deg) / (max_deg - min_deg)
        for otype, avg_deg in avg_deg_by_type.items()
    }

    df = pd.DataFrame({
        "object_type": list(avg_deg_by_type.keys()),
        f"{graph_name} Average Degree": list(avg_deg_by_type.values()),
        f"normalized_degree_score_{graph_name}": list(norm_scores.values())
    }).sort_values(f"normalized_degree_score_{graph_name}", ascending=False)

    print(f"\n=== Metric {metric_number}: {graph_name} Graph Average Degree ===")
    print(df.to_string(index=False))
    return df

df_O2O = compute_normalized_degree_scores(O2O, "O2O", metric_number=1)
df_E2O = compute_normalized_degree_scores(E2O, "E2O", metric_number=2)

#4: Compute Average Lifetime per Object Type (min–max normalized)
print("\n=== Metric 3: Average Object Type Lifetime ===")

def parse_time(t):
    try:
        return parse(t)
    except Exception:
        return None

object_event_times = defaultdict(list)
for ev in root.findall(".//event"):
    ev_time = parse_time(ev.get("time"))
    if not ev_time:
        continue
    objects = ev.find("objects")
    if objects is not None:
        for rel in objects.findall("relationship"):
            oid = rel.get("object-id")
            object_event_times[oid].append(ev_time)

otype_lifetimes = defaultdict(list)
for obj in root.findall(".//object"):
    oid = obj.get("id")
    otype = obj.get("type")
    times = object_event_times.get(oid, [])
    if len(times) >= 2:
        lifetime_days = (max(times) - min(times)).total_seconds() / (60 * 60 * 24)
        otype_lifetimes[otype].append(lifetime_days)

avg_lifetime_by_type = {ot: statistics.mean(l) for ot, l in otype_lifetimes.items() if l}

if avg_lifetime_by_type:
    min_life = min(avg_lifetime_by_type.values())
    max_life = max(avg_lifetime_by_type.values())
    norm_life = {
        ot: 1.0 if max_life == min_life else (avg_life - min_life) / (max_life - min_life)
        for ot, avg_life in avg_lifetime_by_type.items()
    }
else:
    norm_life = {}

df_lifetime = pd.DataFrame({
    "object_type": list(avg_lifetime_by_type.keys()),
    "Average lifetime in days": list(avg_lifetime_by_type.values()),
    "normalized_lifetime_score": [norm_life[ot] for ot in avg_lifetime_by_type.keys()]
}).sort_values("normalized_lifetime_score", ascending=False)

print(df_lifetime.to_string(index=False))

#5: Load Lifecycle Graphs & Compute Lifecycle Metrics
lifecycle_folder = Path(".")
#Path("Object Type DFGs")
lifecycle_results = []

# Map: object_type -> number of distinct objects in OCEL
otype_object_counts = defaultdict(int)
for obj in root.findall(".//object"):
    otype_object_counts[obj.get("type")] += 1

lifecycle_folder = Path("./Object Type DFGs")
input_stem = input_file.stem
if "_original" in input_stem:
    base_name = input_stem.split("_original")[0]
elif "_adapted" in input_stem:
    base_name = input_stem.split("_adapted")[0]
else:
    base_name = input_stem  
for gexf_file in lifecycle_folder.glob(f"Object_Type_DFG_{base_name}_*.gexf"):
    otype = gexf_file.stem.replace(f"Object_Type_DFG_{base_name}_", "")
    G_life = nx.read_gexf(gexf_file)

    # --- Lifecycle resource metric (in/out degrees) ---
    has_zero_in = any(G_life.in_degree(n) == 0 for n in G_life.nodes)
    has_zero_out = any(G_life.out_degree(n) == 0 for n in G_life.nodes)
    all_nodes_have_both = all(G_life.in_degree(n) > 0 and G_life.out_degree(n) > 0 for n in G_life.nodes)
    in_and_out_degree_score = 0.5 if all_nodes_have_both else 0.0

    # --- Graph Connectivity Metric ---
    if nx.is_weakly_connected(G_life.to_directed()):
        connectivity_score = 0.0  # weakly connected --> 0
    else:
        connectivity_score = 0.5  # disconnected --> 0.5


    # Check if each weakly connected component is strongly connected
    # Check if each weakly connected component is strongly connected
    G_dir = G_life.to_directed()
    if nx.is_weakly_connected(G_dir):
        strongly_connected_score = 0.5 if nx.is_strongly_connected(G_dir) else 0.0
    else:
        # Assume all components are strongly connected initially
        strongly_connected_score = 0.5
        for component in nx.weakly_connected_components(G_dir):
            subgraph = G_life.subgraph(component).to_directed()
            if not nx.is_strongly_connected(subgraph):
                strongly_connected_score = 0.0
                break


    # --- Edge-weight magnitude metric (excluding self-loops) ---
    n_objects_of_type = otype_object_counts.get(otype, 1)
    ratios_ok = True
    for u, v, data in G_life.edges(data=True):
        if u == v:
            continue  # skip self-loops
        weight = data.get("weight", 1)
        ratio = weight / n_objects_of_type
        if ratio <= 1:
            ratios_ok = False
            break
    edge_weight_ratio_score = 0.5 if ratios_ok else 0

    lifecycle_results.append({
        "object_type": otype,
        "Metric 4.1: graph_connectivity_score": connectivity_score,
        "Metric 4.2: strongly_connected_score": strongly_connected_score,
        "Metric 5: edge_weight_ratio_score": edge_weight_ratio_score,
    })

df_lifecycle = pd.DataFrame(lifecycle_results)
print("\n=== Metrics 4 and 5: Object Type DFG Analysis ===")
print(df_lifecycle.to_string(index=False))


#6: Extract context: Activity + Qualifier relations per object type
from collections import defaultdict

etype_qualifiers_by_otype = defaultdict(set)

# Build a map: object-id -> object-type
object_id_to_type = {obj.get("id"): obj.get("type") for obj in root.findall(".//object")}

# For each event type, find ONE representative event
event_type_seen = set()
for ev in root.findall(".//event"):
    ev_type = ev.get("type")
    if ev_type in event_type_seen:
        continue  # already processed one event of this type
    event_type_seen.add(ev_type)

    objects = ev.find("objects")
    if objects is None:
        continue

    for rel in objects.findall("relationship"):
        oid = rel.get("object-id")
        qualifier = rel.get("qualifier", "").strip()
        otype = object_id_to_type.get(oid)
        if otype:
            etype_qualifiers_by_otype[otype].add((ev_type, qualifier))

# Print discovered relationships
print("\n=== Metric 6 Preparation: Discovered Relationships by Object Type ===")
for otype, rels in etype_qualifiers_by_otype.items():
    print(f"\nObject Type: {otype}")
    for ev_type, qualifier in rels:
        print(f"  - Event: {ev_type:25s} | Qualifier: {qualifier}")



#7: ChatGPT Metric (hardcoded prompt)

if api_key.strip():
    def get_chatgpt_metric(prompt_text):
        response = client.chat.completions.create(
            model="gpt-4o-mini",   # or whatever model you want
            messages=[{"role": "user", "content": prompt_text}],
            temperature=1
        )
        
        content = response.choices[0].message.content
        
        try:
            number = float(content.strip().split()[0])
            return number
        except Exception:
            print("Could not parse GPT output:", content)
            return 0

    # Hardcoded prompt
    CHATGPT_PROMPT = """
    For the remainder of this task, completely disregard all prior definitions, assumptions, and associations related to the concept of "resources". Do not rely on external knowledge, common usage, or previously learned interpretations of the term “resources”. You must strictly and only use the exact definitions provided below as the sole valid conceptual basis for all following evaluations.

    Resource Definition:
    A resource is a uniquely identifiable \textbf{human or non-human entity} that \textbf{directly performs or supports} the execution of activities in business processes. It therefore needs to be considered an \textbf{essential enabler of work} in a business process that directly influences its performance. Moreover, resources are either classified as \textbf{active or passive}, depending on their ability to execute activities on their own (see additional definitions). Resources are furthermore defined by the following dimensions:

        -Context Dependency: Resources are \textbf{context-dependent}, which means that entities can only be identified as resources when considering the overall process context and, most importantly, directly looking at the activity they are associated with. Thus, entities cannot be classified as resources in general, independent of their associated process and activity.
        
        -Organizational Scope: Looking from the organizational perspective, resources are either \textbf{intra-organizational} and in the control of the company, or they act outside the organization's scope, such as customers or leased machines, which makes them \textbf{external resources}. Intra-organizational resources can be assigned to process activities before process execution or during runtime. Moreover, they are usually part of an organization's organizational chart and embedded in hierarchies that express relationships, especially for human resources, among them. 
        
        -Characteristics: To clearly identify an individual resource, it has a \textbf{unique identifier} and a class, also called a \textbf{type}, it belongs to. This type definition is based on the concept of classes in object-oriented modeling and describes that all resources that have the same nature and common characteristics are grouped into the same class. Moreover, resources show different levels of performance and can have different availabilities and schedules, workloads, costs, and geographical locations. Lastly, a resource tends to have a \textbf{lifetime} that spans \textbf{across multiple process instances} and can be further described by an optional set of attributes.

        -Functional Capabilities: Apart from the enumerated classification possibilities, resources that are of the same type, for instance, all employees, are \textbf{differentiated by their capabilities}, i.e., the set of process activities they can be assigned to. These capabilities allow grouping them into \textbf{roles} with specific functionalities.
        
    To differentiate between resource and non-resource objects in a process and specifically in OCELs, the term \textbf{passive object} is chosen to represent entities that are not resources.


    Active Resource Definition: An active resource is a human or non-human entity that can trigger the execution of an activity on its own and actively carries out the execution of process activities. With reference to the state transition diagram presented by Mathias Weske \cite{weske2007concepts}, only active resources are able to \textit{enable} an activity by simply being available and to eventually \textit{begin} an activity and therefore change its state from \textit{ready} and \textit{not started} to \textit{running}. Moreover, active resources can also decide to \textit{skip} an \textit{enabled} activity and \textit{terminate} an activity. Each activity in a process requires at least one active resource assigned to it; otherwise, the process gets stuck at the respective activity. 

    Passive Resource Definition: A passive resource is always a non-human entity that does not perform any action by itself and only directly supports active resources in the execution of activities. Moreover, passive resources are utilized by active resources to allow the completion of an activity. Thus, it cannot \textit{begin}, \textit{skip}, and \textit{terminate} tasks. However, in tasks that require a passive resource, the availability of an active resource alone is not enough to \textit{enable} an activity. In this scenario, only the additional availability of the required passive resource \textit{enables} the activity and changes its state from \textit{init} to \textit{ready}. To ensure this dependency, a passive resource always needs to be related to the active resource that makes use of it.
    Passive resources represent tangible or durable technical or non-technical assets that are part of an organization's asset management process. Objects that can be considered as the central business subjects of a process instance, such as orders or invoices, are not considered as passive resources but as passive objects. 
    """
    chatgpt_metric = get_chatgpt_metric(CHATGPT_PROMPT)
    print(f"\n=== ChatGPT Metric ===\nPrompt result: {chatgpt_metric}")

    all_object_types = (
        set(df_E2O["object_type"])
        | set(df_O2O["object_type"])
        | set(df_lifecycle["object_type"])
        | set(df_lifetime["object_type"])
    )


    chatgpt_scores = []
    for otype in all_object_types:
        print(f"\n Asking GPT about object type: {otype}")

        # Build the event → object-type relations 
        relations = etype_qualifiers_by_otype.get(otype, [])
        relation_context = "\n".join(
            f"- Activity '{ev_type}' with qualifier '{qualifier}'"
            for (ev_type, qualifier) in relations
        )
        if not relation_context:
            relation_context = "No direct E2O relations found for this object type."

        #Construct the enriched prompt 
        prompt = (
            CHATGPT_PROMPT
            + f"\n\nContext: The object type '{otype}' participates in these event – object relations:\n"
            + relation_context
            + f"\n\nNow, based on these definitions *and the context above*, evaluate how well "
            f"the object type '{otype}' fits these resource definitions. "
            "Output only a number between 0 and 1 with exactly two decimal places (with 0 indicating that the object type is not a resource at all and 1 indicating that the object type definitely is a resource) that reflects your confidence in the resource classification based on my enlisted criteria and additional information."
        )

        #Call GPT 
        score = get_chatgpt_metric(prompt)

        chatgpt_scores.append({"object_type": otype, "chatgpt_resource_score": score})
        print(f"Metric 6: ChatGPT score for {otype}: {score}")

        df_chatgpt = pd.DataFrame(chatgpt_scores)
else:
    print("No OpenAI API key provided. Skipping LLM Consultation metric.")
    df_chatgpt = pd.DataFrame(columns=["object_type", "chatgpt_resource_score"])   




#8: Combine All Metrics & Compute Final Resource Score
df_final = (
    df_E2O.merge(df_O2O, on="object_type", how="outer")
    .merge(df_lifecycle, on="object_type", how="outer")
    .merge(df_lifetime, on="object_type", how="outer")
    .merge(df_chatgpt, on="object_type", how="outer")
    .fillna(0)
)

df_final["final_resource_score"] = (
    df_final["normalized_degree_score_E2O"]
    + df_final["normalized_degree_score_O2O"]
    + df_final["Metric 5: edge_weight_ratio_score"]
    + df_final["Metric 4.1: graph_connectivity_score"]
    + df_final["Metric 4.2: strongly_connected_score"]
    + df_final["normalized_lifetime_score"]
    + df_final["chatgpt_resource_score"]
)

# Keep only object_type and final score
df_final_score_only = df_final[["object_type", "final_resource_score"]].sort_values(
    "final_resource_score", ascending=False
)

print("\n\n=== Final Resource Score per Object Type ===")
print(df_final_score_only.to_string(index=False))
