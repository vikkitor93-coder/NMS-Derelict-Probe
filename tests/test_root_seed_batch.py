from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("analyze_root_seed_batch", ROOT / "tools" / "analyze_root_seed_batch.py")
batch = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(batch)


def event(address: str, seed: str, sequence: int, *, use_seed: bool = True, system: str | None = None) -> dict:
    return {
        "kind": "resource_add",
        "resource_name": "MODELS/SPACE/POI/DUNGEON.SCENE.MBIN",
        "utc": f"2026-10-08T20:00:{sequence:02d}.000Z",
        "trace_sequence": sequence,
        "universe_address_hex_at_capture": address,
        "runtime_metadata_at_capture": {"universe_address_hex": address, "system_name": system or f"System-{sequence}", "reality_index": 0},
        "descriptor_pointer_hex": f"000000000000{sequence:04X}",
        "primary_seed": {"seed_hex": seed, "seed_signed": sequence, "use_seed_value": use_seed},
        "secondary_seed": {"seed_hex": "FFFFFFFFFFFFFFFF"},
    }


def write_journal(path: Path, events: list[dict], malformed: bool = False) -> None:
    lines = [json.dumps(item) for item in events]
    if malformed:
        lines.insert(1, "{broken json")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


class RootSeedBatchTests(unittest.TestCase):
    def test_five_system_events_are_kept_distinct_and_ready_for_comparison(self):
        with tempfile.TemporaryDirectory() as tmp:
            journal = Path(tmp) / "capture-journal-20261008T200000Z-1234.jsonl"
            write_journal(journal, [event(f"{i:016X}", f"{i + 10:016X}", i, system=f"System-{i}") for i in range(1, 6)])

            report = batch.build_report([journal], generated_utc="fixed")

            self.assertEqual(5, report["summary"]["root_event_observation_count"])
            self.assertEqual(5, report["summary"]["distinct_universe_address_count_overall"])
            cohort = report["process_cohorts"][0]
            self.assertTrue(cohort["ready_for_three_address_comparison"])
            self.assertEqual(5, len(cohort["address_groups"]))
            self.assertEqual(1234, cohort["process_id"])
            self.assertIn("does not infer or claim", report["analysis_policy"])

    def test_repeat_same_address_is_a_repeat_not_an_independent_address(self):
        with tempfile.TemporaryDirectory() as tmp:
            journal = Path(tmp) / "capture-journal-20261008T200000Z-42.jsonl"
            write_journal(journal, [
                event("0000000000000001", "000000000000000A", 1),
                event("0000000000000001", "000000000000000A", 2),
            ])

            report = batch.build_report([journal])

            self.assertEqual(2, report["summary"]["root_event_observation_count"])
            self.assertEqual(1, report["summary"]["distinct_universe_address_count_overall"])
            self.assertEqual("more-distinct-addresses-needed-in-one-process", report["summary"]["overall_status"])
            group = report["process_cohorts"][0]["address_groups"][0]
            self.assertTrue(group["repeatability"])
            self.assertEqual(2, group["observation_count"])

    def test_same_seed_at_two_addresses_is_reported_as_collision_without_inference(self):
        with tempfile.TemporaryDirectory() as tmp:
            journal = Path(tmp) / "capture-journal-20261008T200000Z-42.jsonl"
            write_journal(journal, [
                event("0000000000000001", "000000000000000A", 1),
                event("0000000000000002", "000000000000000A", 2),
                event("0000000000000003", "000000000000000B", 3),
            ])

            report = batch.build_report([journal])

            self.assertEqual([{
                "root_seed_candidate_hex": "000000000000000A",
                "universe_addresses_hex": ["0000000000000001", "0000000000000002"],
            }], report["process_cohorts"][0]["same_seed_seen_at_multiple_addresses"])

    def test_addresses_from_separate_launches_do_not_satisfy_single_cohort_threshold(self):
        with tempfile.TemporaryDirectory() as tmp:
            first = Path(tmp) / "capture-journal-20261008T200000Z-41.jsonl"
            second = Path(tmp) / "capture-journal-20261008T210000Z-42.jsonl"
            write_journal(first, [event("0000000000000001", "000000000000000A", 1), event("0000000000000002", "000000000000000B", 2)])
            write_journal(second, [event("0000000000000003", "000000000000000C", 3), event("0000000000000004", "000000000000000D", 4)])

            report = batch.build_report([first, second])

            self.assertEqual(4, report["summary"]["distinct_universe_address_count_overall"])
            self.assertEqual(0, report["summary"]["cohorts_ready_for_three_address_comparison"])
            self.assertEqual("more-distinct-addresses-needed-in-one-process", report["summary"]["overall_status"])

    def test_malformed_lines_missing_address_and_disabled_seed_remain_auditable(self):
        with tempfile.TemporaryDirectory() as tmp:
            journal = Path(tmp) / "capture-journal-20261008T200000Z-42.jsonl"
            write_journal(journal, [
                event("0000000000000001", "000000000000000A", 1, use_seed=False),
                event("not-an-address", "000000000000000B", 2),
            ], malformed=True)

            report = batch.build_report([journal])

            self.assertEqual(1, report["source_journals"][0]["malformed_lines"])
            self.assertEqual(2, report["summary"]["root_event_observation_count"])
            self.assertEqual(1, report["summary"]["incomplete_root_event_count"])
            self.assertEqual(False, report["process_cohorts"][0]["address_groups"][0]["events"][0]["use_seed_value"])
            self.assertEqual(1, len(report["process_cohorts"][0]["incomplete_events"]))

    def test_atomic_report_writer_emits_valid_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "reports" / "root-seed-batch-latest.json"
            report = batch.build_report([])
            batch.write_report(out, report)
            self.assertEqual(report, json.loads(out.read_text(encoding="utf-8")))


if __name__ == "__main__":
    unittest.main()
