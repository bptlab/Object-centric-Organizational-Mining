# Object-Centric OrgMining

This repository includes approaches for the discovery of resources and their roles in OCELs.

In the `Event Logs` folder, all original and adapted event logs, on which the approaches were evaluated on, can be found. Moreover, the `OCEL Modifiers` folder stores the modification scripts that were used to adapt the original OCELs.

In the `Resource Discovery` folder, the resource discovery approach can be found that identifies resource object type candidates based on six metrics and a scoring system. The aproach returns a resource score for each object type and based on a predefined threshold, resource object type candidates can be choosen. 
The metrics are, among others, based on the E2O and O2O relations graphs, as well as on object type Directly-Follows Graphs. 
In the `Relation Graphs` folder, the E2O and O2O relation grphs for the adapted order management OCEL can be found, as well as the generic constructor for these graphs.
In the `Object Type DFGs` folder, the DFGs of all objects types of all adapted OCELs can be found, as well as the constructor, which computes all DFGs for one OCEl.

The `Role Discovery` folder then presents the oc OrgMining approach, that discovers roles for the identified resource object types. As the approach relies on case attributes, the two preparatory steps in the `Preparatory Steps` folder need to be run beforehand to identify suitable case attributes along with their case types.
Lastly, the `Object-Centric OrgMining` folder presents the actual approach that is run in two stages to first discover general roles based on activity and relation types, and then discovers subroles for these general roles based on the full execution modes, inclusive case types.
Moreover, the folder presents the Resource x Execution Mode matrices as .csv files for the inspection.

