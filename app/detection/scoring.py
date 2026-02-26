import networkx as nx
import pandas as pd
import time
from .cycles import detect_cycles
from .smurfing import detect_smurfing
from .shell import detect_layered_shells

class FraudDetector:
    def __init__(self):
        pass

    def run_analysis(self, csv_path):
        start_time = time.time()
        
        # 1. Load Data
        try:
            df = pd.read_csv(csv_path)
            required_cols = ['transaction_id', 'sender_id', 'receiver_id', 'amount', 'timestamp']
            if not all(col in df.columns for col in required_cols):
                return {"error": f"Missing columns. Required: {required_cols}"}
            
            df['timestamp'] = pd.to_datetime(df['timestamp'])
        except Exception as e:
            return {"error": f"Failed to parse CSV: {str(e)}"}

        # 2. Build Full Graph (DiGraph) — vectorized, no iterrows
        G = nx.from_pandas_edgelist(
            df, source='sender_id', target='receiver_id',
            edge_attr=['timestamp', 'amount'],
            create_using=nx.DiGraph()
        )
            
        # ==========================================
        # PHASE 1: DETECTION ONLY
        # ==========================================
        # Detect patterns but DO NOT create rings yet.
        # Store all detections in a central registry.
        
        account_patterns = {} # {acc_id: {'patterns': set(), 'risk_tier': 'LOW'}}

        def register_pattern(acc_id, pattern, tier='LOW'):
            if acc_id not in account_patterns:
                account_patterns[acc_id] = {'patterns': set(), 'risk_tier': 'LOW'}
            account_patterns[acc_id]['patterns'].add(pattern)
            
            # Escalate tier if needed
            current = account_patterns[acc_id]['risk_tier']
            if tier == 'HIGH':
                account_patterns[acc_id]['risk_tier'] = 'HIGH'
            elif tier == 'MEDIUM' and current != 'HIGH':
                account_patterns[acc_id]['risk_tier'] = 'MEDIUM'

        # A. Cycles (HIGH Risk)
        cycles = detect_cycles(G, max_length=5)
        for cycle in cycles:
            ptype = f"cycle_length_{len(cycle)}"
            for node in cycle:
                register_pattern(node, ptype, 'HIGH')

        # B. Smurfing (Aggregator=HIGH, Neighbor=MEDIUM)
        smurf_suspects, smurf_aggregators = detect_smurfing(df)
        
        # Register Aggregators
        for agg in smurf_aggregators:
            ptype = f"smurfing_{agg['type']}" # fan_in / fan_out
            register_pattern(agg['center'], ptype, 'HIGH')
            
            # Register Neighbors (Medium Risk)
            neighbor_ptype = f"{agg['type']}_neighbor"
            for n in agg['neighbors']:
                register_pattern(n, neighbor_ptype, 'MEDIUM')

        # C. Shell Chains (Intermediate=HIGH, Source/Dest=MEDIUM)
        shell_chains = detect_layered_shells(G)
        for chain in shell_chains:
            # Chain: [Start, S1, S2, End]
            # Intermediates are strictly shell nodes -> HIGH
            intermediates = chain[1:-1]
            for node in intermediates:
                register_pattern(node, "shell_intermediate", 'HIGH')
            
            # Endpoints -> MEDIUM
            register_pattern(chain[0], "shell_source", 'MEDIUM')
            register_pattern(chain[-1], "shell_destination", 'MEDIUM')


        # ==========================================
        # PHASE 2: MERCHANT CLASSIFICATION (vectorized)
        # ==========================================
        merchants = []
        merchants_set = set()

        # Vectorized unique-sender / unique-receiver counts via pandas groupby
        u_senders_series = df.groupby('receiver_id')['sender_id'].nunique()
        u_receivers_series = df.groupby('sender_id')['receiver_id'].nunique()

        all_nodes = pd.Index(G.nodes())
        u_senders = u_senders_series.reindex(all_nodes, fill_value=0)
        u_receivers = u_receivers_series.reindex(all_nodes, fill_value=0)

        merchant_mask = (u_senders >= 5) & (u_receivers >= 3)
        merchant_nodes = all_nodes[merchant_mask]

        in_degree  = dict(G.in_degree())
        out_degree = dict(G.out_degree())

        for node in merchant_nodes:
            merchants.append({
                "account_id": node,
                "type": "merchant",
                "degree": in_degree.get(node, 0) + out_degree.get(node, 0),
            })
            merchants_set.add(node)
            # Exclude merchants from suspicious pool
            if node in account_patterns:
                del account_patterns[node]

        # ==========================================
        # PHASE 3: BUILD SUSPICIOUS SUBGRAPH
        # ==========================================
        # G_suspicious includes ONLY accounts with >=1 suspicious pattern (that are not merchants)
        
        suspicious_nodes = list(account_patterns.keys())
        
        if suspicious_nodes:
            # Subgraph of G containing only these nodes
            # We convert to Undirected to find clusters (rings)
            G_susp = G.subgraph(suspicious_nodes).to_undirected()
            
            # Important: We only keep edges that exist between suspicious nodes.
            # NetworkX subgraph does this automatically.
        else:
            G_susp = nx.Graph()


        # ==========================================
        # PHASE 4: CLUSTER RINGS
        # ==========================================
        # Connected Components = Fraud Rings
        
        components = list(nx.connected_components(G_susp))
        
        fraud_rings = []
        ring_id_counter = 1
        node_ring_map = {}
        
        for comp in components:
            if len(comp) < 2: 
                # Single isolated suspicious node. 
                # Is it a ring? Usually no. Just a suspicious account.
                continue
                
            members = list(comp)
            
            # Aggregate patterns & Calculate Score
            ring_patterns = set()
            high_risk_scores = []
            
            for m in members:
                p_data = account_patterns.get(m)
                if not p_data: continue # Should not happen
                
                ring_patterns.update(p_data['patterns'])
                
                # Calculate Individual Score (Deterministic)
                base_score = 0
                patterns = p_data['patterns']
                
                if any('cycle' in str(p) for p in patterns): base_score += 40
                if any('smurfing_fan_in' in str(p) for p in patterns) or any('smurfing_fan_out' in str(p) for p in patterns): base_score += 35
                if 'shell_intermediate' in patterns: base_score += 30
                if 'shell_source' in patterns or 'shell_destination' in patterns: base_score += 15
                if 'fan_in_neighbor' in patterns or 'fan_out_neighbor' in patterns: base_score += 15
                
                # Clamp
                final_score = min(base_score, 100)
                
                # Store back in p_data for later use
                p_data['score'] = final_score
                
                if p_data['risk_tier'] == 'HIGH':
                    high_risk_scores.append(final_score)

            # Ring ID
            ring_id = f"RING_{ring_id_counter:03d}"
            ring_id_counter += 1
            
            # Ring pattern label
            display_patterns = set()
            for p in ring_patterns:
                if 'cycle' in p: display_patterns.add('Cycle')
                elif 'smurfing' in p or 'fan' in p: display_patterns.add('Smurfing')
                elif 'shell' in p: display_patterns.add('Shell Chain')
            
            ptype_str = " + ".join(sorted(list(display_patterns)))
            
            # Ring Risk Score = Average of HIGH risk members
            if high_risk_scores:
                ring_risk = sum(high_risk_scores) / len(high_risk_scores)
            else:
                # Fallback if ring has no high risk members (unlikely given logic, but maybe only medium neighbors connected?)
                # "Risk must NEVER be 0 if ring exists"
                # Use medium scores if no high
                all_scores = [account_patterns[m]['score'] for m in members]
                ring_risk = sum(all_scores) / len(all_scores) if all_scores else 10

            # Identify aggregator nodes for smurfing rings (fan-in/fan-out centers)
            aggregator_nodes = []
            if 'Smurfing' in display_patterns:
                for m in members:
                    p_data = account_patterns.get(m, {})
                    pats = p_data.get('patterns', set())
                    if any('smurfing_fan_in' in p or 'smurfing_fan_out' in p for p in pats):
                        aggregator_nodes.append(m)

            fraud_rings.append({
                "ring_id": ring_id,
                "pattern_type": ptype_str,
                "member_accounts": members,
                "risk_score": round(ring_risk, 1),
                "aggregators": aggregator_nodes   # center nodes for smurfing star layout
            })
            
            for m in members:
                node_ring_map[m] = ring_id


        # ==========================================
        # PHASE 5: FINAL SCORING & OUTPUT
        # ==========================================
        
        suspicious_list = []
        
        # Calculate scores for isolated suspicious nodes as well
        for acc_id, data in account_patterns.items():
            if 'score' not in data:
                 # Calculate score if not done during ring step
                base_score = 0
                patterns = data['patterns']
                # Same logic as above
                if any('cycle' in str(p) for p in patterns): base_score += 40
                if any('smurfing_fan' in str(p) for p in patterns) and 'neighbor' not in str(patterns): base_score += 35
                if 'shell_intermediate' in patterns: base_score += 30
                if 'shell_source' in patterns or 'shell_destination' in patterns: base_score += 15
                if 'fan_in_neighbor' in patterns or 'fan_out_neighbor' in patterns: base_score += 15
                data['score'] = min(base_score, 100)

            # "suspicious_accounts_flagged = count of HIGH + MEDIUM only"
            # Low risk must not be counted? 
            # For the output list, we should probably include them but filter in summary?
            # Or exclude completely? "LOW risk accounts must NOT be counted as suspicious."
            # Let's filter list.
            
            if data['risk_tier'] in ['HIGH', 'MEDIUM']:
                suspicious_list.append({
                    "account_id": acc_id,
                    "suspicion_score": float(data['score']),
                    "detected_patterns": list(data['patterns']),
                    "ring_id": node_ring_map.get(acc_id),
                    "type": "suspicious"
                })

        suspicious_list.sort(key=lambda x: x['suspicion_score'], reverse=True)
        fraud_rings.sort(key=lambda x: x['risk_score'], reverse=True)
        
        # Stats
        processing_time = time.time() - start_time
        
        pattern_counts = {}
        for ring in fraud_rings:
            # Count UNIQUE rings per pattern
            ptypes = ring['pattern_type'].split(' + ')
            for p in ptypes:
                pattern_counts[p] = pattern_counts.get(p, 0) + 1

        # Pruned Edges for Frontend — only ring members + 1-hop suspicious neighbors
        # Do NOT expand all merchant neighbors (they can have hundreds)
        MAX_EDGES = 400
        keep_nodes = set()
        for s in suspicious_list:
            keep_nodes.add(s['account_id'])
            # Only 1-hop neighbors that are also suspicious or ring members
            for nb in list(G.neighbors(s['account_id'])) + list(G.predecessors(s['account_id'])):
                if nb in account_patterns or nb in merchants_set:
                    keep_nodes.add(nb)

        for m in merchants:
            keep_nodes.add(m['account_id'])
            # Skip expanding merchant neighbors (merchants can have 100s)

        # Priority 1: edges between suspicious nodes
        # Priority 2: edges to/from merchants
        suspicious_ids = {s['account_id'] for s in suspicious_list}
        pruned_edges = []
        for u, v in G.edges():
            if u in suspicious_ids and v in suspicious_ids:
                pruned_edges.append({"source": u, "target": v})
        for u, v in G.edges():
            if len(pruned_edges) >= MAX_EDGES:
                break
            if (u in keep_nodes and v in keep_nodes) and \
               not (u in suspicious_ids and v in suspicious_ids):
                pruned_edges.append({"source": u, "target": v})

        result = {
            "summary": {
                "total_accounts_analyzed": len(G.nodes()),
                "total_transactions": len(df),
                "suspicious_accounts_flagged": len(suspicious_list),
                "fraud_rings_detected": len(fraud_rings),
                "high_risk_clusters": len(fraud_rings),
                "merchants_identified": len(merchants),
                "processing_time_seconds": round(processing_time, 2),
                "pattern_distribution": pattern_counts
            },
            "suspicious_accounts": suspicious_list,
            "merchants": merchants,
            "fraud_rings": fraud_rings,
            "graph_edges": pruned_edges,
            "nodes_metadata": {
                **{s['account_id']: {"type": "suspicious", "score": s['suspicion_score']} for s in suspicious_list},
                **{m['account_id']: {"type": "merchant", "score": 10} for m in merchants}
            }
        }
        return result
