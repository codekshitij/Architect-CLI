import { useMemo, useState } from 'react'
import axios from 'axios'
import {
  SigmaContainer,
  useLoadGraph,
  useRegisterEvents,
  useSigma,
} from '@react-sigma/core'
import '@react-sigma/core/lib/style.css'
import './App.css'
import { MultiDirectedGraph } from 'graphology'

type SymbolNode = { id: string; label: string; type: string }
type FileNode = {
  id: string
  label: string
  full_path: string
  children: SymbolNode[]
}
type ContainerNode = {
  id: string
  label: string
  children: FileNode[]
}

type Hierarchy = {
  system: { children: ContainerNode[] }
  aggregate_edges: Array<{ source: string; target: string; weight: number }>
  file_edges: Array<{ source: string; target: string; label: string }>
}

type AnalyzeResponse = {
  analysis_id: string
  edge_count: number
  file_count: number
  hierarchy: Hierarchy
}

type SearchMatch = {
  score: number
  container_id: string
  container_label: string
  file_id: string
  file_label: string
  file_path: string
}

type SearchResponse = {
  matches: SearchMatch[]
}

type RiskResponse = {
  risks: {
    has_cycle: boolean
    cycle_path: string[]
    cross_container_edge_count: number
    potential_leaky_abstractions: string[]
  }
}

type ViewState =
  | { level: 'containers'; containerId: null; fileId: null }
  | { level: 'files'; containerId: string; fileId: null }
  | { level: 'group'; containerId: string; fileId: null; groupId: string }
  | { level: 'file'; containerId: string; fileId: string }

const API_BASE = 'http://127.0.0.1:8000'

const ROOT_GROUP = '(root)'

function getParentGroupLabel(path: string): string {
  const normalized = path.replace(/\\/g, '/')
  const parts = normalized.split('/').filter(Boolean)
  if (parts.length < 2) return ROOT_GROUP
  return parts[parts.length - 2] || ROOT_GROUP
}

function groupFilesByParent(files: FileNode[]) {
  const groups = new Map<string, FileNode[]>()
  files.forEach((file) => {
    const key = getParentGroupLabel(file.full_path)
    if (!groups.has(key)) groups.set(key, [])
    groups.get(key)!.push(file)
  })
  return groups
}

function getGroupNodeId(containerId: string, groupLabel: string) {
  return `group::${containerId}::${groupLabel}`
}

function asCircle(index: number, total: number, radius: number) {
  const angle = (2 * Math.PI * index) / Math.max(total, 1)
  return { x: Math.cos(angle) * radius, y: Math.sin(angle) * radius }
}

