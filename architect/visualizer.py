import json
import os
import re
from jinja2 import Template


HTML_TEMPLATE = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Architect-CLI v3 | Pro Map</title>
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;600;800&family=JetBrains+Mono:wght@400;600&display=swap" rel="stylesheet" />
  <script src="https://unpkg.com/graphology@0.25.4/dist/graphology.umd.min.js"></script>
  <script src="https://unpkg.com/graphology-layout-forceatlas2@0.10.1/browser/graphology-layout-forceatlas2.min.js"></script>
  <script src="https://unpkg.com/sigma@2.4.0/build/sigma.min.js"></script>
  <style>
    :root {
      --bg-0: #0d1117;
      --bg-1: #111827;
      --bg-2: #161f2b;
      --panel: rgba(17, 24, 39, 0.84);
      --accent: #2f81f7;
      --accent-hover: #1f6feb;
      --focus-ring: rgba(47, 129, 247, 0.35);
      --border: #253041;
      --text: #e6edf3;
      --text-muted: #9fb0c3;
      --edge: rgba(143, 163, 186, 0.28);
      --edge-dim: rgba(143, 163, 186, 0.12);
      --edge-active: rgba(47, 129, 247, 0.95);
    }

    body {
      margin: 0; padding: 0;
      background: linear-gradient(160deg, var(--bg-0), var(--bg-1));
      color: var(--text);
      font-family: 'Plus Jakarta Sans', sans-serif;
      overflow: hidden;
      height: 100vh;
      display: flex;
    }

    /* Cinematic Background */
    .bg-effects {
      position: absolute; inset: 0; z-index: -1;
      background: 
        radial-gradient(circle at 20% 30%, rgba(47, 129, 247, 0.08), transparent 40%),
        radial-gradient(circle at 80% 70%, rgba(159, 176, 195, 0.06), transparent 40%);
    }

    .dashboard {
      display: flex; width: 100%; height: 100%;
      padding: 20px; gap: 20px;
    }

    /* Sidebar - Glassmorphism */
    .sidebar {
      width: 320px;
      background: var(--panel);
      backdrop-filter: blur(14px);
      border: 1px solid var(--border);
      border-radius: 24px;
      padding: 24px;
      display: flex; flex-direction: column;
      box-shadow: 0 20px 42px rgba(2, 6, 12, 0.45);
    }

    h1 {
      font-size: 1.2rem; font-weight: 800; margin: 0;
      letter-spacing: -0.02em; text-transform: uppercase;
      color: var(--text);
    }

    .stats {
      display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin: 20px 0;
    }

    .stat-card {
      background: rgba(255, 255, 255, 0.03);
      padding: 12px; border-radius: 12px; border: 1px solid var(--border);
      font-size: 0.75rem; color: var(--text-muted);
    }

    .stat-card b { display: block; font-size: 1rem; color: #76a9fa; }

    .btn {
      background: rgba(255,255,255,0.03);
      border: 1px solid var(--border);
      color: var(--text);
      padding: 10px; border-radius: 8px;
      font-size: 0.85rem; font-weight: 600;
      cursor: pointer; transition: all 0.2s;
      margin-bottom: 8px;
    }

    .btn:hover { background: rgba(47, 129, 247, 0.16); border-color: var(--accent); }

    .btn-primary { background: var(--accent); color: #f8fbff; border-color: var(--accent); }
    .btn-primary:hover { background: var(--accent-hover); }

    .btn:focus-visible,
    select:focus-visible {
      outline: none;
      box-shadow: 0 0 0 3px var(--focus-ring);
    }

    /* Graph Canvas */
    .viewport {
      flex: 1; position: relative;
      background: linear-gradient(160deg, var(--bg-1), var(--bg-2));
      border-radius: 24px; border: 1px solid var(--border);
      overflow: hidden;
    }

    #sigma-container { width: 100%; height: 100%; }

    .node-label { background: rgba(13, 17, 23, 0.92); border: 1px solid var(--border); padding: 4px 8px; border-radius: 4px; }
  </style>
</head>
<body>
  <div class="bg-effects"></div>
  <div class="dashboard">
    <aside class="sidebar">
      <h1>Architect CLI <small>v3.0</small></h1>
      <p style="color: var(--text-muted); font-size: 0.8rem;">Local Intelligence & WebGL Visualizer</p>

      <div class="stats">
        <div class="stat-card">Containers <b id="container-count">-</b></div>
        <div class="stat-card">Files <b id="file-count">-</b></div>
      </div>

      <div style="flex: 1; overflow-y: auto;">
        <label style="font-size: 0.7rem; color: var(--text-muted); text-transform: uppercase;">Navigation</label>
        <div style="margin-top: 10px;">
          <button class="btn" id="homeBtn">Top Level</button>
          <button class="btn" id="backBtn">Go Back</button>
          <button class="btn" id="toggleSemantic">Semantic Zoom: ON</button>
        </div>

        <label style="font-size: 0.7rem; color: var(--text-muted); text-transform: uppercase; margin-top: 20px; display: block;">Path Discovery</label>
        <div style="margin-top: 10px; display: flex; flex-direction: column; gap: 8px;">
          <select id="traceFrom" class="btn" style="text-align: left;"></select>
          <select id="traceTo" class="btn" style="text-align: left;"></select>
          <button class="btn btn-primary" id="traceBtn">Trace Path</button>
        </div>
      </div>

      <div id="zoomMeta" style="font-size: 0.7rem; color: var(--text-muted); text-align: center; border-top: 1px solid var(--border); padding-top: 15px;">
        Layer: Containers
      </div>
    </aside>

    <main class="viewport">
      <div id="sigma-container"></div>
    </main>
  </div>

  <script>
    const graphData = {{ hierarchy_json }};
    const containers = graphData.system.children || [];
    const aggregateEdges = graphData.aggregate_edges || [];
    const fileEdges = graphData.file_edges || [];

    const colors = ["#2f81f7", "#1f6feb", "#316dca", "#3b82f6", "#4f78c4", "#2f5fa5"];
    const getFolderColor = (name) => {
      let hash = 0;
      for (let i = 0; i < name.length; i += 1) hash = name.charCodeAt(i) + ((hash << 5) - hash);
      return colors[Math.abs(hash) % colors.length];
    };

    const containerById = new Map(containers.map((c) => [c.id, c]));
    const containerByName = new Map(containers.map((c) => [c.label, c]));
    const fileById = new Map();
    const fileByPath = new Map();
    for (const container of containers) {
      for (const file of container.children || []) {
        fileById.set(file.id, { ...file, containerId: container.id, containerName: container.label });
        fileByPath.set(file.full_path, { ...file, containerId: container.id, containerName: container.label });
      }
    }

    const edgeByFileIds = [];
    for (const edge of fileEdges) {
      const src = fileByPath.get(edge.source);
      const dst = fileByPath.get(edge.target);
      if (!src || !dst) continue;
      edgeByFileIds.push({
        sourceId: src.id,
        targetId: dst.id,
        label: edge.label || "dependency",
        sourceContainerId: src.containerId,
        targetContainerId: dst.containerId,
      });
    }

    const history = [];
    let state = { level: "containers", containerId: null, fileId: null };
    let renderer = null;
    let graph = null;
    let semanticZoom = true;
    let cameraRatio = 1;

    function newGraph() {
      return new graphology.Graph({ type: "directed", multi: true });
    }

    function addNode(g, id, attrs) {
      if (!g.hasNode(id)) g.addNode(id, attrs);
    }

    function addEdge(g, source, target, attrs, keyPrefix) {
      const key = `${keyPrefix}:${source}->${target}:${Math.random().toString(36).slice(2, 8)}`;
      g.addEdgeWithKey(key, source, target, attrs);
    }

    function buildContainersGraph() {
      const g = newGraph();
      let idx = 0;
      for (const c of containers) {
        addNode(g, c.id, {
          label: c.label,
          kind: "container",
          size: 15,
          color: getFolderColor(c.label),
          x: Math.cos(idx) * 120,
          y: Math.sin(idx) * 120,
        });
        idx += 1;
      }

      for (const edge of aggregateEdges) {
        const src = containerByName.get(edge.source);
        const dst = containerByName.get(edge.target);
        if (!src || !dst) continue;
        addEdge(g, src.id, dst.id, {
          kind: "aggregate",
          size: Math.max(1.5, Math.min(7, edge.weight / 2)),
          color: "rgba(143, 163, 186, 0.28)",
          label: `${edge.weight} deps`,
        }, "agg");
      }
      return g;
    }

    function buildContainerGraph(containerId) {
      const g = newGraph();
      const container = containerById.get(containerId);
      if (!container) return g;

      addNode(g, container.id, {
        label: `${container.label}/`,
        kind: "container",
        size: 18,
        color: getFolderColor(container.label),
        x: 0,
        y: 0,
      });

      const files = container.children || [];
      let idx = 0;
      for (const file of files) {
        const angle = (Math.PI * 2 * idx) / Math.max(files.length, 1);
        addNode(g, file.id, {
          label: file.label,
          kind: "file",
          size: 7,
          color: "#dbe7f5",
          x: Math.cos(angle) * 170,
          y: Math.sin(angle) * 170,
          fullPath: file.full_path,
        });
        addEdge(g, container.id, file.id, {
          kind: "membership",
          size: 0.7,
          color: "rgba(143, 163, 186, 0.18)",
        }, "member");
        idx += 1;
      }

      for (const edge of edgeByFileIds) {
        if (edge.sourceContainerId !== containerId || edge.targetContainerId !== containerId) {
          continue;
        }
        if (!g.hasNode(edge.sourceId) || !g.hasNode(edge.targetId)) continue;
        addEdge(g, edge.sourceId, edge.targetId, {
          kind: "file-relation",
          size: 1.6,
          color: "rgba(143, 163, 186, 0.36)",
          label: edge.label,
        }, "intra");
      }
      return g;
    }

    function buildFileGraph(fileId) {
      const g = newGraph();
      const file = fileById.get(fileId);
      if (!file) return g;

      addNode(g, file.id, {
        label: file.label,
        kind: "file",
        size: 13,
        color: "#2f81f7",
        x: 0,
        y: 0,
      });

      const selectedContainer = containerById.get(file.containerId);
      const symbols = (selectedContainer?.children || []).find((f) => f.id === file.id)?.children || [];

      let idx = 0;
      for (const symbol of symbols) {
        const angle = (Math.PI * 2 * idx) / Math.max(symbols.length, 1);
        const symbolId = `${file.id}::${symbol.id}`;
        addNode(g, symbolId, {
          label: symbol.label,
          kind: symbol.type || "symbol",
          size: 5,
          color: "#dbe7f5",
          x: Math.cos(angle) * 95,
          y: Math.sin(angle) * 95,
        });
        addEdge(g, file.id, symbolId, {
          kind: "symbol",
          size: 0.8,
          color: "rgba(143, 163, 186, 0.24)",
        }, "symbol");
        idx += 1;
      }

      const neighborIds = new Set();
      for (const edge of edgeByFileIds) {
        if (edge.sourceId === file.id) neighborIds.add(edge.targetId);
        if (edge.targetId === file.id) neighborIds.add(edge.sourceId);
      }

      let nidx = 0;
      for (const neighborId of neighborIds) {
        const neighbor = fileById.get(neighborId);
        if (!neighbor) continue;
        const angle = (Math.PI * 2 * nidx) / Math.max(neighborIds.size, 1);
        addNode(g, neighbor.id, {
          label: neighbor.label,
          kind: "neighbor",
          size: 7,
          color: "#8ec5ff",
          x: Math.cos(angle) * 190,
          y: Math.sin(angle) * 190,
        });
        nidx += 1;
      }

      for (const edge of edgeByFileIds) {
        if (!g.hasNode(edge.sourceId) || !g.hasNode(edge.targetId)) continue;
        if (edge.sourceId !== file.id && edge.targetId !== file.id) continue;
        addEdge(g, edge.sourceId, edge.targetId, {
          kind: "relation-focus",
          size: 2.2,
          color: "rgba(143, 163, 186, 0.52)",
          label: edge.label,
        }, "focus");
      }
      return g;
    }

    function resolveSigmaCtor() {
      if (window.sigma && window.sigma.Sigma) return window.sigma.Sigma;
      if (window.Sigma) return window.Sigma;
      throw new Error("Sigma runtime failed to load from CDN");
    }

    function applyLayout(g) {
      const fa2 =
        window.graphologyLayoutForceatlas2 ||
        window.graphologyLayoutForceAtlas2 ||
        window.layoutForceAtlas2 ||
        window.forceAtlas2;
      if (fa2 && typeof fa2.assign === "function") {
        fa2.assign(g, { iterations: 90, settings: { gravity: 1, scalingRatio: 3 } });
      }
    }

    function edgeWeightLabel(edgeAttrs) {
      return edgeAttrs.label || "dependency";
    }

    function refreshTraceSelectors() {
      const from = document.getElementById("traceFrom");
      const to = document.getElementById("traceTo");
      from.innerHTML = '<option value="">From...</option>';
      to.innerHTML = '<option value="">To...</option>';
      if (!graph) return;

      graph.forEachNode((id, attrs) => {
        if (attrs.kind === "symbol") return;
        const a = document.createElement("option");
        const b = document.createElement("option");
        a.value = id;
        b.value = id;
        a.textContent = attrs.label;
        b.textContent = attrs.label;
        from.appendChild(a);
        to.appendChild(b);
      });
    }

    function updateMeta() {
      const levelLabel =
        state.level === "containers"
          ? "Containers"
          : state.level === "files"
            ? `Files in ${containerById.get(state.containerId)?.label || "container"}`
            : `Internals of ${fileById.get(state.fileId)?.label || "file"}`;
      document.getElementById("zoomMeta").innerText = `Layer: ${levelLabel}`;
      document.getElementById("container-count").innerText = containers.length;
      document.getElementById("file-count").innerText = fileById.size;
    }

    function buildStateGraph() {
      if (state.level === "files") return buildContainerGraph(state.containerId);
      if (state.level === "file") return buildFileGraph(state.fileId);
      return buildContainersGraph();
    }

    function renderState() {
      graph = buildStateGraph();
      applyLayout(graph);

      if (renderer) renderer.kill();
      const SigmaCtor = resolveSigmaCtor();
      renderer = new SigmaCtor(graph, document.getElementById("sigma-container"), {
        renderLabels: true,
        defaultEdgeType: "arrow",
        labelFont: "Plus Jakarta Sans",
        labelColor: { color: "#e6edf3" },
        labelSize: 12,
        nodeReducer: (_id, attrs) => {
          const reduced = { ...attrs };
          if (semanticZoom && cameraRatio > 1.5 && attrs.kind === "file") reduced.label = "";
          return reduced;
        },
        edgeReducer: (_id, attrs) => {
          const reduced = { ...attrs };
          if (semanticZoom && cameraRatio > 1.2 && attrs.kind === "file-relation") reduced.hidden = true;
          return reduced;
        },
      });
      cameraRatio = renderer.getCamera().ratio;

      renderer.getCamera().on("updated", () => {
        cameraRatio = renderer.getCamera().ratio;
      });

      renderer.on("doubleClickNode", ({ node }) => {
        const attrs = graph.getNodeAttributes(node);
        if (attrs.kind === "container") {
          history.push({ ...state });
          state = { level: "files", containerId: node, fileId: null };
          renderState();
          return;
        }
        if (attrs.kind === "file") {
          history.push({ ...state });
          state = { level: "file", containerId: state.containerId, fileId: node };
          renderState();
        }
      });

      refreshTraceSelectors();
      updateMeta();
    }

    function bfsPath(sourceId, targetId) {
      if (!graph || !graph.hasNode(sourceId) || !graph.hasNode(targetId)) return [];
      const queue = [[sourceId, [sourceId]]];
      const visited = new Set([sourceId]);
      while (queue.length > 0) {
        const [current, path] = queue.shift();
        if (current === targetId) return path;
        for (const neighbor of graph.outNeighbors(current)) {
          if (visited.has(neighbor)) continue;
          visited.add(neighbor);
          queue.push([neighbor, [...path, neighbor]]);
        }
      }
      return [];
    }

    function highlightPath(path) {
      if (!renderer || !graph || path.length < 2) return;
      const edgesInPath = new Set();
      for (let i = 0; i < path.length - 1; i += 1) {
        const source = path[i];
        const target = path[i + 1];
        const edge = graph.edge(source, target);
        if (edge) edgesInPath.add(edge);
      }

      renderer.setSetting("edgeReducer", (id, attrs) => {
        const reduced = { ...attrs };
        if (edgesInPath.has(id)) {
          reduced.color = "rgba(47, 129, 247, 0.95)";
          reduced.size = Math.max(2.8, attrs.size || 2);
          reduced.label = edgeWeightLabel(attrs);
        } else {
          reduced.color = "rgba(143, 163, 186, 0.12)";
        }
        return reduced;
      });
      renderer.refresh();
    }

    document.getElementById("toggleSemantic").addEventListener("click", () => {
      semanticZoom = !semanticZoom;
      document.getElementById("toggleSemantic").innerText = `Semantic Zoom: ${semanticZoom ? "ON" : "OFF"}`;
      if (renderer) renderer.refresh();
    });

    document.getElementById("homeBtn").addEventListener("click", () => {
      history.push({ ...state });
      state = { level: "containers", containerId: null, fileId: null };
      renderState();
    });

    document.getElementById("backBtn").addEventListener("click", () => {
      if (history.length === 0) return;
      state = history.pop();
      renderState();
    });

    document.getElementById("traceBtn").addEventListener("click", () => {
      const sourceId = document.getElementById("traceFrom").value;
      const targetId = document.getElementById("traceTo").value;
      if (!sourceId || !targetId) return;
      const path = bfsPath(sourceId, targetId);
      if (path.length === 0) {
        document.getElementById("zoomMeta").innerText = "No path found in current layer.";
        return;
      }
      highlightPath(path);
      document.getElementById("zoomMeta").innerText = `Path traced with ${Math.max(0, path.length - 1)} edge(s).`;
    });

    renderState();

  </script>
</body>
</html>
"""


def _sanitize_label(value):
  safe = str(value).replace('"', "'").replace("\n", " ").replace("|", " ")
  safe = re.sub(r"[^a-zA-Z0-9\s\.,\-\?!'/:]", "", safe)
  return safe.strip() or "dependency"


def _sanitize_text(value):
  safe = str(value).replace('"', "'").replace("\n", " ")
  safe = re.sub(r"[^a-zA-Z0-9\s\._\-/:]", "", safe)
  return safe.strip() or "unknown"


def _build_fallback_hierarchy(edges):
  unique_files = sorted({s for s, _, _ in edges} | {t for _, t, _ in edges})
  common_root = os.path.commonpath(unique_files) if unique_files else ""

  containers = {}
  for path in unique_files:
    rel = os.path.relpath(path, common_root) if common_root else os.path.basename(path)
    parts = rel.split(os.sep)
    group = parts[0] if len(parts) > 1 else "root"
    containers.setdefault(group, []).append(
      {
        "id": _sanitize_text(path),
        "label": _sanitize_text(os.path.basename(path)),
        "path": _sanitize_text(rel),
        "full_path": path,
        "type": "file",
        "children": [],
      }
    )

  return {
    "system": {
      "id": "system",
      "label": "Architect System",
      "type": "system",
      "children": [
        {
          "id": _sanitize_text(group),
          "label": _sanitize_text(group),
          "type": "container",
          "children": files,
        }
        for group, files in sorted(containers.items())
      ],
    },
    "aggregate_edges": [],
    "file_edges": [
      {
        "source": s,
        "target": t,
        "label": _sanitize_label(l),
        "source_group": "root",
        "target_group": "root",
      }
      for s, t, l in edges
    ],
  }


def generate_html(edges, output_path, hierarchical_graph=None):
  hierarchy = hierarchical_graph if hierarchical_graph else _build_fallback_hierarchy(edges)
  for edge in hierarchy.get("file_edges", []):
    edge["label"] = _sanitize_label(edge.get("label", "dependency"))

  template = Template(HTML_TEMPLATE)
  with open(output_path, "w", encoding="utf-8") as f:
    f.write(template.render(hierarchy_json=json.dumps(hierarchy)))