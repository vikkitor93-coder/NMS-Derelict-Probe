"""Standalone entry point; also works in the full project or a renamed folder."""
import importlib.util
from pathlib import Path
import sys


def main():
    root = Path(__file__).resolve().parent
    sys.path.insert(0, str(root))  # bundled unchanged analyzer dependencies
    if not (root / "tools").is_dir():
        sys.path.insert(0, str(root.parents[1]))  # original project layout
    spec = importlib.util.spec_from_file_location("derelict_offline", root / "__init__.py",
                                                submodule_search_locations=[str(root)])
    module = importlib.util.module_from_spec(spec)
    sys.modules["derelict_offline"] = module
    spec.loader.exec_module(module)
    command = sys.argv[1] if len(sys.argv) > 1 else "diagnose"
    if command == "test":
        import unittest
        suite = unittest.defaultTestLoader.discover(str(root / "tests"), pattern="test_derelict_offline*.py")
        return 0 if unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful() else 1
    if command == "export":
        from derelict_offline.export_evidence import main as entry
    elif command == "native":
        from derelict_offline.native_check import check
        import json
        print(json.dumps(check(), indent=2))
        return 0
    elif command == "package":
        from derelict_offline.package_experiment import main as entry
    elif command == "runner":
        from derelict_offline.local_runner import main as entry
    elif command == "github":
        from derelict_offline.github_exchange import main as entry
    elif command == "gui":
        from derelict_offline.runner_gui import main as entry
    elif command == "install":
        from derelict_offline.install_runner import main as entry
    elif command == "update":
        from derelict_offline.update_protocol import apply_staged, record_update_state
        import argparse
        from derelict_offline.common import HERE
        parser = argparse.ArgumentParser()
        parser.add_argument("--apply", type=Path, required=True)
        parser.add_argument("--wait-pid", type=int)
        update_args = parser.parse_args(sys.argv[2:])
        try:
            apply_staged(HERE.resolve(), update_args.apply, update_args.wait_pid)
            return 0
        except Exception as error:
            if isinstance(error, ValueError):
                detail = str(error)
            elif isinstance(error, OSError):
                detail = "update-apply-filesystem-error"
            else:
                detail = "update-apply-unexpected-" + type(error).__name__
            record_update_state(HERE.resolve(), "failed", phase="failed", error=detail)
            return 2
    else:
        from derelict_offline.run import main as entry
        return entry(sys.argv[1:])
    return entry(sys.argv[2:])


if __name__ == "__main__":
    raise SystemExit(main())