function buildGraph(
  hierarchy: Hierarchy,
  view: ViewState,
  highlightPath: string[],
  condenseSimilarFiles: boolean,
): MultiDirectedGraph {
  const graph = new MultiDirectedGraph()
  const containers = hierarchy.system.children
  const byName = new Map(containers.map((c) => [c.label, c]))
  const fileByPath = new Map<string, (FileNode & { containerId: string })>()

  for (const c of containers) {
    for (const f of c.children) {
      fileByPath.set(f.full_path, { ...f, containerId: c.id })
    }
  }

  const highlightedEdges = new Set<string>()
  for (let i = 0; i < highlightPath.length - 1; i += 1) {
    highlightedEdges.add(`${highlightPath[i]}->${highlightPath[i + 1]}`)
  }

  if (view.level === 'containers') {
    containers.forEach((container, i) => {
      const pos = asCircle(i, containers.length, 14)
      graph.addNode(container.id, {
        label: container.label,
        kind: 'container',
        color: '#2f81f7',
        size: 14,
        x: pos.x,
        y: pos.y,
      })
    })

    hierarchy.aggregate_edges.forEach((edge, i) => {
      const src = byName.get(edge.source)
      const dst = byName.get(edge.target)
      if (!src || !dst || !graph.hasNode(src.id) || !graph.hasNode(dst.id)) return
      graph.addEdgeWithKey(`agg-${i}`, src.id, dst.id, {
        label: `${edge.weight} deps`,
        size: Math.max(1.2, Math.min(6, edge.weight / 2)),
        color: '#8fa3ba',
      })
    })
  }

  if (view.level === 'files') {
    const container = containers.find((c) => c.id === view.containerId)
    if (!container) return graph

    graph.addNode(container.id, {
      label: `${container.label}/`,
      kind: 'container',
      color: '#2f81f7',
      size: 16,
      x: 0,
      y: 0,
    })

    if (condenseSimilarFiles) {
      const grouped = groupFilesByParent(container.children)
      const groupedLabels = Array.from(grouped.keys()).sort()
      const visibleIds = new Set<string>()
      const condensedEdgeStats = new Map<string, { source: string; target: string; count: number; highlighted: boolean }>()
      let vIndex = 0

      groupedLabels.forEach((groupLabel) => {
        const files = grouped.get(groupLabel) || []
        if (files.length >= 2) {
          const groupId = getGroupNodeId(container.id, groupLabel)
          const pos = asCircle(vIndex, groupedLabels.length, 12)
          graph.addNode(groupId, {
            label: `${groupLabel}/ (${files.length})`,
            kind: 'group',
            groupLabel,
            color: '#90e0ef',
            size: 10,
            x: pos.x,
            y: pos.y,
          })
          graph.addEdgeWithKey(`member-group-${vIndex}`, container.id, groupId, {
            size: 0.8,
            color: '#5b6b82',
          })
          visibleIds.add(groupId)
          vIndex += 1
          return
        }

        const file = files[0]
        if (!file) return
        const pos = asCircle(vIndex, container.children.length, 12)
        graph.addNode(file.id, {
          label: file.label,
          kind: 'file',
          color: '#dbe7f5',
          size: 7,
          x: pos.x,
          y: pos.y,
        })
        graph.addEdgeWithKey(`member-single-${vIndex}`, container.id, file.id, {
          size: 0.6,
          color: '#5b6b82',
        })
        visibleIds.add(file.id)
        vIndex += 1
      })

      hierarchy.file_edges.forEach((edge) => {
        const src = fileByPath.get(edge.source)
        const dst = fileByPath.get(edge.target)
        if (!src || !dst) return
        if (src.containerId !== container.id || dst.containerId !== container.id) return
        const srcGroup = getGroupNodeId(container.id, getParentGroupLabel(src.full_path))
        const dstGroup = getGroupNodeId(container.id, getParentGroupLabel(dst.full_path))
        const srcVisible = visibleIds.has(src.id) ? src.id : srcGroup
        const dstVisible = visibleIds.has(dst.id) ? dst.id : dstGroup
        if (!graph.hasNode(srcVisible) || !graph.hasNode(dstVisible) || srcVisible === dstVisible) return
        const key = `${src.id}->${dst.id}`
        const visibleKey = `${srcVisible}->${dstVisible}`
        const existing = condensedEdgeStats.get(visibleKey)
        if (existing) {
          existing.count += 1
          existing.highlighted = existing.highlighted || highlightedEdges.has(key)
          return
        }
        condensedEdgeStats.set(visibleKey, {
          source: srcVisible,
          target: dstVisible,
          count: 1,
          highlighted: highlightedEdges.has(key),
        })
      })

      Array.from(condensedEdgeStats.values()).forEach((item, idx) => {
        graph.addEdgeWithKey(`intra-condensed-${idx}`, item.source, item.target, {
          label: item.count > 1 ? `${item.count} links` : undefined,
          size: item.highlighted ? 2.8 : Math.min(2.4, 1 + item.count * 0.2),
          color: item.highlighted ? '#2f81f7' : '#8fa3ba',
        })
      })
    } else {
      container.children.forEach((file, i) => {
        const pos = asCircle(i, container.children.length, 12)
        graph.addNode(file.id, {
          label: file.label,
          kind: 'file',
          color: '#dbe7f5',
          size: 7,
          x: pos.x,
          y: pos.y,
        })
        graph.addEdgeWithKey(`member-${i}`, container.id, file.id, {
          size: 0.6,
          color: '#5b6b82',
        })
      })

      hierarchy.file_edges.forEach((edge, i) => {
        const src = fileByPath.get(edge.source)
        const dst = fileByPath.get(edge.target)
        if (!src || !dst) return
        if (src.containerId !== container.id || dst.containerId !== container.id) return
        if (!graph.hasNode(src.id) || !graph.hasNode(dst.id)) return
        const key = `${src.id}->${dst.id}`
        graph.addEdgeWithKey(`intra-${i}`, src.id, dst.id, {
          label: edge.label,
          size: highlightedEdges.has(key) ? 3 : 1.2,
          color: highlightedEdges.has(key) ? '#2f81f7' : '#8fa3ba',
        })
      })
    }
  }

  if (view.level === 'group') {
    const container = containers.find((c) => c.id === view.containerId)
    if (!container) return graph
    const grouped = groupFilesByParent(container.children)
    const files = grouped.get(view.groupId) || []
    if (files.length === 0) return graph

    graph.addNode(container.id, {
      label: `${container.label}/`,
      kind: 'container',
      color: '#2f81f7',
      size: 16,
      x: 0,
      y: 0,
    })

    files.forEach((file, i) => {
      const pos = asCircle(i, files.length, 12)
      graph.addNode(file.id, {
        label: file.label,
        kind: 'file',
        color: '#dbe7f5',
        size: 7,
        x: pos.x,
        y: pos.y,
      })
      graph.addEdgeWithKey(`group-member-${i}`, container.id, file.id, {
        size: 0.7,
        color: '#5b6b82',
      })
    })

    const groupEdgeStats = new Map<string, { source: string; target: string; count: number; highlighted: boolean; label: string }>()

    hierarchy.file_edges.forEach((edge, i) => {
      const src = fileByPath.get(edge.source)
      const dst = fileByPath.get(edge.target)
      if (!src || !dst) return
      const srcInGroup = files.some((f) => f.id === src.id)
      const dstInGroup = files.some((f) => f.id === dst.id)
      if (!srcInGroup && !dstInGroup) return

      const other = srcInGroup ? dst : src
      if (!graph.hasNode(other.id)) {
        const pos = asCircle(i, Math.max(files.length, 6), 17)
        graph.addNode(other.id, {
          label: other.label,
          kind: 'neighbor',
          color: '#8ec5ff',
          size: 6.5,
          x: pos.x,
          y: pos.y,
        })
      }

      const key = `${src.id}->${dst.id}`
      const visibleKey = `${src.id}->${dst.id}`
      const existing = groupEdgeStats.get(visibleKey)
      if (existing) {
        existing.count += 1
        existing.highlighted = existing.highlighted || highlightedEdges.has(key)
        return
      }

      groupEdgeStats.set(visibleKey, {
        source: src.id,
        target: dst.id,
        count: 1,
        highlighted: highlightedEdges.has(key),
        label: edge.label,
      })
    })

    Array.from(groupEdgeStats.values()).forEach((item, idx) => {
      graph.addEdgeWithKey(`group-focus-${idx}`, item.source, item.target, {
        label: item.count > 1 ? `${item.label} (+${item.count - 1})` : item.label,
        size: item.highlighted ? 3 : Math.min(2.6, 1.2 + item.count * 0.2),
        color: item.highlighted ? '#2f81f7' : '#8fa3ba',
      })
    })
  }

  if (view.level === 'file') {
    const container = containers.find((c) => c.id === view.containerId)
    const file = container?.children.find((f) => f.id === view.fileId)
    if (!container || !file) return graph

    graph.addNode(file.id, {
      label: file.label,
      kind: 'file',
      color: '#2f81f7',
      size: 14,
      x: 0,
      y: 0,
    })

    file.children.forEach((symbol, i) => {
      const sid = `${file.id}::${symbol.id}`
      const pos = asCircle(i, file.children.length, 9)
      graph.addNode(sid, {
        label: symbol.label,
        kind: 'symbol',
        color: '#dbe7f5',
        size: 4,
        x: pos.x,
        y: pos.y,
      })
      graph.addEdgeWithKey(`symbol-${i}`, file.id, sid, {
        size: 0.8,
        color: '#5b6b82',
      })
    })

    let nIndex = 0
    hierarchy.file_edges.forEach((edge, i) => {
      const src = fileByPath.get(edge.source)
      const dst = fileByPath.get(edge.target)
      if (!src || !dst) return

      const touches = src.id === file.id || dst.id === file.id
      if (!touches) return

      const other = src.id === file.id ? dst : src
      if (!graph.hasNode(other.id)) {
        const pos = asCircle(nIndex, 8, 16)
        graph.addNode(other.id, {
          label: other.label,
          kind: 'neighbor',
          color: '#8ec5ff',
          size: 7,
          x: pos.x,
          y: pos.y,
        })
        nIndex += 1
      }

      const key = `${src.id}->${dst.id}`
      graph.addEdgeWithKey(`focus-${i}`, src.id, dst.id, {
        label: edge.label,
        size: highlightedEdges.has(key) ? 3 : 1.6,
        color: highlightedEdges.has(key) ? '#2f81f7' : '#8fa3ba',
      })
    })
  }

  return graph
}

