import networkx as nx

def detect_cycles(G: nx.DiGraph, max_length=5):
    """
    Detects simple cycles of length 3 to max_length.
    Returns a list of cycles (lists of nodes).
    Uses a Depth-Limited Search to ensure performance on dense graphs.
    """
    cycles = []
    seen_cycles = set()
    
    # Sort nodes to ensure deterministic output and optimization
    # (Checking smallest node id idea)
    nodes = sorted(list(G.nodes()))
    
    def dfs(start_node, current_node, path, length):
        if length > max_length:
            return

        # Explore neighbors
        for neighbor in G.neighbors(current_node):
            if neighbor == start_node:
                # Found a cycle back to start
                if length >= 3:
                    # Canonical form for deduplication
                    # We only accept if start_node is the smallest (or we handle dedupe explicitly)
                    # Let's use tuple of sorted nodes as key if order doesn't matter for "set of nodes"
                    # But for a cycle, order matters. Canonical: rotate so smallest is first.
                    # Since we started at start_node, if we enforce start_node is min(path), we avoid dups.
                    if start_node == min(path):
                        cycles.append(path[:])
            elif neighbor not in path:
                # Continue search
                # Optimization: Only continue if neighbor > start_node?
                # This enforces that we only find the cycle when we start at its smallest node.
                # This is a standard way to find unique elementary circuits.
                if neighbor > start_node:
                    dfs(start_node, neighbor, path + [neighbor], length + 1)
    
    # Limit total cycles to avoid memory explosion if graph is fully connected
    MAX_TOTAL_CYCLES = 2000
    
    for node in nodes:
        if len(cycles) >= MAX_TOTAL_CYCLES:
            break
        # Start DFS
        dfs(node, node, [node], 1)
        
    return cycles
