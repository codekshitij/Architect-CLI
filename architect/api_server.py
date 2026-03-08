import os
import uuid
from datetime import datetime
from typing import Any
import re
import json

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from architect.analysis_core import (
    _find_path,
    apply_focus,
    build_hierarchical_graph,
    build_indexes,
    discover_files,
    label_edges,
    load_cache,
    resolve_edges,
    resolve_llm_budget,
    resolve_workers,
    save_cache,
    scan_files,
)
from architect.brain import InferenceEngine
from architect.scanner import UniversalScanner


class AnalyzeRequest(BaseModel):
    path: str = Field(..., description="Absolute path of repository to analyze")
    model: str = Field(default="qwen2.5-coder:7b")
    focus: str | None = None
    max_edges: int = 0
    workers: int = 0
    no_llm: bool = False
    label_mode: str = Field(default="hybrid")
    llm_max_edges: int | None = None
    max_targets_per_dep: int = 8
    cache_file: str = Field(default=".architect_cache.json")
    no_cache: bool = False


class PathExplanationRequest(BaseModel):
    analysis_id: str
    source: str
    target: str


app = FastAPI(title="Architect-CLI v4 API", version="4.0-prototype")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5173",
        "http://localhost:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

ANALYSIS_STORE: dict[str, dict[str, Any]] = {}
ANALYSIS_STORE_FILE = ".architect_analysis_store.json"


class RiskAnalysisRequest(BaseModel):
    analysis_id: str
    source: str | None = None
    target: str | None = None


class SearchRequest(BaseModel):
    analysis_id: str
    query: str


def _persistable_store() -> dict[str, dict[str, Any]]:
    snapshot: dict[str, dict[str, Any]] = {}
    for key, value in ANALYSIS_STORE.items():
        snapshot[key] = {
            "edges": value.get("edges", []),
            "file_cache": value.get("file_cache", {}),
            "project_path": value.get("project_path", ""),
            "created_at": value.get("created_at", ""),
            "llm_model": value.get("llm_model", ""),
            "llm_enabled": value.get("llm_enabled", False),
        }
    return snapshot


def _save_analysis_store() -> None:
    data = _persistable_store()
    with open(ANALYSIS_STORE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f)


def _load_analysis_store() -> None:
    if not os.path.exists(ANALYSIS_STORE_FILE):
        return
    try:
        with open(ANALYSIS_STORE_FILE, "r", encoding="utf-8") as f:
            payload = json.load(f)
    except (OSError, json.JSONDecodeError):
        return

    if not isinstance(payload, dict):
        return

    for key, value in payload.items():
        if not isinstance(value, dict):
            continue
        ANALYSIS_STORE[key] = {
            "edges": value.get("edges", []),
            "file_cache": value.get("file_cache", {}),
            "brain": None,
            "created_at": value.get("created_at", ""),
            "project_path": value.get("project_path", ""),
            "llm_model": value.get("llm_model", ""),
            "llm_enabled": value.get("llm_enabled", False),
        }


def _adjacency(edges: list[tuple[str, str, str]]) -> dict[str, set[str]]:
    graph: dict[str, set[str]] = {}
    for source, target, _ in edges:
        graph.setdefault(source, set()).add(target)
        graph.setdefault(target, set())
    return graph


def _detect_cycle(edges: list[tuple[str, str, str]]) -> list[str]:
    graph = _adjacency(edges)
    visited: set[str] = set()
    stack: set[str] = set()
    parent: dict[str, str] = {}

    def dfs(node: str) -> list[str]:
        visited.add(node)
        stack.add(node)
        for neighbor in graph.get(node, set()):
            if neighbor not in visited:
                parent[neighbor] = node
                cycle = dfs(neighbor)
                if cycle:
                    return cycle
            elif neighbor in stack:
                cycle_path = [neighbor]
                current = node
                while current != neighbor and current in parent:
                    cycle_path.append(current)
                    current = parent[current]
                cycle_path.append(neighbor)
                cycle_path.reverse()
                return cycle_path
        stack.remove(node)
        return []

    for node in graph:
        if node in visited:
            continue
        cycle = dfs(node)
        if cycle:
            return cycle
    return []


def _container_name(path: str, project_path: str) -> str:
    try:
        rel = os.path.relpath(path, project_path)
    except ValueError:
        return "root"
    parts = rel.split(os.sep)
    if len(parts) <= 1:
        return "root"
    return parts[0]


def _risk_flags(payload: dict[str, Any], source: str | None, target: str | None) -> dict[str, Any]:
    edges: list[tuple[str, str, str]] = payload.get("edges", [])
    project_path = payload.get("project_path", "")

    cycle = _detect_cycle(edges)
    cross_container_edges = 0
    per_source_cross: dict[str, int] = {}
    for src, dst, _ in edges:
        if _container_name(src, project_path) != _container_name(dst, project_path):
            cross_container_edges += 1
            per_source_cross[src] = per_source_cross.get(src, 0) + 1

    leaky_sources = [
        path for path, count in per_source_cross.items() if count >= 4
    ]

    scoped_path = []
    scoped_labels = []
    if source and target:
        scoped_path, scoped_labels = _find_path(source, target, edges)

    return {
        "has_cycle": bool(cycle),
        "cycle_path": cycle,
        "cross_container_edge_count": cross_container_edges,
        "potential_leaky_abstractions": leaky_sources,
        "scoped_path": scoped_path,
        "scoped_labels": scoped_labels,
    }