function GraphController({
  graph,
  onDrill,
}: {
  graph: MultiDirectedGraph
  onDrill: (node: string, kind: string) => void
}) {
  const loadGraph = useLoadGraph()
  const sigma = useSigma()
  const registerEvents = useRegisterEvents()

  useMemo(() => {
    loadGraph(graph)
    sigma.getCamera().animatedReset({ duration: 350 })
  }, [graph, loadGraph, sigma])

  useMemo(() => {
    registerEvents({
      doubleClickNode: ({ node }) => {
        const attrs = graph.getNodeAttributes(node)
        onDrill(node, String(attrs.kind || ''))
      },
    })
  }, [graph, onDrill, registerEvents])

  return null
}

function App() {
  const [projectPath, setProjectPath] = useState('/Users/kshitijmishra/tinygrad')
  const [analysisId, setAnalysisId] = useState<string>('')
  const [hierarchy, setHierarchy] = useState<Hierarchy | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [view, setView] = useState<ViewState>({ level: 'containers', containerId: null, fileId: null })
  const [history, setHistory] = useState<ViewState[]>([])
  const [traceFrom, setTraceFrom] = useState('')
  const [traceTo, setTraceTo] = useState('')
  const [highlightPath, setHighlightPath] = useState<string[]>([])
  const [searchQuery, setSearchQuery] = useState('')
  const [searchResults, setSearchResults] = useState<SearchMatch[]>([])
  const [riskSummary, setRiskSummary] = useState('')
  const [condenseSimilarFiles, setCondenseSimilarFiles] = useState(true)

  async function runAnalyze() {
    setLoading(true)
    setError('')
    try {
      const { data } = await axios.post<AnalyzeResponse>(`${API_BASE}/api/analyze`, {
        path: projectPath,
        no_llm: true,
        label_mode: 'hints',
      })
      setAnalysisId(data.analysis_id)
      setHierarchy(data.hierarchy)
      setView({ level: 'containers', containerId: null, fileId: null })
      setHistory([])
      setHighlightPath([])
      setTraceFrom('')
      setTraceTo('')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Analysis failed')
    } finally {
      setLoading(false)
    }
  }

  const graph = useMemo(() => {
    if (!hierarchy) return new MultiDirectedGraph()
    return buildGraph(hierarchy, view, highlightPath, condenseSimilarFiles)
  }, [hierarchy, view, highlightPath, condenseSimilarFiles])

  const traceOptions = useMemo(() => {
    return graph.nodes().map((id) => ({
      id,
      label: String(graph.getNodeAttribute(id, 'label') || id),
    }))
  }, [graph])

  function bfs(sourceId: string, targetId: string) {
    if (!graph.hasNode(sourceId) || !graph.hasNode(targetId)) return [] as string[]
    const queue: Array<{ id: string; path: string[] }> = [{ id: sourceId, path: [sourceId] }]
    const visited = new Set([sourceId])
    while (queue.length > 0) {
      const item = queue.shift()!
      if (item.id === targetId) return item.path
      for (const neighbor of graph.outNeighbors(item.id)) {
        if (visited.has(neighbor)) continue
        visited.add(neighbor)
        queue.push({ id: neighbor, path: [...item.path, neighbor] })
      }
    }
    return []
  }

  function onDrill(node: string, kind: string) {
    if (!hierarchy) return
    if (kind === 'container') {
      setHistory((h) => [...h, view])
      setView({ level: 'files', containerId: node, fileId: null })
      setHighlightPath([])
      return
    }
    if (kind === 'group' && (view.level === 'files' || view.level === 'group')) {
      const groupLabel = String(graph.getNodeAttribute(node, 'groupLabel') || '')
      if (!groupLabel) return
      setHistory((h) => [...h, view])
      setView({ level: 'group', containerId: view.containerId!, fileId: null, groupId: groupLabel })
      setHighlightPath([])
      return
    }
    if (kind === 'file' && view.level !== 'containers') {
      setHistory((h) => [...h, view])
      setView({ level: 'file', containerId: view.containerId!, fileId: node })
      setHighlightPath([])
    }
  }

  async function runSearchToZoom() {
    if (!analysisId || !searchQuery.trim()) return
    setError('')
    try {
      const { data } = await axios.post<SearchResponse>(`${API_BASE}/api/search`, {
        analysis_id: analysisId,
        query: searchQuery,
      })
      setSearchResults(data.matches)
      const best = data.matches[0]
      if (!best) return
      setHistory((h) => [...h, view])
      setView({ level: 'files', containerId: best.container_id, fileId: null })
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Search failed')
    }
  }

  async function runRiskAnalysis() {
    if (!analysisId) return
    setError('')
    try {
      const { data } = await axios.post<RiskResponse>(`${API_BASE}/api/risk-analysis`, {
        analysis_id: analysisId,
      })
      const r = data.risks
      const summary = `cycle=${r.has_cycle ? 'yes' : 'no'}, cross-container=${r.cross_container_edge_count}, leaky=${r.potential_leaky_abstractions.length}`
      setRiskSummary(summary)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Risk analysis failed')
    }
  }

  const breadcrumb =
    view.level === 'containers'
      ? 'Root'
      : view.level === 'files'
        ? `Root > ${view.containerId}`
        : view.level === 'group'
          ? `Root > ${view.containerId} > ${view.groupId}`
          : `Root > ${view.containerId} > ${view.fileId}`

  const canGoBack = history.length > 0
  const analysisReady = Boolean(analysisId && hierarchy)
  const canTrace = Boolean(traceFrom && traceTo)
  const hasPathHighlight = highlightPath.length > 1
  const canSearch = Boolean(analysisId && searchQuery.trim())

  function goTopLevel() {
    setHistory((h) => [...h, view])
    setView({ level: 'containers', containerId: null, fileId: null })
    setHighlightPath([])
  }

  function goBack() {
    if (!canGoBack) return
    const prev = history[history.length - 1]
    setHistory((h) => h.slice(0, -1))
    setView(prev)
    setHighlightPath([])
  }

  function runTrace() {
    if (!canTrace) return
    setHighlightPath(bfs(traceFrom, traceTo))
  }

  return (
    <div className="dashboard-shell">
      <header className="dashboard-header">
        <div>
          <p className="eyebrow">Architect v4</p>
          <h1>Code Map Dashboard</h1>
          <p className="subtle">Explore container boundaries, file dependencies, and risk hotspots without visual clutter.</p>
        </div>
        <div className="status-strip" aria-live="polite">
          <span className={`status-chip ${analysisReady ? 'ready' : ''}`}>
            {analysisReady ? 'Analysis ready' : 'No analysis'}
          </span>
          <span className="status-chip">View: {view.level}</span>
          <span className="status-chip">Path: {hasPathHighlight ? `${highlightPath.length} hops` : 'none'}</span>
        </div>
      </header>

      <div className="dashboard-grid">
        <aside className="control-panel">
          <section className="panel-card">
            <h2>Analyze Project</h2>
            <p className="panel-help">Choose your root path and generate a fresh architecture graph.</p>
            <label className="field-label" htmlFor="projectPath">Project path</label>
            <input
              id="projectPath"
              value={projectPath}
              onChange={(e) => setProjectPath(e.target.value)}
              className="control-input"
            />
            <button
              onClick={runAnalyze}
              disabled={loading}
              className="control-button primary"
            >
              {loading ? 'Analyzing...' : 'Analyze project'}
            </button>
            <div className="meta-block">
              <div>
                <span>Analysis ID</span>
                <strong>{analysisId || '-'}</strong>
              </div>
              <div>
                <span>Breadcrumb</span>
                <strong>{breadcrumb}</strong>
              </div>
            </div>
          </section>

          <section className="panel-card">
            <h2>Navigation</h2>
            <p className="panel-help">Drill with a double click in the graph, then use quick jumps here.</p>
            <label className="toggle-row" htmlFor="condenseSimilarFiles">
              <span>Condense similar files</span>
              <input
                id="condenseSimilarFiles"
                type="checkbox"
                checked={condenseSimilarFiles}
                onChange={(e) => setCondenseSimilarFiles(e.target.checked)}
              />
            </label>
            <div className="button-row">
              <button onClick={goTopLevel} className="control-button secondary">Top level</button>
              <button onClick={goBack} disabled={!canGoBack} className="control-button secondary">Back</button>
            </div>
          </section>

          <details className="panel-card collapsible" open>
            <summary>
              <h2>Trace Path</h2>
              <span>Shortest path in current layer</span>
            </summary>
            <label className="field-label" htmlFor="traceFrom">From</label>
            <select
              id="traceFrom"
              value={traceFrom}
              onChange={(e) => setTraceFrom(e.target.value)}
              className="control-input"
            >
              <option value="">Choose source...</option>
              {traceOptions.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.label}
                </option>
              ))}
            </select>
            <label className="field-label" htmlFor="traceTo">To</label>
            <select
              id="traceTo"
              value={traceTo}
              onChange={(e) => setTraceTo(e.target.value)}
              className="control-input"
            >
              <option value="">Choose destination...</option>
              {traceOptions.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.label}
                </option>
              ))}
            </select>
            <button onClick={runTrace} disabled={!canTrace} className="control-button secondary">
              Trace path
            </button>
          </details>

          <details className="panel-card collapsible" open>
            <summary>
              <h2>Search and Zoom</h2>
              <span>Jump to the most relevant file cluster</span>
            </summary>
            <label className="field-label" htmlFor="searchQuery">Search query</label>
            <input
              id="searchQuery"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="scheduler tensor"
              className="control-input"
            />
            <button onClick={runSearchToZoom} disabled={!canSearch} className="control-button secondary">
              Search and zoom
            </button>
            {searchResults.length > 0 ? (
              <p className="result-text">
                Best match: {searchResults[0].container_label}/{searchResults[0].file_label}
              </p>
            ) : null}
          </details>

          <details className="panel-card collapsible">
            <summary>
              <h2>Risk Analysis</h2>
              <span>Cycles and cross-container coupling</span>
            </summary>
            <button onClick={runRiskAnalysis} disabled={!analysisId} className="control-button secondary">
              Analyze risks
            </button>
            {riskSummary ? <p className="result-text warning">{riskSummary}</p> : null}
          </details>

          {error ? <p className="error-banner">{error}</p> : null}
        </aside>

        <main className="graph-stage" aria-label="Architecture graph">
          <div className="graph-canvas">
            <SigmaContainer
              style={{ height: '100%' }}
              settings={{
                renderEdgeLabels: false,
                defaultNodeColor: '#2f81f7',
                labelDensity: 0.08,
                labelGridCellSize: 120,
                minCameraRatio: 0.05,
                maxCameraRatio: 5,
              }}
            >
              <GraphController graph={graph} onDrill={onDrill} />
            </SigmaContainer>
          </div>
        </main>
      </div>
    </div>
  )
}

export default App
