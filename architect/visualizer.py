import os
import re
import hashlib
import json
from jinja2 import Template

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Architect-CLI Graph Report</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&family=JetBrains+Mono:wght@400;600&display=swap" rel="stylesheet">
    <script src="https://unpkg.com/vis-network/standalone/umd/vis-network.min.js"></script>
    <style>
        :root {
            --bg-a: #05070d;
            --bg-b: #0b1220;
            --panel: #101827;
            --panel-glass: rgba(16, 24, 39, 0.82);
            --ink: #eef2ff;
            --ink-soft: #9ba9c6;
            --accent: #06b6d4;
            --accent-2: #34d399;
            --stroke: #25354e;
            --shadow: 0 20px 48px rgba(3, 8, 18, 0.58);
        }

        * {
            box-sizing: border-box;
        }

        body {
            margin: 0;
            min-height: 100vh;
            color: var(--ink);
            font-family: "Space Grotesk", "Segoe UI", sans-serif;
            background:
                radial-gradient(circle at 8% 12%, rgba(6, 182, 212, 0.2), transparent 34%),
                radial-gradient(circle at 90% 8%, rgba(52, 211, 153, 0.14), transparent 35%),
                radial-gradient(circle at 50% 92%, rgba(59, 130, 246, 0.12), transparent 44%),
                linear-gradient(155deg, var(--bg-a), var(--bg-b));
            padding: 18px;
        }

        .shell {
            max-width: 1320px;
            margin: 0 auto;
            display: grid;
            grid-template-columns: 310px minmax(0, 1fr);
            gap: 20px;
            align-items: stretch;
            min-height: calc(100vh - 36px);
        }

        .panel {
            background: var(--panel-glass);
            backdrop-filter: blur(10px);
            border: 1px solid var(--stroke);
            border-radius: 18px;
            box-shadow: var(--shadow);
        }

        .sidebar {
            position: sticky;
            top: 16px;
            padding: 18px;
            max-height: calc(100vh - 52px);
            overflow: auto;
        }

        .title {
            margin: 0;
            font-size: clamp(1.36rem, 2.6vw, 1.85rem);
            line-height: 1.15;
            letter-spacing: 0.01em;
        }

        .subtitle {
            margin-top: 7px;
            margin-bottom: 0;
            color: var(--ink-soft);
            font-size: 0.95rem;
        }

        .chips {
            margin-top: 16px;
            display: grid;
            grid-template-columns: 1fr;
            gap: 8px;
        }

        .chip {
            border: 1px solid var(--stroke);
            background: rgba(11, 19, 33, 0.9);
            border-radius: 10px;
            padding: 9px 10px;
            font-size: 0.88rem;
            color: var(--ink-soft);
        }

        .chip strong {
            color: var(--ink);
            margin-right: 6px;
        }

        .controls {
            margin-top: 18px;
            padding-top: 16px;
            border-top: 1px dashed #2f4363;
            display: grid;
            gap: 10px;
        }

        .controls-grid {
            display: grid;
            gap: 10px;
        }

        .label {
            font-size: 0.76rem;
            text-transform: uppercase;
            letter-spacing: 0.09em;
            color: var(--ink-soft);
        }

        select,
        input[type="text"],
        input[type="checkbox"] {
            accent-color: var(--accent);
        }

        select,
        input[type="text"] {
            width: 100%;
            padding: 9px 10px;
            border-radius: 10px;
            border: 1px solid var(--stroke);
            font-family: "Space Grotesk", "Segoe UI", sans-serif;
            background: #0a1220;
            color: var(--ink);
            font-size: 0.93rem;
        }

        .checkbox-row {
            display: flex;
            align-items: center;
            gap: 8px;
            font-size: 0.9rem;
            color: var(--ink);
        }

        .legend {
            margin-top: 16px;
            padding-top: 14px;
            border-top: 1px dashed #2f4363;
            font-size: 0.86rem;
            color: var(--ink-soft);
            line-height: 1.5;
        }

        .relations {
            margin-top: 16px;
            padding-top: 14px;
            border-top: 1px dashed #2f4363;
        }

        .relations-title {
            margin: 0 0 8px;
            font-size: 0.78rem;
            text-transform: uppercase;
            letter-spacing: 0.09em;
            color: var(--ink-soft);
        }

        .relation-list {
            display: grid;
            gap: 7px;
            max-height: 320px;
            overflow: auto;
            padding-right: 3px;
        }

        .inline-row {
            display: grid;
            grid-template-columns: 1fr auto;
            gap: 8px;
            align-items: center;
        }

        .range-row {
            display: grid;
            gap: 6px;
        }

        .range-row input[type="range"] {
            width: 100%;
            accent-color: var(--accent-2);
        }

        .micro-note {
            font-size: 0.76rem;
            color: var(--ink-soft);
        }

        .relation-meta {
            margin-top: 7px;
            font-size: 0.76rem;
            color: var(--ink-soft);
        }

        .relation-item {
            border: 1px solid #2a3f5e;
            border-radius: 10px;
            background: rgba(10, 18, 31, 0.9);
            padding: 8px 9px;
            cursor: pointer;
            transition: border-color 120ms ease;
        }

        .relation-item:hover {
            border-color: #38bdf8;
        }

        .relation-head {
            display: flex;
            align-items: center;
            gap: 7px;
            font-size: 0.8rem;
            color: #dbe8ff;
            margin-bottom: 4px;
            font-family: "JetBrains Mono", monospace;
        }

        .relation-label {
            font-size: 0.79rem;
            color: #9fdcf7;
            line-height: 1.35;
        }

        .button-row {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 8px;
            margin-top: 6px;
        }

        .btn {
            border: 1px solid #2a567c;
            background: linear-gradient(180deg, #13273f, #0e1f35);
            color: #e6f2ff;
            border-radius: 9px;
            padding: 8px 10px;
            font-size: 0.82rem;
            cursor: pointer;
            font-family: "Space Grotesk", "Segoe UI", sans-serif;
        }

        .btn:hover {
            border-color: #38bdf8;
        }

        .legend code {
            font-family: "JetBrains Mono", monospace;
            font-size: 0.82rem;
            background: #0a1220;
            border: 1px solid #2f4363;
            border-radius: 6px;
            padding: 1px 5px;
            color: #d8e0f2;
        }

        .graph-panel {
            padding: 18px;
            min-height: calc(100vh - 52px);
            height: calc(100vh - 52px);
            overflow: auto;
            background:
                linear-gradient(180deg, rgba(13, 23, 39, 0.75), rgba(11, 18, 32, 0.92));
        }

        .network {
            width: 100%;
            min-width: 760px;
            min-height: 100%;
            height: 100%;
            padding: 8px;
            animation: riseIn 460ms ease-out;
            border-radius: 14px;
            border: 1px solid #2b405f;
            background: rgba(7, 13, 23, 0.72);
        }

        @keyframes riseIn {
            from {
                opacity: 0;
                transform: translateY(14px);
            }
            to {
                opacity: 1;
                transform: translateY(0);
            }
        }

        @media (max-width: 1060px) {
            .shell {
                grid-template-columns: 1fr;
                min-height: auto;
            }

            .sidebar {
                position: static;
                max-height: none;
                overflow: visible;
            }

            .graph-panel {
                min-height: 72vh;
                height: 72vh;
            }

            .network {
                min-width: 100%;
            }
        }
    </style>
</head>
<body>
    <div class="shell">
        <aside class="panel sidebar">
            <h1 class="title">Architect-CLI Graph Report</h1>
            <p class="subtitle">Dependency map grouped by top-level folder.</p>

            <div class="chips">
                <div class="chip"><strong>Nodes</strong>{{ node_count }}</div>
                <div class="chip"><strong>Edges</strong>{{ edge_count }}</div>
                <div class="chip"><strong>Groups</strong>{{ group_count }}</div>
            </div>

            <div class="controls">
                <div class="controls-grid">
                    <div>
                        <div class="label">Layout</div>
                        <select id="layoutSelect">
                            <option value="LR" selected>Hierarchy Left to Right</option>
                            <option value="TD">Hierarchy Top to Bottom</option>
                            <option value="force">Force Directed</option>
                        </select>
                    </div>

                    <label class="checkbox-row" for="layeredModeToggle">
                        <input id="layeredModeToggle" type="checkbox" checked />
                        Layered mode (top-level first)
                    </label>

                    <div>
                        <div class="label">Focus Node</div>
                        <input id="searchInput" type="text" placeholder="Type file name..." />
                    </div>

                    <div>
                        <div class="label">Group Filter</div>
                        <select id="groupFilter"></select>
                    </div>

                    <div class="range-row">
                        <div class="inline-row">
                            <div class="label">Visible Edges</div>
                            <div id="edgeLimitValue" class="micro-note">0</div>
                        </div>
                        <input id="edgeLimit" type="range" min="50" step="50" />
                    </div>

                    <label class="checkbox-row" for="focusModeToggle">
                        <input id="focusModeToggle" type="checkbox" />
                        Focus mode (neighbors only)
                    </label>

                    <div>
                        <div class="label">Focus Depth</div>
                        <select id="focusDepth">
                            <option value="1" selected>1 hop</option>
                            <option value="2">2 hops</option>
                            <option value="3">3 hops</option>
                        </select>
                    </div>

                    <label class="checkbox-row" for="labelsToggle">
                        <input id="labelsToggle" type="checkbox" />
                        Show edge labels on graph
                    </label>

                    <label class="checkbox-row" for="physicsToggle">
                        <input id="physicsToggle" type="checkbox" />
                        Enable physics animation
                    </label>

                    <div class="button-row">
                        <button id="fitBtn" class="btn" type="button">Fit Graph</button>
                        <button id="stabilizeBtn" class="btn" type="button">Stabilize</button>
                    </div>

                    <div class="button-row">
                        <button id="focusBtn" class="btn" type="button">Focus Search</button>
                        <button id="resetViewBtn" class="btn" type="button">Reset View</button>
                    </div>

                    <div class="button-row">
                        <button id="collapseAllBtn" class="btn" type="button">Collapse All</button>
                        <button id="expandAllBtn" class="btn" type="button">Expand All</button>
                    </div>
                </div>
            </div>

            <div class="legend">
                <div><code>vis-network</code> powers zoom, pan, selection, focus.</div>
                <div>Node color denotes top-level folder group.</div>
                <div>In layered mode, click a group node to expand/collapse its internals.</div>
                <div>Use Group Filter, Focus Mode, and Visible Edges to declutter large graphs.</div>
                <div id="visibleSummary">Visible: 0 nodes, 0 edges</div>
            </div>

            <div class="relations">
                <h2 class="relations-title">Relationships</h2>
                <div id="relationList" class="relation-list"></div>
                <div id="relationMeta" class="relation-meta"></div>
            </div>
        </aside>

        <main class="panel graph-panel">
            <div class="network" id="network"></div>
        </main>
    </div>

    <script>
        const baseNodes = {{ nodes_json }};
        const baseEdges = {{ edges_json }};
        const baseGroups = {{ groups_json }};

        let network = null;
        let baseNodeMap = new Map();
        let visibleNodeMap = new Map();
        let focusedNodeId = null;
        let renderedEdgeCount = 0;
        const expandedGroups = new Set();

        function groupNodeId(groupName) {
            return `grp::${groupName}`;
        }

        function isGroupNodeId(nodeId) {
            return String(nodeId).startsWith('grp::');
        }

        function groupNameFromNodeId(nodeId) {
            return String(nodeId).replace(/^grp::/, '');
        }

        function buildNodeMap() {
            baseNodeMap = new Map(baseNodes.map((node) => [node.id, node]));
        }

        function initializeControls() {
            const groupFilter = document.getElementById('groupFilter');
            groupFilter.innerHTML = '<option value="all" selected>All Groups</option>';
            for (const group of baseGroups) {
                const opt = document.createElement('option');
                opt.value = group.name;
                opt.textContent = `${group.name} (${group.count})`;
                groupFilter.appendChild(opt);
            }

            const edgeLimit = document.getElementById('edgeLimit');
            const maxEdgeCap = Math.max(50, Math.min(baseEdges.length, 4000));
            const defaultEdgeCap = Math.max(50, Math.min(baseEdges.length, 1200));
            edgeLimit.max = String(maxEdgeCap);
            edgeLimit.value = String(defaultEdgeCap);
            updateEdgeLimitLabel();
        }

        function buildLayeredGraph() {
            const groupedNodes = new Map();
            const layeredNodes = [];

            for (const node of baseNodes) {
                if (!groupedNodes.has(node.group)) groupedNodes.set(node.group, []);
                groupedNodes.get(node.group).push(node);
            }

            for (const [groupName, nodes] of groupedNodes.entries()) {
                if (groupName === 'root') {
                    for (const node of nodes) {
                        layeredNodes.push({ ...node, kind: 'file' });
                    }
                    continue;
                }

                const groupColor = nodes[0]?.color || {
                    background: '#153b63',
                    border: '#3ea9ff',
                    highlight: { background: '#153b63', border: '#dbeafe' },
                };
                layeredNodes.push({
                    id: groupNodeId(groupName),
                    label: `${groupName}/`,
                    path: groupName,
                    group: groupName,
                    color: groupColor,
                    title: `${groupName} (${nodes.length} files)`,
                    kind: 'group',
                    sizeHint: nodes.length,
                });

                if (expandedGroups.has(groupName)) {
                    for (const node of nodes) {
                        layeredNodes.push({ ...node, kind: 'file' });
                    }
                }
            }

            const visibleIds = new Set(layeredNodes.map((n) => n.id));
            const layeredEdgesMap = new Map();

            for (const edge of baseEdges) {
                const src = baseNodeMap.get(edge.from);
                const dst = baseNodeMap.get(edge.to);
                if (!src || !dst) continue;

                const srcId = src.group !== 'root' && !expandedGroups.has(src.group)
                    ? groupNodeId(src.group)
                    : src.id;
                const dstId = dst.group !== 'root' && !expandedGroups.has(dst.group)
                    ? groupNodeId(dst.group)
                    : dst.id;

                if (srcId === dstId) continue;
                if (!visibleIds.has(srcId) || !visibleIds.has(dstId)) continue;

                const key = `${srcId}__${dstId}`;
                const existing = layeredEdgesMap.get(key);
                if (existing) {
                    existing.weight += 1;
                    continue;
                }

                layeredEdgesMap.set(key, {
                    id: key,
                    from: srcId,
                    to: dstId,
                    label: edge.label,
                    title: edge.title,
                    weight: 1,
                });
            }

            const layeredEdges = [];
            for (const edge of layeredEdgesMap.values()) {
                if (edge.weight > 1) {
                    edge.title = `${edge.weight} aggregated dependencies`;
                    edge.label = `${edge.weight} deps`;
                }
                layeredEdges.push(edge);
            }

            return { nodes: layeredNodes, edges: layeredEdges };
        }

        function updateEdgeLimitLabel() {
            const edgeLimit = document.getElementById('edgeLimit');
            const edgeLimitValue = document.getElementById('edgeLimitValue');
            edgeLimitValue.textContent = `${edgeLimit.value}`;
        }

        function nodeMatchesQuery(node, query) {
            const q = query.toLowerCase();
            return node.label.toLowerCase().includes(q) || node.path.toLowerCase().includes(q);
        }

        function bfsNeighborhood(seedId, edges, depth) {
            const adjacency = new Map();
            for (const edge of edges) {
                if (!adjacency.has(edge.from)) adjacency.set(edge.from, new Set());
                if (!adjacency.has(edge.to)) adjacency.set(edge.to, new Set());
                adjacency.get(edge.from).add(edge.to);
                adjacency.get(edge.to).add(edge.from);
            }

            const visited = new Set([seedId]);
            let frontier = new Set([seedId]);
            for (let d = 0; d < depth; d += 1) {
                const nextFrontier = new Set();
                for (const nodeId of frontier) {
                    const neighbors = adjacency.get(nodeId);
                    if (!neighbors) continue;
                    for (const neighbor of neighbors) {
                        if (!visited.has(neighbor)) {
                            visited.add(neighbor);
                            nextFrontier.add(neighbor);
                        }
                    }
                }
                frontier = nextFrontier;
                if (frontier.size === 0) break;
            }
            return visited;
        }

        function computeVisibleGraph() {
            const groupFilter = document.getElementById('groupFilter').value;
            const focusMode = document.getElementById('focusModeToggle').checked;
            const focusDepth = Number(document.getElementById('focusDepth').value || 1);
            const edgeLimit = Number(document.getElementById('edgeLimit').value || 0);
            const layeredMode = document.getElementById('layeredModeToggle').checked;

            const sourceGraph = layeredMode ? buildLayeredGraph() : { nodes: baseNodes, edges: baseEdges };
            const sourceNodeMap = new Map(sourceGraph.nodes.map((n) => [n.id, n]));

            let edges = sourceGraph.edges;
            if (groupFilter !== 'all') {
                edges = edges.filter((edge) => {
                    const source = sourceNodeMap.get(edge.from);
                    const target = sourceNodeMap.get(edge.to);
                    return (source && source.group === groupFilter) || (target && target.group === groupFilter);
                });
            }

            if (focusMode && focusedNodeId) {
                const visibleNodes = bfsNeighborhood(focusedNodeId, edges, focusDepth);
                edges = edges.filter((edge) => visibleNodes.has(edge.from) && visibleNodes.has(edge.to));
            }

            const totalBeforeLimit = edges.length;
            if (edgeLimit > 0 && edges.length > edgeLimit) {
                edges = edges.slice(0, edgeLimit);
            }

            const visibleNodeIds = new Set();
            for (const edge of edges) {
                visibleNodeIds.add(edge.from);
                visibleNodeIds.add(edge.to);
            }

            if (edges.length === 0 && groupFilter !== 'all') {
                for (const node of baseNodes) {
                    if (node.group === groupFilter) {
                        visibleNodeIds.add(node.id);
                    }
                }
            }

            if (focusedNodeId && sourceNodeMap.has(focusedNodeId)) {
                visibleNodeIds.add(focusedNodeId);
            }

            const nodes = sourceGraph.nodes.filter((node) => visibleNodeIds.has(node.id));
            return {
                nodes,
                edges,
                totalBeforeLimit,
            };
        }

        function buildData(showLabels, visibleNodes, visibleEdges) {
            const nodes = new vis.DataSet(
                visibleNodes.map((node) => ({
                    id: node.id,
                    label: node.label,
                    title: node.title,
                    group: node.group,
                    color: node.color,
                    shape: node.kind === 'group' ? 'database' : 'box',
                    borderWidth: 1.3,
                    margin: 10,
                    size: node.kind === 'group' ? 26 : undefined,
                    widthConstraint: { maximum: 240 },
                    font: {
                        color: '#edf4ff',
                        face: 'Space Grotesk',
                        size: node.kind === 'group' ? 15 : 14,
                    },
                }))
            );

            const edges = new vis.DataSet(
                visibleEdges.map((edge) => ({
                    id: edge.id,
                    from: edge.from,
                    to: edge.to,
                    label: showLabels ? edge.label : '',
                    title: edge.title,
                    arrows: 'to',
                    width: 1.2,
                    color: {
                        color: '#78d9ff',
                        highlight: '#86efac',
                        hover: '#bae6fd',
                        inherit: false,
                    },
                    smooth: {
                        enabled: true,
                        type: 'cubicBezier',
                        roundness: 0.36,
                    },
                    font: {
                        color: '#c9daf9',
                        face: 'JetBrains Mono',
                        size: 11,
                        strokeWidth: 0,
                        align: 'middle',
                    },
                }))
            );

            return { nodes, edges };
        }

        function buildOptions(layoutMode, physicsEnabled) {
            const forceMode = layoutMode === 'force';
            return {
                autoResize: true,
                interaction: {
                    hover: true,
                    tooltipDelay: 120,
                    navigationButtons: true,
                    keyboard: true,
                    zoomView: true,
                    dragView: true,
                },
                physics: forceMode && physicsEnabled ? {
                    enabled: true,
                    stabilization: { iterations: 140 },
                    barnesHut: {
                        gravitationalConstant: -2800,
                        centralGravity: 0.22,
                        springLength: 132,
                        springConstant: 0.06,
                        damping: 0.16,
                    },
                } : { enabled: false },
                layout: forceMode ? {
                    improvedLayout: true,
                } : {
                    hierarchical: {
                        enabled: true,
                        direction: layoutMode,
                        sortMethod: 'directed',
                        nodeSpacing: 210,
                        levelSeparation: 180,
                        treeSpacing: 220,
                        parentCentralization: true,
                    },
                },
                edges: {
                    selectionWidth: 2,
                },
                nodes: {
                    shadow: {
                        enabled: true,
                        color: 'rgba(6, 14, 25, 0.6)',
                        size: 12,
                        x: 0,
                        y: 4,
                    },
                },
            };
        }

        function renderNetwork() {
            const layoutMode = document.getElementById('layoutSelect').value;
            const showLabels = document.getElementById('labelsToggle').checked;
            const physicsEnabled = document.getElementById('physicsToggle').checked;
            const container = document.getElementById('network');
            const graph = computeVisibleGraph();

            const data = buildData(showLabels, graph.nodes, graph.edges);
            const options = buildOptions(layoutMode, physicsEnabled);
            visibleNodeMap = new Map(graph.nodes.map((node) => [node.id, node]));

            renderedEdgeCount = graph.edges.length;

            network = new vis.Network(container, data, options);
            network.once('stabilizationIterationsDone', () => {
                network.fit({ animation: { duration: 300, easingFunction: 'easeInOutQuad' } });
            });

            network.on('selectNode', (params) => {
                if (params.nodes && params.nodes.length > 0) {
                    const nodeId = params.nodes[0];
                    focusedNodeId = nodeId;

                    if (document.getElementById('layeredModeToggle').checked && isGroupNodeId(nodeId)) {
                        const groupName = groupNameFromNodeId(nodeId);
                        if (expandedGroups.has(groupName)) {
                            expandedGroups.delete(groupName);
                        } else {
                            expandedGroups.add(groupName);
                        }
                        renderNetwork();
                        return;
                    }

                    if (document.getElementById('focusModeToggle').checked) {
                        renderNetwork();
                    }
                }
            });

            renderRelationshipList(graph.edges, graph.totalBeforeLimit);
            updateVisibleSummary(graph.nodes.length, graph.edges.length, graph.totalBeforeLimit);
        }

        function updateVisibleSummary(nodeCount, edgeCount, totalBeforeLimit) {
            const summary = document.getElementById('visibleSummary');
            const limitedBy = totalBeforeLimit > edgeCount ? `, capped from ${totalBeforeLimit}` : '';
            summary.textContent = `Visible: ${nodeCount} nodes, ${edgeCount} edges${limitedBy}`;
        }

        function renderRelationshipList(visibleEdges, totalBeforeLimit) {
            const list = document.getElementById('relationList');
            const meta = document.getElementById('relationMeta');
            list.innerHTML = '';

            const maxListItems = 600;
            const listed = visibleEdges.slice(0, maxListItems);

            for (const edge of listed) {
                const source = visibleNodeMap.get(edge.from);
                const target = visibleNodeMap.get(edge.to);
                const sourceLabel = source ? source.label : edge.from;
                const targetLabel = target ? target.label : edge.to;

                const item = document.createElement('button');
                item.type = 'button';
                item.className = 'relation-item';
                item.innerHTML = `
                    <div class="relation-head">
                        <span>${sourceLabel}</span>
                        <span>-></span>
                        <span>${targetLabel}</span>
                    </div>
                    <div class="relation-label">${edge.label}</div>
                `;

                item.addEventListener('click', () => {
                    if (!network) {
                        return;
                    }
                    network.selectNodes([edge.from, edge.to]);
                    network.focus(edge.to, {
                        scale: 1.08,
                        animation: {
                            duration: 360,
                            easingFunction: 'easeInOutQuad',
                        },
                    });
                });

                list.appendChild(item);
            }

            const clipped = visibleEdges.length - listed.length;
            const capHint = totalBeforeLimit > renderedEdgeCount ? ` (edge cap applied)` : '';
            if (clipped > 0) {
                meta.textContent = `Showing ${listed.length} of ${visibleEdges.length} visible relationships${capHint}. Narrow further with filters.`;
            } else {
                meta.textContent = `Showing ${visibleEdges.length} visible relationships${capHint}.`;
            }
        }

        function focusNodeByQuery() {
            if (!network) {
                return;
            }
            const query = document.getElementById('searchInput').value.trim().toLowerCase();
            if (!query) {
                return;
            }

            const match = baseNodes.find((node) => {
                return node.label.toLowerCase().includes(query) || node.path.toLowerCase().includes(query);
            });
            if (!match) {
                return;
            }

            focusedNodeId = match.id;
            if (document.getElementById('layeredModeToggle').checked && match.group !== 'root') {
                expandedGroups.add(match.group);
            }
            if (document.getElementById('focusModeToggle').checked) {
                renderNetwork();
            }

            network.selectNodes([match.id]);
            network.focus(match.id, {
                scale: 1.2,
                animation: {
                    duration: 380,
                    easingFunction: 'easeInOutQuad',
                },
            });
        }

        function resetViewState() {
            focusedNodeId = null;
            expandedGroups.clear();
            document.getElementById('searchInput').value = '';
            document.getElementById('groupFilter').value = 'all';
            document.getElementById('focusModeToggle').checked = false;
            document.getElementById('focusDepth').value = '1';
            document.getElementById('layeredModeToggle').checked = true;
            renderNetwork();
        }

        function collapseAllGroups() {
            expandedGroups.clear();
            renderNetwork();
        }

        function expandAllGroups() {
            for (const group of baseGroups) {
                if (group.name !== 'root') {
                    expandedGroups.add(group.name);
                }
            }
            renderNetwork();
        }

        document.getElementById('layoutSelect').addEventListener('change', renderNetwork);
        document.getElementById('layeredModeToggle').addEventListener('change', () => {
            focusedNodeId = null;
            renderNetwork();
        });
        document.getElementById('labelsToggle').addEventListener('change', renderNetwork);
        document.getElementById('physicsToggle').addEventListener('change', renderNetwork);
        document.getElementById('groupFilter').addEventListener('change', renderNetwork);
        document.getElementById('focusModeToggle').addEventListener('change', renderNetwork);
        document.getElementById('focusDepth').addEventListener('change', renderNetwork);
        document.getElementById('edgeLimit').addEventListener('input', () => {
            updateEdgeLimitLabel();
            renderNetwork();
        });
        document.getElementById('focusBtn').addEventListener('click', focusNodeByQuery);
        document.getElementById('resetViewBtn').addEventListener('click', resetViewState);
        document.getElementById('collapseAllBtn').addEventListener('click', collapseAllGroups);
        document.getElementById('expandAllBtn').addEventListener('click', expandAllGroups);
        document.getElementById('fitBtn').addEventListener('click', () => {
            if (network) {
                network.fit({ animation: { duration: 260, easingFunction: 'easeInOutQuad' } });
            }
        });
        document.getElementById('stabilizeBtn').addEventListener('click', () => {
            if (network) {
                network.stabilize(140);
            }
        });
        document.getElementById('searchInput').addEventListener('keydown', (event) => {
            if (event.key === 'Enter') {
                focusNodeByQuery();
            }
        });

        window.addEventListener('resize', () => {
            if (!network) {
                return;
            }
            network.redraw();
            network.fit({ animation: { duration: 180, easingFunction: 'easeInOutQuad' } });
        });

        buildNodeMap();
        initializeControls();
        renderNetwork();
    </script>
</body>
</html>
"""


def _sanitize_label(value):
    safe = str(value).replace('"', "'").replace("\n", " ").replace("|", " ")
    safe = re.sub(r"[^a-zA-Z0-9\s\.,\-\?!'/:]", "", safe)
    return safe.strip()


def _sanitize_text(value):
    safe = str(value).replace('"', "'").replace("\n", " ")
    safe = re.sub(r"[^a-zA-Z0-9\s\._\-/:]", "", safe)
    return safe.strip() or "unknown"


def _group_label(rel_path):
    parts = rel_path.split(os.sep)
    if len(parts) <= 1:
        return "root"
    return parts[0]


def _group_color(group_name):
    palette = [
        ("#153b63", "#3ea9ff"),
        ("#1b3f32", "#34d399"),
        ("#3b2f19", "#f59e0b"),
        ("#35214f", "#a78bfa"),
        ("#442227", "#fb7185"),
        ("#163842", "#22d3ee"),
    ]
    idx = int(hashlib.md5(group_name.encode("utf-8")).hexdigest(), 16) % len(palette)
    bg, border = palette[idx]
    if group_name == "root":
        return {
            "background": "#10302c",
            "border": "#2bc48a",
            "highlight": {"background": "#134238", "border": "#49de9f"},
        }
    return {
        "background": bg,
        "border": border,
        "highlight": {"background": bg, "border": "#e2e8f0"},
    }


def generate_html(edges, output_path):
    template = Template(HTML_TEMPLATE)
    
    unique_files = set()
    for s, t, _ in edges:
        unique_files.add(s)
        unique_files.add(t)
    
    # Use path+hash to avoid basename collisions across different folders.
    def make_id(path):
        basename = os.path.basename(path)
        safe_name = re.sub(r'[^a-zA-Z0-9]', '_', basename)
        short_hash = hashlib.md5(path.encode("utf-8")).hexdigest()[:8]
        return f"{safe_name}_{short_hash}"

    common_root = os.path.commonpath(list(unique_files)) if unique_files else ""

    nodes = []
    groups = {}
    for file_path in sorted(unique_files):
        node_id = make_id(file_path)
        node_name = _sanitize_text(os.path.basename(file_path))

        if common_root:
            rel_path = os.path.relpath(file_path, common_root)
        else:
            rel_path = os.path.basename(file_path)

        group_name = _group_label(rel_path)
        groups.setdefault(group_name, []).append(node_id)

        nodes.append({
            "id": node_id,
            "label": node_name,
            "path": _sanitize_text(rel_path),
            "group": group_name,
            "color": _group_color(group_name),
            "title": f"{node_name} ({_sanitize_text(rel_path)})",
        })
    
    clean_edges = []
    for s, t, l in edges:
        safe_label = _sanitize_label(l)
        clean_edges.append({
            "id": f"{make_id(s)}__{make_id(t)}",
            "from": make_id(s),
            "to": make_id(t),
            "label": safe_label,
            "title": safe_label,
        })

    group_list = [{"name": k, "count": len(v)} for k, v in sorted(groups.items())]
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(
            template.render(
                node_count=len(nodes),
                edge_count=len(clean_edges),
                group_count=len(group_list),
                nodes_json=json.dumps(nodes),
                edges_json=json.dumps(clean_edges),
                groups_json=json.dumps(group_list),
            )
        )