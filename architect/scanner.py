import os
from tree_sitter_language_pack import get_parser, get_language
from tree_sitter import QueryCursor

class UniversalScanner:
    def __init__(self):
        self.configs = {
            ".py": ("python", "(import_from_statement) @i (import_statement) @i"),
            ".cpp": ("cpp", "(preproc_include) @i"),
            ".hpp": ("cpp", "(preproc_include) @i"),
            ".js": ("javascript", "(import_statement) @i"),
            ".ts": ("typescript", "(import_statement) @i")
        }

    def scan(self, file_path):
        ext = os.path.splitext(file_path)[1]
        if ext not in self.configs: return None, []
        
        lang_name, query_str = self.configs[ext]
        parser = get_parser(lang_name)
        lang = get_language(lang_name)
        
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            code = f.read()
            
        tree = parser.parse(bytes(code, "utf8"))
        query = lang.query(query_str)
        
        # New API requirement
        cursor = QueryCursor(query)
        captures = cursor.captures(tree.root_node)
        
        deps = []
        for nodes in captures.values():
            for node in nodes:
                deps.append(node.text.decode("utf8").strip('"<> \n'))
                
        return code, list(set(deps))