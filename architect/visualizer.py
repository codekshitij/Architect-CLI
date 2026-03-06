import os
import re
from jinja2 import Template

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <script src="https://cdn.jsdelivr.net/npm/mermaid/dist/mermaid.min.js"></script>
    <style>
        body { background: #0d1117; color: white; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; display: flex; flex-direction: column; align-items: center; padding: 20px; }
        .mermaid { background: #161b22; padding: 30px; border-radius: 12px; width: 95%; box-shadow: 0 4px 20px rgba(0,0,0,0.5); }
        h1 { margin-bottom: 10px; color: #58a6ff; }
    </style>
</head>
<body>
    <h1>Architect-CLI: Repository Map</h1>
    <div class="mermaid">
        graph TD
        {% for node in nodes %}
        {{ node.id }}[{{ node.name }}]
        {% endfor %}

        {% for edge in edges %}
        {{ edge.source_id }} -->|{{ edge.label }}| {{ edge.target_id }}
        {% endfor %}
    </div>
    <script>
        mermaid.initialize({
            startOnLoad: true, 
            theme: 'dark',
            securityLevel: 'loose',
            flowchart: { useMaxWidth: true, htmlLabels: true, curve: 'basis' }
        });
    </script>
</body>
</html>
"""

def generate_html(edges, output_path):
    template = Template(HTML_TEMPLATE)
    
    unique_files = set()
    for s, t, _ in edges:
        unique_files.add(s)
        unique_files.add(t)
    
    # Create Safe IDs (e.g., "pipeline_py")
    def make_id(path):
        name = os.path.basename(path)
        return re.sub(r'[^a-zA-Z0-9]', '_', name)

    nodes = [{"id": make_id(f), "name": os.path.basename(f)} for f in unique_files]
    
    clean_edges = []
    for s, t, l in edges:
        # Strict sanitization for the label
        # Remove anything that isn't a basic character, space, or standard punctuation
        safe_label = str(l).replace('"', "'").replace("\n", " ").replace("|", " ")
        safe_label = re.sub(r'[^a-zA-Z0-9\s\.\,\-\?\!\']', '', safe_label)
        
        clean_edges.append({
            "source_id": make_id(s),
            "target_id": make_id(t),
            "label": safe_label.strip()
        })
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(template.render(nodes=nodes, edges=clean_edges))