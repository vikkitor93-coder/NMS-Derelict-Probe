"""Check caller-edge classification without importing the injected NMS probe."""

import ast
import unittest
from pathlib import Path
from types import SimpleNamespace


PROBE = Path(__file__).resolve().parents[1] / "mod" / "derelict_baseline_probe.py"
TREE = ast.parse(PROBE.read_text(encoding="utf-8"))
FUNCTIONS = [
    node for node in TREE.body
    if isinstance(node, ast.FunctionDef)
    and node.name in {"_classify_caller_bytes", "_observed_hook_rva"}
]
MODULE = ast.Module(body=FUNCTIONS, type_ignores=[])
SCOPE = {
    "hook_manager": SimpleNamespace(hooks={}),
    "ctypes": SimpleNamespace(c_void_p=int, windll=SimpleNamespace(kernel32=SimpleNamespace(GetModuleHandleW=lambda _: 0x140000000))),
}
exec(compile(MODULE, str(PROBE), "exec"), SCOPE)
classify = SCOPE["_classify_caller_bytes"]
observed_hook_rva = SCOPE["_observed_hook_rva"]


class ProbeHookIdentityTests(unittest.TestCase):
    def test_current_recursive_edge(self):
        return_rva = 0x0063A773
        hook_rva = 0x0063A6D0
        displacement = hook_rva - return_rva
        raw = b"\xE8" + displacement.to_bytes(4, "little", signed=True)
        self.assertEqual(classify(raw, return_rva, hook_rva), (True, False))
        self.assertEqual(classify(raw, return_rva, 0x006369F0), (False, False))

    def test_current_indirect_caller(self):
        self.assertEqual(
            classify(b"\x48\x8B\xFF\x52\x10", 0x02C0860A, 0x0063A6D0),
            (False, True),
        )

    def test_missing_bytes_cannot_prove_edge(self):
        self.assertEqual(classify(None, 0x02C0860A, 0x0063A6D0), (False, False))
        self.assertEqual(classify(b"\xFF\x52\x10", 0x02C0860A, 0x0063A6D0), (False, False))

    def test_resolves_installed_hook_target_without_old_build_constant(self):
        SCOPE["hook_manager"].hooks = {
            "resource": SimpleNamespace(_name="_resource_descriptor_walk_entry", target=0x14063A6D0)
        }
        self.assertEqual(observed_hook_rva(), 0x0063A6D0)
        SCOPE["hook_manager"].hooks = {}
        self.assertIsNone(observed_hook_rva())


if __name__ == "__main__":
    unittest.main()
