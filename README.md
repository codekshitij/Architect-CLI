# Architect v4

Architect v4 is a FastAPI backend plus a React frontend for interactive software architecture analysis.

## Stack

- Backend: FastAPI + tree-sitter scanning + optional Ollama-based labeling
- Frontend: React + Vite + Tailwind + Sigma graph rendering
- Dev workflow: one command local startup via `make dev`

## Run Locally

```bash
make dev
```

This starts:

- Backend: `http://127.0.0.1:8000`
- Frontend: `http://127.0.0.1:5173`

## Backend Only

```bash
uvicorn architect.api_server:app --host 0.0.0.0 --port 8000
```

Health check:

```bash
curl http://127.0.0.1:8000/api/health
```

Analyze a repo:

```bash
curl -X POST http://127.0.0.1:8000/api/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "path": "/Users/kshitijmishra/tinygrad",
    "no_llm": true,
    "label_mode": "hints"
  }'
```

## Frontend Only

```bash
cd frontend
npm install
npm run dev
```

## Optional LLM Setup

For LLM relationship labels, run Ollama locally and pull a model:

```bash
ollama serve
ollama pull qwen2.5-coder:7b
```

## API Endpoints

- `GET /api/health`
- `POST /api/analyze`
- `POST /api/path-explanation`
- `POST /api/risk-analysis`
- `POST /api/search`

## Notes

- Analysis results are persisted in `.architect_analysis_store.json`.
- LLM edge labels are cached in `.architect_cache.json` unless disabled.

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
