import hashlib
import json
import os
import re
from collections import defaultdict, deque
from concurrent.futures import ThreadPoolExecutor, as_completed

IGNORED_DIRS = {".git", "node_modules", "venv", "__pycache__", "frontend/node_modules"}


def discover_files(root_path: str) -> list[str]:
    all_paths: list[str] = []
    for root, dirnames, files in os.walk(root_path):
        dirnames[:] = [d for d in dirnames if d not in IGNORED_DIRS]
        for name in files:
            all_paths.append(os.path.join(root, name))
    return all_paths


def build_indexes(paths: list[str]) -> tuple[dict[str, set[str]], dict[str, set[str]]]:
    by_filename: dict[str, set[str]] = {}
    by_stem: dict[str, set[str]] = {}
    for path in paths:
        filename = os.path.basename(path)
        stem = os.path.splitext(filename)[0]
        by_filename.setdefault(filename, set()).add(path)
        by_stem.setdefault(stem, set()).add(path)
    return by_filename, by_stem


def extract_dependency_candidates(dep_text: str) -> list[str]:
    text = dep_text.strip()
    if not text:
        return []

    candidates: set[str] = set()
    for value in re.findall(r"['\"]([^'\"]+)['\"]", text):
        candidates.add(value)

    if text.startswith("from "):
        parts = text.split()
        if len(parts) >= 2:
            candidates.add(parts[1])
    elif text.startswith("import "):
        imports = text.replace("import ", "", 1)
        for item in imports.split(","):
            name = item.strip().split(" as ")[0].strip()
            if name:
                candidates.add(name)
    elif text.startswith("#include"):
        include_value = text.replace("#include", "", 1).strip(" <>\"")
        if include_value:
            candidates.add(include_value)

    if not candidates:
        candidates.add(text)

    normalized: set[str] = set()
    for value in candidates:
        value = value.strip()
        if not value:
            continue
        normalized.add(value)
        normalized.add(os.path.basename(value))
        normalized.add(os.path.splitext(os.path.basename(value))[0])
        normalized.add(value.split("/")[-1])
        normalized.add(value.split(".")[-1])

    return [c for c in normalized if c]


def _resolve_candidate_targets(
    candidate: str,
    by_filename: dict[str, set[str]],
    by_stem: dict[str, set[str]],
    max_targets_per_dep: int,
) -> set[str]:
    direct = set(by_filename.get(candidate, set()))
    if direct:
        return direct

    if len(candidate) < 3:
        return set()

    stem_matches = set(by_stem.get(candidate, set()))
    if max_targets_per_dep > 0 and len(stem_matches) > max_targets_per_dep:
        return set()
    return stem_matches


def relationship_hint(dep_text: str, target_path: str) -> str:
    text = dep_text.strip()
    target_name = os.path.basename(target_path)
    target_stem = os.path.splitext(target_name)[0]

    if text.startswith("#include"):
        include_value = text.replace("#include", "", 1).strip(" <>\"")
        include_value = os.path.basename(include_value) if include_value else target_name
        return f"includes {include_value}"

    if text.startswith("from "):
        parts = text.split()
        if len(parts) >= 2:
            module = parts[1].split(".")[-1]
            return f"imports from {module}"
        return f"imports from {target_stem}"

    if text.startswith("import "):
        imports = text.replace("import ", "", 1)
        names = []
        for item in imports.split(","):
            name = item.strip().split(" as ")[0].strip()
            if name:
                names.append(name.split(".")[-1])
        for name in names:
            if name == target_stem:
                return f"imports {name}"
        if names:
            return f"imports {names[0]}"
        return f"imports {target_stem}"

    quoted = re.findall(r"['\"]([^'\"]+)['\"]", text)
    if quoted:
        quoted_target = os.path.basename(quoted[0])
        quoted_stem = os.path.splitext(quoted_target)[0]
        return f"imports {quoted_stem}"

    return f"uses {target_stem}"


def resolve_edges(
    raw_deps: dict[str, list[str]],
    by_filename: dict[str, set[str]],
    by_stem: dict[str, set[str]],
    max_targets_per_dep: int = 8,
) -> tuple[list[tuple[str, str]], dict[tuple[str, str], str]]:
    edge_hints: dict[tuple[str, str], str] = {}

    def _track_edge(source_path: str, target_path: str, dep_text: str) -> None:
        if source_path == target_path:
            return
        edge = (source_path, target_path)
        hint = relationship_hint(dep_text, target_path)
        existing = edge_hints.get(edge)
        if existing is None or (existing.startswith("uses ") and not hint.startswith("uses ")):
            edge_hints[edge] = hint

    for source_path, deps in raw_deps.items():
        for dep in deps:
            for candidate in extract_dependency_candidates(dep):
                targets = _resolve_candidate_targets(candidate, by_filename, by_stem, max_targets_per_dep)
                for target_path in targets:
                    _track_edge(source_path, target_path, dep)

    edges = sorted(edge_hints.keys())
    return edges, edge_hints


