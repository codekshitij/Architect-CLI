import tempfile
import unittest
from pathlib import Path

import main


class FakeBrain:
    def __init__(self, model="fake-model"):
        self.model = model
        self.calls = 0

    def get_relationship(self, source_path, source_code, target_path, target_code, hint=""):
        self.calls += 1
        return f"rel:{Path(source_path).name}->{Path(target_path).name}"


class MainPipelineTests(unittest.TestCase):
    def test_resolve_edges_handles_duplicate_basenames(self):
        source = "/repo/src/app.py"
        util_a = "/repo/src/util.py"
        util_b = "/repo/tests/util.py"

        raw_deps = {source: ["import util"]}
        by_filename = {"app.py": {source}, "util.py": {util_a, util_b}}
        by_stem = {"app": {source}, "util": {util_a, util_b}}

        edges, hints = main.resolve_edges(raw_deps, by_filename, by_stem)

        self.assertIn((source, util_a), edges)
        self.assertIn((source, util_b), edges)
        self.assertEqual(len(edges), 2)
        self.assertEqual(hints[(source, util_a)], "imports util")

    def test_make_cache_key_changes_with_code(self):
        key_1 = main.make_cache_key("m", "a.py", "print(1)", "b.py", "print(2)")
        key_2 = main.make_cache_key("m", "a.py", "print(99)", "b.py", "print(2)")

        self.assertNotEqual(key_1, key_2)

    def test_save_and_load_cache_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            cache_file = str(Path(tmp_dir) / "cache" / "labels.json")
            payload = {"k1": "label1", "k2": "label2"}

            main.save_cache(cache_file, payload)
            loaded = main.load_cache(cache_file)

            self.assertEqual(payload, loaded)

    def test_label_edges_uses_cache_without_brain_call(self):
        brain = FakeBrain()
        source = "/repo/src/a.py"
        target = "/repo/src/b.py"
        file_cache = {source: "import b", target: "def b(): pass"}

        key = main.make_cache_key(
            brain.model,
            source,
            file_cache[source],
            target,
            file_cache[target],
            hint="imports b",
        )
        cache_data = {key: "cached-label"}

        labeled = main.label_edges(
            edges=[(source, target)],
            edge_hints={(source, target): "imports b"},
            file_cache=file_cache,
            brain=brain,
            no_llm=False,
            workers=1,
            use_cache=True,
            cache_data=cache_data,
        )

        self.assertEqual(labeled, [(source, target, "cached-label")])
        self.assertEqual(brain.calls, 0)

    def test_label_edges_populates_cache_on_miss(self):
        brain = FakeBrain()
        source = "/repo/src/a.py"
        target = "/repo/src/b.py"
        file_cache = {source: "import b", target: "def b(): pass"}
        cache_data = {}

        labeled = main.label_edges(
            edges=[(source, target)],
            edge_hints={(source, target): "uses b"},
            file_cache=file_cache,
            brain=brain,
            no_llm=False,
            workers=1,
            use_cache=True,
            cache_data=cache_data,
        )

        self.assertEqual(len(labeled), 1)
        self.assertEqual(brain.calls, 1)

        key = main.make_cache_key(
            brain.model,
            source,
            file_cache[source],
            target,
            file_cache[target],
            hint="uses b",
        )
        self.assertIn(key, cache_data)

    def test_label_edges_no_llm_short_circuit(self):
        brain = FakeBrain()
        source = "/repo/src/a.py"
        target = "/repo/src/b.py"

        labeled = main.label_edges(
            edges=[(source, target)],
            edge_hints={(source, target): "imports b"},
            file_cache={},
            brain=brain,
            no_llm=True,
            workers=4,
            use_cache=False,
            cache_data={},
        )

        self.assertEqual(labeled, [(source, target, "imports b")])
        self.assertEqual(brain.calls, 0)


if __name__ == "__main__":
    unittest.main()
