# Architect-CLI

![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![Platform](https://img.shields.io/badge/platform-macOS%20%7C%20Linux-lightgrey)
![Renderer](https://img.shields.io/badge/renderer-vis--network-0ea5e9)
![Status](https://img.shields.io/badge/status-active-success)

Architect-CLI generates an interactive architecture map for your codebase.

It scans files, resolves cross-file dependencies, and produces a dark-theme HTML graph report powered by `vis-network`.

## Architecture

```mermaid
flowchart LR
  A[Project Path] --> B[Scanner\n(tree-sitter)]
  B --> C[Dependency Resolver\n(candidate extraction + matching)]
  C --> D{Label Mode}
  D -->|hints| E[Deterministic Labels]
  D -->|hybrid| F[Top-K LLM Labels + Hints]
  D -->|llm| G[LLM Labels for All Edges]
  F --> H[Edge Cache\n(.architect_cache.json)]
  G --> H
  E --> I[HTML Generator\n(vis-network UI)]
  H --> I
  I --> J[map.html\nLayered Graph + Filters]
```

Pipeline summary:

- Parse files and extract import/include dependencies.
- Resolve likely source-target file edges across the repository.
- Label edges using hints, hybrid budgeted LLM, or full LLM mode.
- Render an interactive layered graph report as `map.html`.

## Why Use It

- Works on large repositories with fast fallback modes.
- Supports LLM-enhanced relationship labels (via local Ollama).
- Includes layered graph exploration:
  - top-level groups first
  - click to expand/collapse sub-dependencies
- Ships with filters for dense graphs:
  - group filtering
  - focus mode and neighborhood depth
  - visible edge cap

## Requirements

- Python `3.10+`
- `pip`
- Optional for LLM labeling:
  - [Ollama](https://ollama.com/) running locally on `http://localhost:11434`
  - a pulled model (default: `qwen2.5-coder:7b`)

## Installation

```bash
git clone https://github.com/codekshitij/Architect-CLI.git
cd Architect-CLI

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Optional Ollama setup for detailed labels:

```bash
ollama serve
ollama pull qwen2.5-coder:7b
```

## Quick Start

```bash
python main.py --path ./my-project --output map.html
```

Open `map.html` in your browser if not opened automatically.

## Recommended Modes

Fastest (large repos, no LLM calls):

```bash
python main.py --path ./big-repo --label-mode hints --no-open
```

Balanced quality/speed (budgeted LLM labels):

```bash
python main.py --path ./big-repo --label-mode hybrid --no-open
```

Full LLM labeling for all edges (slowest):

```bash
python main.py --path ./my-project --label-mode llm
```

## CLI Examples

Focus on a file area:

```bash
python main.py --path ./my-project --focus main.py
```

Limit graph size:

```bash
python main.py --path ./my-project --max-edges 400
```

Use workers and persistent cache:

```bash
python main.py --path ./my-project --workers 8 --cache-file .architect_cache.json
```

Disable browser auto-open:

```bash
python main.py --path ./my-project --no-open
```

## Important Flags

- `--path` path to project root (required)
- `--output` output HTML path (default: `map.html`)
- `--model` Ollama model name (default: `qwen2.5-coder:7b`)
- `--label-mode` `hints | hybrid | llm` (default: `hybrid`)
- `--llm-max-edges` max LLM-labeled edges in hybrid mode
- `--max-targets-per-dep` cap noisy stem matches
- `--workers` thread count (`0` = auto)
- `--cache-file` cache JSON path
- `--no-cache` disable cache reads/writes
- `--focus` restrict graph to a filename/path fragment
- `--max-edges` trim analyzed edge count

## Graph UI Tips

- Start in layered mode (enabled by default):
  - see top-level groups first
  - click group nodes to expand
- Use `Visible Edges` slider before enabling force layout on huge graphs.
- Use `Focus mode` + depth `1` or `2` for local reasoning.
- Use `Collapse All` to quickly reset visual complexity.

## Notes

- In hybrid mode, `--llm-max-edges` auto-scales by graph size when not set.
- `--no-cache` can be significantly slower for repeated LLM runs.
- Ignored directories include `.git`, `node_modules`, `venv`, and `__pycache__`.

## Troubleshooting

### 1. `venv` activation fails

If `source venv/bin/activate` fails, recreate it:

```bash
rm -rf venv
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. LLM labeling is slow on big repos

Use fast or balanced modes:

```bash
python main.py --path ./big-repo --label-mode hints --no-open
python main.py --path ./big-repo --label-mode hybrid --no-open
```

Tips:

- Avoid `--no-cache` for repeated LLM runs.
- Reduce LLM work with `--llm-max-edges 20` (or similar).
- Use layered mode and edge cap in the UI for readability.

### 3. Ollama connection errors

Ensure Ollama is running and the model exists:

```bash
ollama serve
ollama list
ollama pull qwen2.5-coder:7b
```

If needed, switch model:

```bash
python main.py --path ./my-project --model qwen2.5-coder:7b
```

### 4. Output HTML not opening automatically

Generate without auto-open and open manually:

```bash
python main.py --path ./my-project --output map.html --no-open
```

Then open `map.html` in your browser.

### 5. Graph looks too crowded

Use these together:

- Layered mode enabled (default)
- `Visible Edges` slider
- `Group Filter`
- `Focus mode` with depth `1` or `2`
- `Collapse All` to reset view

## Development

Run tests:

```bash
python -m unittest discover -s tests -q
```

Run a quick syntax check:

```bash
python -m py_compile main.py architect/brain.py architect/visualizer.py
```