def apply_focus(
    edges: list[tuple[str, str]],
    edge_hints: dict[tuple[str, str], str],
    focus: str | None,
) -> tuple[list[tuple[str, str]], dict[tuple[str, str], str]]:
    if not focus:
        return edges, edge_hints
    filtered_edges = [(s, t) for s, t in edges if focus in s or focus in t]
    filtered_hints = {edge: edge_hints[edge] for edge in filtered_edges if edge in edge_hints}
    return filtered_edges, filtered_hints


def _code_hash(code: str) -> str:
    return hashlib.sha256(code.encode("utf-8", errors="ignore")).hexdigest()


def make_cache_key(
    model: str,
    source_path: str,
    source_code: str,
    target_path: str,
    target_code: str,
    cache_salt: str = "",
    hint: str = "",
) -> str:
    payload = "\n".join(
        [
            model,
            cache_salt,
            source_path,
            _code_hash(source_code),
            target_path,
            _code_hash(target_code),
            hint,
        ]
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def load_cache(cache_file: str) -> dict[str, str]:
    if not os.path.exists(cache_file):
        return {}
    try:
        with open(cache_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            return data
    except (OSError, json.JSONDecodeError):
        pass
    return {}


def save_cache(cache_file: str, cache_data: dict[str, str]) -> None:
    cache_dir = os.path.dirname(cache_file)
    if cache_dir:
        os.makedirs(cache_dir, exist_ok=True)
    with open(cache_file, "w", encoding="utf-8") as f:
        json.dump(cache_data, f, indent=2, sort_keys=True)


def _scan_file(scanner, full_path: str):
    code, deps, symbols = scanner.scan(full_path)
    return full_path, code, deps, symbols


def scan_files(scanner, all_paths: list[str], workers: int):
    raw_deps: dict[str, list[str]] = {}
    file_cache: dict[str, str] = {}
    symbol_index: dict[str, dict[str, list[str]]] = {}

    if workers == 1:
        for full_path in all_paths:
            _, code, deps, symbols = _scan_file(scanner, full_path)
            if code:
                file_cache[full_path] = code
                raw_deps[full_path] = deps
                symbol_index[full_path] = symbols
        return file_cache, raw_deps, symbol_index

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [executor.submit(_scan_file, scanner, full_path) for full_path in all_paths]
        for future in as_completed(futures):
            full_path, code, deps, symbols = future.result()
            if code:
                file_cache[full_path] = code
                raw_deps[full_path] = deps
                symbol_index[full_path] = symbols

    return file_cache, raw_deps, symbol_index


def _top_level_group(path: str, common_root: str) -> str:
    if not common_root:
        return "root"
    rel = os.path.relpath(path, common_root)
    parts = rel.split(os.sep)
    if len(parts) <= 1:
        return "root"
    return parts[0]


def _stable_id(prefix: str, raw_value: str) -> str:
    digest = hashlib.md5(raw_value.encode("utf-8")).hexdigest()[:10]
    safe = re.sub(r"[^a-zA-Z0-9]", "_", raw_value)[:36]
    return f"{prefix}_{safe}_{digest}"


def build_hierarchical_graph(labeled_edges, symbol_index):
    file_paths = sorted({s for s, _, _ in labeled_edges} | {t for _, t, _ in labeled_edges})
    common_root = os.path.commonpath(file_paths) if file_paths else ""

    containers: dict[str, dict] = {}
    aggregate: dict[tuple[str, str], dict] = {}
    file_edges: list[dict] = []

    for path in file_paths:
        group = _top_level_group(path, common_root)
        rel_path = os.path.relpath(path, common_root) if common_root else os.path.basename(path)
        file_node = {
            "id": _stable_id("file", path),
            "label": os.path.basename(path),
            "path": rel_path,
            "full_path": path,
            "type": "file",
            "children": [],
        }

        symbols = symbol_index.get(path, {"classes": [], "functions": []})
        for class_name in symbols.get("classes", []):
            file_node["children"].append(
                {
                    "id": _stable_id("class", f"{path}:{class_name}"),
                    "label": class_name,
                    "type": "class",
                }
            )
        for fn_name in symbols.get("functions", []):
            file_node["children"].append(
                {
                    "id": _stable_id("func", f"{path}:{fn_name}"),
                    "label": fn_name,
                    "type": "function",
                }
            )

        if group not in containers:
            containers[group] = {
                "id": _stable_id("container", group),
                "label": group,
                "type": "container",
                "children": [],
            }
        containers[group]["children"].append(file_node)

    for source_path, target_path, label in labeled_edges:
        src_group = _top_level_group(source_path, common_root)
        dst_group = _top_level_group(target_path, common_root)

        key = (src_group, dst_group)
        entry = aggregate.setdefault(
            key,
            {
                "id": _stable_id("agg", f"{src_group}->{dst_group}"),
                "source": src_group,
                "target": dst_group,
                "weight": 0,
                "labels": defaultdict(int),
            },
        )
        entry["weight"] += 1
        entry["labels"][label] += 1

        file_edges.append(
            {
                "id": _stable_id("edge", f"{source_path}->{target_path}"),
                "source": source_path,
                "target": target_path,
                "label": label,
                "source_group": src_group,
                "target_group": dst_group,
            }
        )

    aggregate_edges = []
    for value in aggregate.values():
        top_labels = sorted(value["labels"].items(), key=lambda item: item[1], reverse=True)
        aggregate_edges.append(
            {
                "id": value["id"],
                "source": value["source"],
                "target": value["target"],
                "weight": value["weight"],
                "top_label": top_labels[0][0] if top_labels else "dependency",
            }
        )

    return {
        "system": {
            "id": "system",
            "label": "Architect System",
            "type": "system",
            "children": [containers[name] for name in sorted(containers.keys())],
        },
        "aggregate_edges": sorted(aggregate_edges, key=lambda item: (item["source"], item["target"])),
        "file_edges": file_edges,
    }


def _find_path(source_path: str, target_path: str, edges):
    adjacency: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for edge in edges:
        adjacency[edge[0]].append((edge[1], edge[2]))

    queue = deque([(source_path, [source_path], [])])
    visited = {source_path}
    while queue:
        node, path_nodes, path_labels = queue.popleft()
        if node == target_path:
            return path_nodes, path_labels
        for neighbor, label in adjacency.get(node, []):
            if neighbor in visited:
                continue
            visited.add(neighbor)
            queue.append((neighbor, path_nodes + [neighbor], path_labels + [label]))
    return [], []


def _choose_llm_edges(edges, edge_hints, llm_max_edges: int) -> set[tuple[str, str]]:
    if llm_max_edges <= 0:
        return set()

    degree: dict[str, int] = {}
    for source_path, target_path in edges:
        degree[source_path] = degree.get(source_path, 0) + 1
        degree[target_path] = degree.get(target_path, 0) + 1

    def score(edge):
        source_path, target_path = edge
        hint = edge_hints.get(edge, "")
        ambiguity = 1 if hint.startswith("uses ") else 0
        centrality = degree.get(source_path, 0) + degree.get(target_path, 0)
        return (ambiguity, centrality)

    ranked = sorted(edges, key=score, reverse=True)
    return set(ranked[:llm_max_edges])


def label_edges(
    edges,
    edge_hints,
    file_cache,
    brain,
    no_llm,
    workers,
    use_cache,
    cache_data,
    label_mode="llm",
    llm_max_edges=0,
):
    if no_llm or label_mode == "hints":
        return [(s, t, edge_hints.get((s, t), "dependency")) for s, t in edges]

    labels_by_edge: dict[tuple[str, str], str] = {}
    llm_edges = _choose_llm_edges(edges, edge_hints, llm_max_edges) if label_mode == "hybrid" else set(edges)

    def _label_one(source_path, target_path, hint):
        source_code = file_cache.get(source_path, "")
        target_code = file_cache.get(target_path, "")
        label = brain.get_relationship(source_path, source_code, target_path, target_code, hint)
        return source_path, target_path, source_code, target_code, label

    unresolved = []
    cache_salt = getattr(brain, "cache_salt", "")
    for source_path, target_path in edges:
        hint = edge_hints.get((source_path, target_path), "")

        if (source_path, target_path) not in llm_edges:
            labels_by_edge[(source_path, target_path)] = hint or "dependency"
            continue

        source_code = file_cache.get(source_path, "")
        target_code = file_cache.get(target_path, "")
        cache_key = make_cache_key(
            brain.model,
            source_path,
            source_code,
            target_path,
            target_code,
            cache_salt,
            hint,
        )
        if use_cache and cache_key in cache_data:
            labels_by_edge[(source_path, target_path)] = cache_data[cache_key]
        else:
            unresolved.append((source_path, target_path, cache_key, hint))

    if workers == 1:
        for source_path, target_path, cache_key, hint in unresolved:
            _, _, _, _, label = _label_one(source_path, target_path, hint)
            labels_by_edge[(source_path, target_path)] = label
            if use_cache:
                cache_data[cache_key] = label
        return [(s, t, labels_by_edge.get((s, t), edge_hints.get((s, t), "dependency"))) for s, t in edges]

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {}
        for source_path, target_path, cache_key, hint in unresolved:
            future = executor.submit(_label_one, source_path, target_path, hint)
            futures[future] = cache_key

        for future in as_completed(futures):
            source_path, target_path, _, _, label = future.result()
            labels_by_edge[(source_path, target_path)] = label
            if use_cache:
                cache_data[futures[future]] = label

    return [(s, t, labels_by_edge.get((s, t), edge_hints.get((s, t), "dependency"))) for s, t in edges]


def resolve_workers(requested_workers: int) -> int:
    if requested_workers > 0:
        return requested_workers
    return min(32, (os.cpu_count() or 4) + 4)


def resolve_llm_budget(label_mode: str, requested_llm_max_edges: int | None, edge_count: int) -> int:
    if label_mode != "hybrid":
        return requested_llm_max_edges if requested_llm_max_edges is not None else 0

    if requested_llm_max_edges is not None:
        return requested_llm_max_edges

    if edge_count >= 8000:
        return 15
    if edge_count >= 5000:
        return 20
    if edge_count >= 2500:
        return 35
    if edge_count >= 1200:
        return 70
    return 140
