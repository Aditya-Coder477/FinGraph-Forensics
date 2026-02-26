document.addEventListener('DOMContentLoaded', async () => {
    // STATE
    let currentMode = 'empty'; // empty, focus, suspicious, full
    let analysisData = null;
    let cy = null;
    const layoutCache = {};  // { 'full': {id:{x,y}}, 'suspicious': {...}, 'ring_RING_001': {...} }

    // DOM Elements
    const els = {
        stats: {
            total: document.getElementById('stat-total'),
            transactions: document.getElementById('stat-transactions'),
            rings: document.getElementById('stat-rings'),
            suspicious: document.getElementById('stat-suspicious'),
            time: document.getElementById('stat-time')
        },
        tables: {
            suspicious: document.querySelector('#suspicious-table-mini tbody'),
            rings: document.querySelector('#rings-table tbody')
        },
        patternDist: document.getElementById('pattern-dist'),
        insightText: document.getElementById('insight-text'),
        graph: {
            container: document.getElementById('cy'),
            placeholder: document.getElementById('graph-placeholder'),
            section: document.querySelector('.graph-section')
        },
        sidePanel: {
            el: document.getElementById('side-panel'),
            id: document.getElementById('intel-id'),
            pattern: document.getElementById('intel-pattern'),
            score: document.getElementById('intel-score'),
            desc: document.getElementById('intel-desc'),
            members: document.getElementById('intel-members-list'),
            close: document.getElementById('close-side-panel')
        },
        controls: {
            focus: document.getElementById('btn-focus'),
            suspicious: document.getElementById('btn-suspicious'),
            full: document.getElementById('btn-full')
        },
        resultArea: {
            wrapper: document.getElementById('graph-result-area'),
            title: document.getElementById('graph-result-title'),
            content: document.getElementById('graph-result-content')
        }
    };

    // 1. Fetch Data
    try {
        const response = await fetch('/api/results');
        if (!response.ok) throw new Error("Failed to load results");
        analysisData = await response.json();
        initDashboard();
    } catch (e) {
        console.error(e);
        // If fail, just show empty or redirect (dev mode: alert)
        // alert("No data found. Upload a file first.");
    }

    function initDashboard() {
        populateStats();
        populateTables();
        initGraph(); // Initialize cy but empty or preset
    }

    // 2. Populate Metrics & Tables
    function populateStats() {
        const s = analysisData.summary;
        if (!s) return;
        
        els.stats.total.textContent = s.total_accounts_analyzed.toLocaleString();
        els.stats.transactions.textContent = s.total_transactions ? s.total_transactions.toLocaleString() : '-';
        els.stats.rings.textContent = s.fraud_rings_detected;
        els.stats.suspicious.textContent = s.suspicious_accounts_flagged;
        els.stats.time.textContent = s.processing_time_seconds + 's';

        // Pattern Distribution — animated bar chart
        els.patternDist.innerHTML = '';
        if (s.pattern_distribution && Object.keys(s.pattern_distribution).length > 0) {
            const entries = Object.entries(s.pattern_distribution);
            const maxCount = Math.max(...entries.map(([, c]) => c), 1);
            let maxPattern = '', maxCount2 = 0;

            // Config per known pattern
            const patternConfig = {
                'Cycle':       { icon: '🔄', color: '#ef4444', bg: '#fef2f2', label: 'Cycle Rings',       desc: 'Circular fund flows returning to origin — wash trading / layering' },
                'Smurfing':    { icon: '🐟', color: '#f97316', bg: '#fff7ed', label: 'Smurfing Rings',    desc: 'Fan-in / fan-out bursts across many accounts within 72h' },
                'Shell Chain': { icon: '🔗', color: '#eab308', bg: '#fefce8', label: 'Shell Chain Rings', desc: 'Long layered hops through low-activity accounts to obscure origin' },
            };

            entries.forEach(([key, count]) => {
                // Match to a known config (partial match)
                let cfg = Object.entries(patternConfig).find(([k]) => key.includes(k));
                cfg = cfg ? cfg[1] : { icon: '⚠️', color: '#6366f1', bg: '#eef2ff', label: key, desc: 'Anomalous transaction pattern detected.' };

                const pct = Math.round((count / maxCount) * 100);

                const card = document.createElement('div');
                card.className = 'pattern-chart-card';
                card.innerHTML = `
                    <div class="pcc-header">
                        <span class="pcc-icon">${cfg.icon}</span>
                        <span class="pcc-label">${cfg.label}</span>
                        <span class="pcc-count" style="background:${cfg.color}20;color:${cfg.color}">${count} ring${count !== 1 ? 's' : ''}</span>
                    </div>
                    <div class="pcc-bar-track">
                        <div class="pcc-bar-fill" data-pct="${pct}" style="background:${cfg.color};width:0%"></div>
                    </div>
                    <div class="pcc-desc">${cfg.desc}</div>
                `;
                els.patternDist.appendChild(card);

                if (count > maxCount2) { maxCount2 = count; maxPattern = cfg.label; }
            });

            // Animate bars after paint
            requestAnimationFrame(() => {
                document.querySelectorAll('.pcc-bar-fill').forEach(bar => {
                    bar.style.transition = 'width 0.8s cubic-bezier(0.4,0,0.2,1)';
                    bar.style.width = bar.dataset.pct + '%';
                });
            });

            els.insightText.textContent = maxPattern
                ? `Highest prevalence: ${maxPattern} — indicates organized layering behavior.`
                : 'No significant patterns detected.';
        } else {
            els.patternDist.innerHTML = '<p style="padding:1.5rem;color:#94a3b8;font-size:0.9rem;">No patterns detected in this dataset.</p>';
            els.insightText.textContent = 'No significant patterns detected.';
        }
    }

    function populateTables() {
        // Mini Suspicious Table (Top 5)
        const top5 = analysisData.suspicious_accounts.slice(0, 5);
        els.tables.suspicious.innerHTML = '';
        top5.forEach(acc => {
            const tr = document.createElement('tr');
            // Simply use first pattern
            const pattern = acc.detected_patterns.length > 0 ? acc.detected_patterns[0] : 'Unknown';
            tr.innerHTML = `<td>${acc.account_id}</td><td><span class="score-high">${acc.suspicion_score}</span></td><td>${pattern}</td>`;
            els.tables.suspicious.appendChild(tr);
        });

        // Rings Table
        els.tables.rings.innerHTML = '';
        analysisData.fraud_rings.forEach(ring => {
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td><strong>${ring.ring_id}</strong></td>
                <td><span class="badge badge-net-cycle">${ring.pattern_type}</span></td>
                <td>${ring.member_accounts.length}</td>
                <td>${Math.round(ring.risk_score)}</td>
                <td><button class="btn btn-primary" style="padding:0.3rem 0.8rem; font-size:0.8rem;">View</button></td>
            `;
            tr.addEventListener('click', () => selectRing(ring));
            els.tables.rings.appendChild(tr);
        });
    }

    // 3. Graph Logic
    function initGraph() {
        const elements = [];
        const addedNodes = new Set();
        const meta = analysisData.nodes_metadata || {};

        // Build a set of all aggregator nodes across all smurfing rings
        const aggregatorSet = new Set();
        (analysisData.fraud_rings || []).forEach(ring => {
            (ring.aggregators || []).forEach(a => aggregatorSet.add(a));
        });

        const addNode = (id) => {
            if (addedNodes.has(id)) return;
            let type = meta[id] ? meta[id].type : 'normal';
            let score = meta[id] ? meta[id].score : 0;
            const isAggregator = aggregatorSet.has(id);
            const size = isAggregator ? 52
                       : type === 'suspicious' ? Math.max(28, Math.min(48, 28 + score * 0.25))
                       : type === 'merchant'   ? 34
                       : 18;
            const classes = [type, isAggregator ? 'aggregator' : ''].filter(Boolean).join(' ');
            elements.push({
                data: { id, label: id, score, type, size, isAggregator },
                classes
            });
            addedNodes.add(id);
        };

        if (analysisData.graph_edges) {
            analysisData.graph_edges.forEach(e => {
                addNode(e.source);
                addNode(e.target);
                elements.push({ data: { source: e.source, target: e.target, id: `${e.source}_${e.target}` } });
            });
        }

        cy = cytoscape({
            container: els.graph.container,
            elements,
            style: [
                // ── Default Nodes ──────────────────────────────────────────────
                {
                    selector: 'node',
                    style: {
                        'background-color': '#94a3b8',
                        'background-gradient-stop-colors': '#cbd5e1 #94a3b8',
                        'width':  'data(size)',
                        'height': 'data(size)',
                        'label': 'data(label)',
                        'font-family': 'Inter, system-ui, sans-serif',
                        'font-size': 9,
                        'font-weight': 600,
                        'color': '#1e293b',
                        'text-valign': 'bottom',
                        'text-halign': 'center',
                        'text-margin-y': 4,
                        'text-outline-width': 2,
                        'text-outline-color': '#ffffff',
                        'text-max-width': 80,
                        'overflow-clip-mode': 'none',
                        'border-width': 2,
                        'border-color': '#e2e8f0',
                        'transition-property': 'background-color, border-color, width, height',
                        'transition-duration': '0.2s'
                    }
                },

                // ── Aggregator (Smurfing Center) Nodes ────────────────────────
                {
                    selector: 'node.aggregator',
                    style: {
                        'shape': 'star',
                        'background-color': '#f97316',
                        'background-gradient-direction': 'to-bottom-right',
                        'background-gradient-stop-colors': '#fdba74 #ea580c',
                        'border-color': '#c2410c',
                        'border-width': 4,
                        'width': 'data(size)',
                        'height': 'data(size)',
                        'font-size': 10,
                        'font-weight': 800,
                        'color': '#7c2d12',
                        'text-outline-color': '#fff',
                        'text-outline-width': 3,
                        'shadow-blur': 20,
                        'shadow-color': '#f97316',
                        'shadow-opacity': 0.7,
                        'shadow-offset-x': 0,
                        'shadow-offset-y': 0,
                        'z-index': 200
                    }
                },
                // ── Suspicious Nodes ───────────────────────────────────────────
                {
                    selector: 'node.suspicious',
                    style: {
                        'background-color': '#ef4444',
                        'background-gradient-direction': 'to-bottom-right',
                        'background-gradient-stop-colors': '#fca5a5 #dc2626',
                        'border-color': '#b91c1c',
                        'border-width': 3,
                        'color': '#7f1d1d',
                        'font-size': 10,
                        'font-weight': 700,
                        'text-outline-color': '#fef2f2',
                        'z-index': 10
                    }
                },

                // ── Merchant Nodes ─────────────────────────────────────────────
                {
                    selector: 'node.merchant',
                    style: {
                        'shape': 'round-rectangle',
                        'background-color': '#3b82f6',
                        'background-gradient-direction': 'to-bottom-right',
                        'background-gradient-stop-colors': '#93c5fd #1d4ed8',
                        'border-color': '#1e40af',
                        'border-width': 3,
                        'color': '#1e3a8a',
                        'font-size': 10,
                        'font-weight': 700,
                        'text-outline-color': '#eff6ff',
                        'z-index': 10
                    }
                },

                // ── Default Edges ───────────────────────────────────────────────
                {
                    selector: 'edge',
                    style: {
                        'width': 1.5,
                        'line-color': '#cbd5e1',
                        'line-style': 'solid',
                        'curve-style': 'unbundled-bezier',
                        'control-point-distances': 30,
                        'target-arrow-shape': 'triangle',
                        'target-arrow-color': '#94a3b8',
                        'arrow-scale': 0.8,
                        'opacity': 0.7,
                        'transition-property': 'line-color, opacity, width',
                        'transition-duration': '0.2s'
                    }
                },

                // ── Hidden ───────────────────────────────────────────────────
                {
                    selector: '.hidden',
                    style: { 'display': 'none' }
                },

                // ── Highlighted Edges ───────────────────────────────────────────
                {
                    selector: 'edge.highlighted',
                    style: {
                        'line-color': '#f97316',
                        'target-arrow-color': '#f97316',
                        'width': 2.5,
                        'opacity': 1,
                        'z-index': 50
                    }
                },

                // ── Highlighted Nodes ───────────────────────────────────────────
                {
                    selector: 'node.highlighted',
                    style: {
                        'border-width': 4,
                        'border-color': '#f97316',
                        'font-size': 11,
                        'font-weight': 700,
                        'text-outline-width': 3,
                        'z-index': 100,
                        'shadow-blur': 18,
                        'shadow-color': '#f97316',
                        'shadow-opacity': 0.6,
                        'shadow-offset-x': 0,
                        'shadow-offset-y': 0
                    }
                },

                // ── Hover ───────────────────────────────────────────────────────
                {
                    selector: 'node:selected',
                    style: {
                        'border-width': 4,
                        'border-color': '#7c3aed',
                        'shadow-blur': 14,
                        'shadow-color': '#7c3aed',
                        'shadow-opacity': 0.5,
                        'shadow-offset-x': 0,
                        'shadow-offset-y': 0
                    }
                }
            ],
            layout: { name: 'preset' }
        });

        // Default: HIDE ALL
        cy.elements().addClass('hidden');

        // ── TOOLTIP (Popper-style div) ──────────────────────────────────────
        const tooltip = document.createElement('div');
        tooltip.id = 'cy-tooltip';
        tooltip.style.cssText = `
            position: absolute; display: none; pointer-events: none;
            background: #0f172a; color: #f8fafc;
            padding: 8px 12px; border-radius: 8px;
            font-family: Inter, sans-serif; font-size: 12px;
            line-height: 1.6; z-index: 9999;
            box-shadow: 0 4px 20px rgba(0,0,0,0.4);
            border: 1px solid #334155;
            max-width: 200px;
        `;
        document.querySelector('.graph-container').style.position = 'relative';
        document.querySelector('.graph-container').appendChild(tooltip);

        cy.on('mouseover', 'node', (e) => {
            const node = e.target;
            const d = node.data();
            const typeLabel = d.type === 'suspicious' ? '🚨 Suspicious'
                            : d.type === 'merchant'   ? '🏪 Merchant'
                            : '⬤ Normal';
            const scoreText = d.score > 0 ? `<br><span style="color:#fca5a5">Risk Score: ${Math.round(d.score)}</span>` : '';
            tooltip.innerHTML = `<strong style="color:#f1f5f9">${d.id}</strong><br>${typeLabel}${scoreText}`;
            tooltip.style.display = 'block';
        });

        cy.on('mousemove', 'node', (e) => {
            const pos = e.renderedPosition;
            const container = els.graph.container.getBoundingClientRect();
            const cyRect = cy.container().getBoundingClientRect();
            tooltip.style.left = (pos.x + 16) + 'px';
            tooltip.style.top  = (pos.y - 10) + 'px';
        });

        cy.on('mouseout', 'node', () => {
            tooltip.style.display = 'none';
        });

        // ── Controls ────────────────────────────────────────────────────────
        els.controls.focus.addEventListener('click', () => { /* ring-click activates focus */ });
        els.controls.suspicious.addEventListener('click', () => setMode('suspicious'));
        els.controls.full.addEventListener('click', () => setMode('full'));

        els.sidePanel.close.addEventListener('click', () => {
            els.sidePanel.el.style.display = 'none';
            els.graph.section.style.gridTemplateColumns = '1fr';
        });
    }

    function selectRing(ring) {
        els.graph.placeholder.style.display = 'none';
        updateSidePanel(ring);

        const cacheKey = `ring_${ring.ring_id}`;
        const isSmurfing = (ring.pattern_type || '').includes('Smurfing');
        const aggregators = ring.aggregators || [];

        cy.batch(() => {
            cy.elements().addClass('hidden').removeClass('highlighted');
            const members = cy.collection();
            ring.member_accounts.forEach(id => {
                const n = cy.getElementById(id);
                if (n.length) members.merge(n);
            });
            const edges = members.edgesWith(members);
            members.union(edges).removeClass('hidden').addClass('highlighted');
        });

        if (isSmurfing && aggregators.length > 0 && !layoutCache[cacheKey]) {
            // ── Smurfing Star Layout: concentric with aggregators at centre ──
            const aggSet = new Set(aggregators);
            const visible = cy.nodes().not('.hidden');
            setTimeout(() => {
                const layout = cy.layout({
                    name: 'concentric',
                    animate: false,
                    padding: 60,
                    spacingFactor: 1.6,
                    concentric: (node) => aggSet.has(node.id()) ? 2 : 1,
                    levelWidth: () => 1,
                    minNodeSpacing: 28
                });
                layout.on('layoutstop', () => {
                    const pos = {};
                    cy.nodes().not('.hidden').forEach(n => { pos[n.id()] = { ...n.position() }; });
                    layoutCache[cacheKey] = pos;
                });
                layout.run();
            }, 0);
        } else {
            runLayout(cacheKey, {
                animate: true,
                animationDuration: 400,
                padding: 60,
                nodeSeparation: 80,
                idealEdgeLength: 120,
                nodeRepulsion: 5000,
                gravity: 0.4,
                numIter: 500,
                randomize: true
            });
        }

        updateControls('focus');
        showResultArea(
            `🔍 Focus View: ${ring.ring_id} — ${ isSmurfing ? '🐟 Smurfing Pattern' : 'Members' }`,
            ring.member_accounts.map(m => {
                const meta = (analysisData.nodes_metadata || {})[m] || {};
                const score = meta.score !== undefined ? ` <span style="color:#ef4444;font-weight:700">(Score: ${Math.round(meta.score)})</span>` : '';
                const type = meta.type ? ` <em style="color:#64748b">[${meta.type}]</em>` : '';
                const isAgg = aggregators.includes(m) ? ' <span style="background:#fff7ed;color:#ea580c;padding:1px 6px;border-radius:4px;font-size:0.75em;font-weight:700">⭐ Aggregator</span>' : '';
                return `<li>${m}${type}${score}${isAgg}</li>`;
            }).join('')
        );
    }
    
    function setMode(mode) {
        currentMode = mode;
        els.graph.placeholder.style.display = 'none';
        els.sidePanel.el.style.display = 'none';
        els.graph.section.style.gridTemplateColumns = "1fr";

        cy.batch(() => {
            cy.elements().removeClass('highlighted hidden');
            if (mode === 'suspicious') {
                const visibleNodes = cy.nodes().filter(n => n.hasClass('suspicious') || n.hasClass('merchant'));
                const visibleEdges = visibleNodes.edgesWith(visibleNodes);
                cy.elements().not(visibleNodes.union(visibleEdges)).addClass('hidden');

                const suspList = analysisData.suspicious_accounts || [];
                showResultArea(
                    `🚨 Suspicious Only View — ${suspList.length} Accounts`,
                    suspList.map(a =>
                        `<li><strong>${a.account_id}</strong> — Score: <span style="color:#ef4444">${Math.round(a.suspicion_score)}</span> — ${(a.detected_patterns||[]).slice(0,2).join(', ')}</li>`
                    ).join('')
                );
            } else if (mode === 'full') {
                cy.elements().removeClass('hidden');
                hideResultArea();
            }
        });

        runLayout(mode, {
            animate: true,
            animationDuration: 400,
            randomize: false,
            padding: 50,
            nodeSeparation: 70,
            idealEdgeLength: 110,
            nodeRepulsion: 4000,
            gravity: 0.5,
            numIter: 500
        });

        updateControls(mode);
    }

    /**
     * runLayout: picks the fastest appropriate layout.
     * fCOSE is never used (blocks main thread on large graphs).
     * circle / breadthfirst / grid selected by node count, all cached.
     */
    function runLayout(cacheKey, opts) {
        if (layoutCache[cacheKey]) {
            cy.layout({ name: 'preset', positions: layoutCache[cacheKey], animate: false }).run();
            return;
        }

        const visibleCount = cy.nodes().not('.hidden').length;

        let layoutOpts;
        if (visibleCount <= 12) {
            // Small ring — circle layout: beautiful, instant
            layoutOpts = { name: 'circle', animate: false, padding: 60, sort: (a, b) => a.data('type') > b.data('type') ? 1 : -1 };
        } else if (visibleCount <= 60) {
            // Medium — breadthfirst: hierarchical, very fast O(n)
            layoutOpts = { name: 'breadthfirst', animate: false, padding: 50, spacingFactor: 1.4, directed: true };
        } else {
            // Large — grid: instant, handles 100s of nodes
            layoutOpts = { name: 'grid', animate: false, padding: 40, avoidOverlap: true };
        }

        // Defer to let browser paint first (prevents "page not responding")
        setTimeout(() => {
            const layout = cy.layout(layoutOpts);
            layout.on('layoutstop', () => {
                const pos = {};
                cy.nodes().not('.hidden').forEach(n => { pos[n.id()] = { ...n.position() }; });
                layoutCache[cacheKey] = pos;
            });
            layout.run();
        }, 0);
    }

    function updateControls(activeMode) {
        Object.values(els.controls).forEach(btn => btn.classList.remove('active'));
        if (activeMode === 'focus') els.controls.focus.classList.add('active');
        if (activeMode === 'suspicious') els.controls.suspicious.classList.add('active');
        if (activeMode === 'full') els.controls.full.classList.add('active');
    }

    function showResultArea(title, listHtml) {
        if (!els.resultArea.wrapper) return;
        els.resultArea.title.textContent = title;
        els.resultArea.content.innerHTML = `<ul style="margin:0;padding-left:1.2rem;line-height:1.8">${listHtml}</ul>`;
        els.resultArea.wrapper.style.display = 'block';
    }

    function hideResultArea() {
        if (!els.resultArea.wrapper) return;
        els.resultArea.wrapper.style.display = 'none';
    }

    function updateSidePanel(ring) {
        els.sidePanel.el.style.display = 'flex';
        els.graph.section.style.gridTemplateColumns = "1fr 300px";
        
        els.sidePanel.id.textContent = ring.ring_id;
        els.sidePanel.pattern.textContent = ring.pattern_type;
        els.sidePanel.score.textContent = Math.round(ring.risk_score);
        
        els.sidePanel.desc.textContent = explainPattern(ring.pattern_type);
        
        els.sidePanel.members.innerHTML = '';
        ring.member_accounts.forEach(m => {
            const li = document.createElement('li');
            li.textContent = m;
            els.sidePanel.members.appendChild(li);
        });
    }

    function explainPattern(ptype) {
        if (ptype.includes('Cycle')) return "Circular flow of funds detected. Money returns to origin, indicating wash trading or layering.";
        if (ptype.includes('Smurfing')) return "Fan-in or fan-out pattern detected. Funds being rapidly split or consolidated across many accounts.";
        if (ptype.includes('Shell')) return "Long chain of transactions through low-activity accounts. Layering designed to distance funds from source.";
        return "Anomalous transaction pattern detected.";
    }
});
