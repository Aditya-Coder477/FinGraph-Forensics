import networkx as nx

def detect_layered_shells(G: nx.DiGraph, min_hops=3):
    """
    Detects chains of min_hops+ length where intermediate nodes are strictly 'shell' accounts.
    Shell Criteria:
    - Total transactions (degree) <= 3
    - In-degree <= 2
    - Out-degree <= 2
    
    Returns a list of chains (list of nodes).
    Implements deduplication: merges chains sharing > 60% nodes.
    """
    
    # 1. Identify Shell Nodes (Strict Criteria)
    degrees = dict(G.degree())
    in_degrees = dict(G.in_degree())
    out_degrees = dict(G.out_degree())
    
    shell_nodes = set()
    for n in G.nodes():
        # "Total transactions <= 3" AND "in/out <= 2"
        if degrees.get(n, 0) <= 3 and in_degrees.get(n, 0) <= 2 and out_degrees.get(n, 0) <= 2:
            shell_nodes.add(n)
            
    # 2. Find Chains
    # We look for connections between shell nodes: S1 -> S2
    # And then extend to endpoints: Pre -> S1 -> S2 -> ... -> Post
    
    # Subgraph of ONLY shell nodes to find the "middle" of chains
    S_sub = G.subgraph(shell_nodes).copy()
    
    # Find connected components in the shell subgraph (weakly connected)
    # Each component represents a potential chain core.
    components = list(nx.weakly_connected_components(S_sub))
    
    raw_chains = []
    
    for comp in components:
        if len(comp) < 1: continue
        
        # In this component, find all simple paths
        # Since shell nodes have low degree, paths shouldn't be too many or long
        sub_comp = S_sub.subgraph(comp)
        
        # Find roots (nodes with 0 in-degree IN THE SUBGRAPH) and leaves
        # But it might be a cycle, though unlikely for "layered chains" which implies direction.
        # Just iterate all nodes? Or use logic:
        # A chain core is S_start -> ... -> S_end
        
        # Let's find all simple paths longer than length 1 (at least 2 shell nodes)
        # S1->S2 is length 1 (edges). Nodes: 2.
        # Requirement: "3+ hop chains". 
        # Structure: Start -> S1 -> S2 -> End (3 hops).
        # So we need a path of at least 2 Shell Nodes in the core.
        
        # Iterate all pairs in the component? Efficient enough for small components.
        comp_nodes = list(comp)
        for i in range(len(comp_nodes)):
            for j in range(len(comp_nodes)):
                if i == j: continue
                u, v = comp_nodes[i], comp_nodes[j]
                
                # specific optimization: if u has in-degree in sub_G > 0, maybe not start?
                # But it could be middle.
                
                paths = list(nx.all_simple_paths(sub_comp, u, v, cutoff=6))
                for path in paths:
                    if len(path) >= 2: # At least 2 shell nodes: S1->S2
                        # Check endpoints
                        s_first = path[0]
                        s_last = path[-1]
                        
                        # Look for Predecessors of S1 (that are NOT in the path)
                        preds = [p for p in G.predecessors(s_first) if p not in path]
                        # Look for Successors of S_last (that are NOT in the path)
                        succs = [s for s in G.successors(s_last) if s not in path]
                        
                        if preds and succs:
                            # We have a valid chain: Pre -> [S...S] -> Post
                            for pre in preds:
                                for post in succs:
                                    if pre == post: continue # Loop
                                    
                                    full_chain = [pre] + path + [post]
                                    
                                    # Check length: hops = nodes - 1
                                    # Nodes = 2 (Shells) + 2 (Ends) = 4 nodes. Hops = 3.
                                    # Matches requirement ">= 3 hops".
                                    
                                    # Store sorted tuple for deduplication key, but keep original for display
                                    raw_chains.append(full_chain)

    # 3. Deduplication (Merge sharing > 60% nodes)
    # Sort chains by length descending to prioritize longer ones?
    raw_chains.sort(key=len, reverse=True)
    
    final_rings = []
    
    for chain in raw_chains:
        chain_set = set(chain)
        
        # Check against existing rings
        merged = False
        for ring in final_rings:
            # Calculate overlap
            ring_set = set(ring)
            intersection = chain_set.intersection(ring_set)
            
            # If overlap > 60% of THE SMALLER set? or the Candidate?
            # "shares >60% nodes with existing chain -> merge"
            # Usually means Jaccard or overlap ratio.
            # Let's use: len(intersection) / len(chain_set) > 0.6
            
            if len(intersection) / len(chain_set) > 0.6:
                # Merge logic: Union of nodes?
                # If we merge, we might lose the "chain" order. 
                # But requirements say "represent each detected chain as a sorted tuple... Only create ONE ring"
                # So the ring accounts = Union of unique accounts.
                # We just update the existing ring members.
                ring.extend(list(chain_set - ring_set))
                merged = True
                break
        
        if not merged:
            final_rings.append(list(chain)) # Start a new ring
            
    return final_rings