def _search_targets(payload: dict[str, Any], query: str) -> list[dict[str, Any]]:
    hierarchy = build_hierarchical_graph(payload.get("edges", []), {})
    q = query.strip().lower()
    terms = [token for token in re.split(r"\W+", q) if token]

    results: list[dict[str, Any]] = []
    for container in hierarchy["system"]["children"]:
        container_label = container["label"]
        for file_node in container["children"]:
            text = f"{container_label} {file_node['label']} {file_node['path']}".lower()
            score = sum(2 for term in terms if term in text)
            if q and q in text:
                score += 3
            for child in file_node.get("children", []):
                child_text = f"{child.get('label', '')}".lower()
                if q and q in child_text:
                    score += 2
                score += sum(1 for term in terms if term in child_text)
            if score <= 0:
                continue
            results.append(
                {
                    "score": score,
                    "container_id": container["id"],
                    "container_label": container_label,
                    "file_id": file_node["id"],
                    "file_label": file_node["label"],
                    "file_path": file_node["path"],
                }
            )

    results.sort(key=lambda item: item["score"], reverse=True)
    return results[:15]


_load_analysis_store()


@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "architect-api"}


@app.post("/api/analyze")
async def analyze(req: AnalyzeRequest) -> dict[str, Any]:
    project_path = os.path.abspath(req.path)
    if not os.path.isdir(project_path):
        raise HTTPException(status_code=400, detail=f"Invalid path: {project_path}")

    scanner = UniversalScanner()
    workers = resolve_workers(req.workers)
    effective_label_mode = "hints" if req.no_llm else req.label_mode
    llm_needed = effective_label_mode != "hints"
    brain = InferenceEngine(model=req.model) if llm_needed else None

    use_cache = not req.no_cache and llm_needed
    cache_file = os.path.abspath(req.cache_file)
    cache_data = load_cache(cache_file) if use_cache else {}

    all_paths = discover_files(project_path)
    by_filename, by_stem = build_indexes(all_paths)
    file_cache, raw_deps, symbol_index = scan_files(scanner, all_paths, workers)

    edges, edge_hints = resolve_edges(
        raw_deps,
        by_filename,
        by_stem,
        max_targets_per_dep=req.max_targets_per_dep,
    )
    edges, edge_hints = apply_focus(edges, edge_hints, req.focus)

    if req.max_edges > 0:
        edges = edges[: req.max_edges]

    llm_budget = resolve_llm_budget(effective_label_mode, req.llm_max_edges, len(edges))
    final_edges = label_edges(
        edges,
        edge_hints,
        file_cache,
        brain,
        req.no_llm,
        workers,
        use_cache,
        cache_data,
        label_mode=effective_label_mode,
        llm_max_edges=llm_budget,
    )

    if use_cache:
        save_cache(cache_file, cache_data)

    hierarchy = build_hierarchical_graph(final_edges, symbol_index)
    analysis_id = str(uuid.uuid4())
    ANALYSIS_STORE[analysis_id] = {
        "edges": final_edges,
        "file_cache": file_cache,
        "brain": brain,
        "created_at": datetime.utcnow().isoformat() + "Z",
        "project_path": project_path,
        "llm_model": req.model,
        "llm_enabled": llm_needed,
    }
    _save_analysis_store()

    return {
        "analysis_id": analysis_id,
        "project_path": project_path,
        "edge_count": len(final_edges),
        "file_count": len(file_cache),
        "mode": effective_label_mode,
        "hierarchy": hierarchy,
    }


@app.post("/api/path-explanation")
async def path_explanation(req: PathExplanationRequest) -> dict[str, Any]:
    payload = ANALYSIS_STORE.get(req.analysis_id)
    if not payload:
        raise HTTPException(status_code=404, detail="Unknown analysis_id")

    edges = payload["edges"]
    file_cache = payload["file_cache"]
    brain = payload.get("brain")

    if not brain and payload.get("llm_enabled"):
        model = payload.get("llm_model") or "qwen2.5-coder:7b"
        brain = InferenceEngine(model=model)
        payload["brain"] = brain

    path_nodes, path_labels = _find_path(req.source, req.target, edges)
    if not path_nodes:
        raise HTTPException(status_code=404, detail="No dependency path found")

    if brain:
        explanation = brain.get_path_explanation(path_nodes, path_labels, file_cache)
    else:
        explanation = " -> ".join(path_labels) if path_labels else "direct dependency"

    return {
        "source": req.source,
        "target": req.target,
        "path": path_nodes,
        "labels": path_labels,
        "explanation": explanation,
    }


@app.post("/api/risk-analysis")
async def risk_analysis(req: RiskAnalysisRequest) -> dict[str, Any]:
    payload = ANALYSIS_STORE.get(req.analysis_id)
    if not payload:
        raise HTTPException(status_code=404, detail="Unknown analysis_id")

    risks = _risk_flags(payload, req.source, req.target)
    return {
        "analysis_id": req.analysis_id,
        "project_path": payload.get("project_path"),
        "risks": risks,
    }


@app.post("/api/search")
async def search(req: SearchRequest) -> dict[str, Any]:
    payload = ANALYSIS_STORE.get(req.analysis_id)
    if not payload:
        raise HTTPException(status_code=404, detail="Unknown analysis_id")
    if not req.query.strip():
        raise HTTPException(status_code=400, detail="query is required")

    results = _search_targets(payload, req.query)
    return {
        "analysis_id": req.analysis_id,
        "query": req.query,
        "matches": results,
    }
