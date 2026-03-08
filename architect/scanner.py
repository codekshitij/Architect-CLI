import os
from tree_sitter_language_pack import get_parser, get_language
from tree_sitter import QueryCursor


class UniversalScanner:
    def __init__(self):
        self.configs = {
            ".py": {
                "lang": "python",
                "deps": "(import_from_statement) @i (import_statement) @i",
                "symbols": """
                    (class_definition name: (identifier) @class.name)
                    (function_definition name: (identifier) @func.name)
                """,
            },
            ".cpp": {
                "lang": "cpp",
                "deps": "(preproc_include) @i",
                "symbols": """
                    (class_specifier name: (type_identifier) @class.name)
                    (struct_specifier name: (type_identifier) @class.name)
                    (function_definition declarator: (function_declarator declarator: (identifier) @func.name))
                """,
            },
            ".hpp": {
                "lang": "cpp",
                "deps": "(preproc_include) @i",
                "symbols": """
                    (class_specifier name: (type_identifier) @class.name)
                    (struct_specifier name: (type_identifier) @class.name)
                    (function_definition declarator: (function_declarator declarator: (identifier) @func.name))
                """,
            },
            ".js": ("javascript", "(import_statement) @i"),
            ".ts": ("typescript", "(import_statement) @i")
        }

    def scan(self, file_path):
        ext = os.path.splitext(file_path)[1]
        if ext not in self.configs:
            return None, [], {"classes": [], "functions": []}

        config = self.configs[ext]
        if isinstance(config, tuple):
            lang_name, query_str = config
            symbol_query_str = ""
        else:
            lang_name = config["lang"]
            query_str = config["deps"]
            symbol_query_str = config.get("symbols", "")

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

        symbols = {"classes": [], "functions": []}
        if symbol_query_str:
            symbol_query = lang.query(symbol_query_str)
            symbol_cursor = QueryCursor(symbol_query)
            symbol_captures = symbol_cursor.captures(tree.root_node)

            class_nodes = symbol_captures.get("class.name", [])
            func_nodes = symbol_captures.get("func.name", [])

            classes = sorted({node.text.decode("utf8").strip() for node in class_nodes if node.text})
            functions = sorted({node.text.decode("utf8").strip() for node in func_nodes if node.text})
            symbols = {"classes": classes, "functions": functions}

        return code, list(set(deps)), symbols