import ast
import unittest
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SOURCE_PATH = ROOT / "mod" / "derelict_baseline_probe.py"


def load_helpers():
    source = SOURCE_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    selected = [
        node for node in tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name in {"_normalize_universe_address", "_root_seed_effective_state"}
    ]
    namespace = {"Any": Any}
    exec(compile(ast.Module(body=selected, type_ignores=[]), str(SOURCE_PATH), "exec"), namespace)
    return source, namespace


class SystemScopedRootCaptureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source, cls.helpers = load_helpers()
        cls.tree = ast.parse(cls.source)
        cls.probe = next(
            node for node in cls.tree.body
            if isinstance(node, ast.ClassDef) and node.name == "DerelictBaselineProbe"
        )

    def method(self, name):
        return next(node for node in self.probe.body if isinstance(node, ast.FunctionDef) and node.name == name)

    def test_address_normalization_rejects_transition_gaps(self):
        normalize = self.helpers["_normalize_universe_address"]
        self.assertEqual(normalize("0xf"), "000000000000000F")
        self.assertIsNone(normalize("0000000000000000"))
        self.assertIsNone(normalize(None))
        self.assertIsNone(normalize("not-an-address"))

    def test_seed_raw_value_is_separate_from_effective_use(self):
        state = self.helpers["_root_seed_effective_state"]
        disabled = state({"seed_hex": "F000000000000000", "use_seed_value": False})
        self.assertEqual(disabled["root_seed_state"], "disabled")
        self.assertIsNone(disabled["root_seed_effective_hex"])
        zero = state({"seed_hex": "0000000000000000", "use_seed_value": True})
        self.assertEqual(zero["root_seed_state"], "enabled_zero")
        self.assertEqual(zero["root_seed_effective_hex"], "0000000000000000")
        active = state({"seed_hex": "0000000F00000000", "use_seed_value": True})
        self.assertEqual(active["root_seed_state"], "enabled")
        self.assertEqual(active["root_seed_effective_hex"], "0000000F00000000")
        sentinel = state({"seed_hex": "FFFFFFFFFFFFFFFF", "use_seed_value": True})
        self.assertEqual(sentinel["root_seed_state"], "all_ones_sentinel")

    def test_system_transition_closes_session_and_clears_live_seed_buffers(self):
        method = ast.unparse(self.method("_observe_system_scope"))
        for required in (
            'reason="system_changed"',
            "self._pre_session_trace.clear()",
            "self._pre_session_dungeon_seeds.clear()",
            "self._pre_session_poi_candidates.clear()",
            "self._last_exact_root_caller = None",
            "self._last_generation_room_summary = None",
        ):
            self.assertIn(required, method)

    def test_poll_and_root_capture_both_observe_system_address(self):
        tick = ast.unparse(self.method("_tick"))
        root_hook = ast.unparse(self.method("_trace_resource_add"))
        self.assertIn("_observe_system_scope", tick)
        self.assertIn('source="root_resource"', root_hook)

    def test_root_seed_summary_exposes_raw_and_effective_fields(self):
        self.assertIn('"last_dungeon_root_seed_raw_hex"', self.source)
        self.assertIn('"dungeon_root_seed_effective_candidates"', self.source)
        self.assertIn('"last_seed_use_seed_value"', self.source)

    def test_root_dispatch_snapshot_is_hidden_when_it_belongs_to_another_system(self):
        method = ast.unparse(self.method("_root_dispatch_capture_payload"))
        self.assertIn("_normalize_universe_address", method)
        self.assertIn("captured_ua != self._current_universe_address_hex", method)


if __name__ == "__main__":
    unittest.main()
