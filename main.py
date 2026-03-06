import os
import argparse
import webbrowser
from architect.scanner import UniversalScanner
from architect.brain import InferenceEngine
from architect.visualizer import generate_html

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--path", required=True)
    parser.add_argument("--model", default="qwen2.5-coder:7b")
    parser.add_argument("--focus", help="Only map files connected to this filename (e.g., main.cpp)")
    args = parser.parse_args()

    scanner = UniversalScanner()
    brain = InferenceEngine(model=args.model)
    edges = []
    file_cache = {}
    
    # 1. Build a master list of ALL files in the project
    all_files = {}
    print(f"🔍 Scanning all directories in {args.path}...")
    for root, _, files in os.walk(args.path):
        if any(x in root for x in [".git", "node_modules", "venv"]): continue
        for f in files:
            full_path = os.path.join(root, f)
            all_files[f] = full_path

    # 2. Extract raw dependencies from every file
    raw_deps = {}
    for filename, full_path in all_files.items():
        code, deps = scanner.scan(full_path)
        if code:
            file_cache[full_path] = code
            raw_deps[full_path] = deps

    # 3. Resolve dependencies globally
    for source_path, deps in raw_deps.items():
        source_name = os.path.basename(source_path)
        for d in deps:
            # Check if the extracted dependency matches any file in the whole repo
            for target_name, target_path in all_files.items():
                # Remove extension from target_name for looser matching (e.g. 'utils' matches 'utils.py')
                target_base = os.path.splitext(target_name)[0]
                if target_base in d and target_name != source_name:
                    edges.append((source_path, target_path))

    # Apply Focus Filter
    if args.focus:
        edges = [(s, t) for s, t in edges if args.focus in s or args.focus in t]

    # Remove duplicates
    edges = list(set(edges))

    print(f"🧠 Analyzing {len(edges)} relationships with {args.model}...")
    final_edges = []
    for s, t in edges:
        label = brain.get_relationship(s, file_cache[s], t, file_cache.get(t, ""))
        final_edges.append((s, t, label))

    # 4. Generate and Open
    output_path = os.path.abspath("map.html")
    generate_html(final_edges, output_path)
    
    print(f"✅ Done! Opening {output_path}")
    webbrowser.open("file://" + output_path)

if __name__ == "__main__":
    main()