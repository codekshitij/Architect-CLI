# Architect-CLI

Local AI Codebase Visualizer

Renderer: Interactive dark-theme graph report powered by `vis-network`.

## Installation

1. Clone the repository
2. Create a virtual environment: `python -m venv venv`
3. Activate the environment: `source venv/bin/activate`
4. Install dependencies: `pip install -r requirements.txt`

## Usage

```bash
python main.py --path ./my-project --model qwen2.5-coder:7b --output map.html
```

Quick run without LLM labeling:

```bash
python main.py --path ./my-project --no-llm --output map.html --no-open
```

Focus on a file and limit analysis size:

```bash
python main.py --path ./my-project --focus main.py --max-edges 200
```

Use parallel workers and persistent label cache:

```bash
python main.py --path ./my-project --workers 8 --cache-file .architect_cache.json
```

Disable cache when debugging:

```bash
python main.py --path ./my-project --no-cache --workers 1
```

Large repository fast mode (recommended for 5k+ relationships):

```bash
python main.py --path ./big-repo --label-mode hints --no-open
```

Balanced quality/speed mode for large repos:

```bash
python main.py --path ./big-repo --label-mode hybrid --no-open
```

Notes:

- `--llm-max-edges` defaults to auto-scaling by graph size in hybrid mode.
- `--no-cache` can significantly increase runtime when LLM labeling is enabled.
