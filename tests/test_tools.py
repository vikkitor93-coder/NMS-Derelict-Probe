import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    return module


preview = load_module("build_preview", ROOT / "tools" / "build_preview.py")
compare_mod = load_module("compare_sessions", ROOT / "tools" / "compare_sessions.py")
overlay_mod = load_module("derelict_overlay", ROOT / "overlay" / "derelict_overlay.py")
crate_analyzer = load_module("analyze_crate_trace", ROOT / "tools" / "analyze_crate_trace.py")
crate_indexer = load_module("index_extracted_crates", ROOT / "tools" / "index_extracted_crates.py")
scene_indexer = load_module("build_scene_crate_index", ROOT / "tools" / "build_scene_crate_index.py")
session_asset_calc = load_module("calculate_session_crates_from_assets", ROOT / "tools" / "calculate_session_crates_from_assets.py")
asset_extract = load_module("extract_current_derelict_assets", ROOT / "tools" / "extract_current_derelict_assets.py")
crate_discovery = load_module("discover_crate_targets", ROOT / "tools" / "discover_crate_targets.py")
dungeon_table = load_module("analyze_dungeon_generation_table", ROOT / "tools" / "analyze_dungeon_generation_table.py")
generation_baseline = load_module("analyze_generation_baseline", ROOT / "tools" / "analyze_generation_baseline.py")
generation_measure = load_module("record_generation_measurement", ROOT / "tools" / "record_generation_measurement.py")
seed_room_correlation = load_module("analyze_seed_room_correlation", ROOT / "tools" / "analyze_seed_room_correlation.py")
caller_extract = load_module("extract_nms_caller_code", ROOT / "tools" / "extract_nms_caller_code.py")
upstream_extract = load_module("extract_nms_upstream_callers", ROOT / "tools" / "extract_nms_upstream_callers.py")
exact_root_extract = load_module("extract_exact_root_caller_code", ROOT / "tools" / "extract_exact_root_caller_code.py")
seed_function = load_module("analyze_nms_seed_function", ROOT / "tools" / "analyze_nms_seed_function.py")
github_integration = load_module("github_integration_recovery_test", ROOT / "tools" / "github_integration.py")


class ToolTests(unittest.TestCase):
    def setUp(self):
        self.sample = json.loads((ROOT / "samples" / "example-session.json").read_text(encoding="utf-8"))

    def test_preview_contains_expected_summary(self):
        rendered = preview.build_html(self.sample)
        self.assertIn("Example System", rendered)
        self.assertIn("Blue crates marked", rendered)
        self.assertIn(">1<", rendered)
        self.assertIn("<svg", rendered)

    def test_compare_same_spatial_address_across_realities(self):
        b = json.loads(json.dumps(self.sample))
        b["runtime_start"]["reality_index"] = 5
        result = compare_mod.compare(self.sample, b)
        self.assertTrue(result["same_galactic_address_ignoring_reality"])
        self.assertFalse(result["same_full_runtime_address"])
        self.assertTrue(result["different_reality_index"])
        self.assertTrue(result["same_marked_blue_crate_count"])

    def test_preview_cli_output(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "preview.html"
            out.write_text(preview.build_html(self.sample), encoding="utf-8")
            self.assertGreater(out.stat().st_size, 1000)

    def test_overlay_ready_and_recording_summaries(self):
        ready = {
            "heartbeat_epoch": 1000.0,
            "probe_version": "0.3.10",
            "state": "ready",
            "recording": False,
            "detail": "Loaded & ready — enter a derelict freighter",
            "last_event": "Probe loaded — ready to record",
        }
        ready_view = overlay_mod.summarize_status(ready, now_epoch=1001.0)
        self.assertIn("LOADED & READY", ready_view["headline"])
        self.assertEqual("", ready_view["counts"])

        recording = dict(ready)
        recording.update({
            "state": "recording",
            "recording": True,
            "blue_crates": 7,
            "rooms": 3,
            "room_zero_rooms": 2,
            "vertical_transitions": 1,
            "shuttle_bays": 0,
            "engineering_marked": True,
            "engineering_module_class": "S",
            "position": {"x": 12.5, "y": -2.25, "z": 90.0},
            "position_source": "player.mPosition",
            "last_event": "Crate added #7 (F7)",
            "trace": {"resource_events": 12, "reward_events": 1, "unique_seed_count": 3, "last_seed_hex": "0123456789ABCDEF"},
            "auto_crates": {"count": 7, "salvage_crates": 5, "crew_footlockers": 2, "target_ids": ["ABAND_CRATE_M", "FOOTLOCKER"], "status": "live", "confidence": "high", "method": "Engine.AddNodes", "node_spawn_events": 40},
        })
        recording_view = overlay_mod.summarize_status(recording, now_epoch=1001.0)
        self.assertIn("RECORDING", recording_view["headline"])
        self.assertIn("CRATES 7", recording_view["counts"])
        self.assertIn("ROOMS 3", recording_view["counts"])
        self.assertIn("ROOM 0 2", recording_view["counts"])
        self.assertIn("ENG YES", recording_view["counts"])
        self.assertIn("MODULE S", recording_view["counts"])
        self.assertIn("X 12.500", recording_view["telemetry"])
        self.assertIn("SOURCE player.mPosition", recording_view["telemetry"])
        self.assertIn("F5 ROOM 0", recording_view["hotkeys_1"])
        self.assertIn("F10 ENGINEERING", recording_view["hotkeys_2"])
        self.assertIn("F11 MODULE C-S", recording_view["hotkeys_2"])
        self.assertEqual("Crate added #7 (F7)", recording_view["event"])
        self.assertIn("TRACE RES 12", recording_view["trace"])
        self.assertIn("REWARD 1", recording_view["trace"])
        self.assertIn("0123456789ABCDEF", recording_view["trace"])
        self.assertIn("AUTO TARGET 7", recording_view["auto_crates"])
        self.assertIn("SALVAGE 5", recording_view["auto_crates"])
        self.assertIn("FOOTLOCKER 2", recording_view["auto_crates"])
        self.assertIn("LIVE", recording_view["auto_crates"])


    def test_overlay_supports_opacity_without_layered_window_style(self):
        source = (ROOT / "overlay" / "derelict_overlay.py").read_text(encoding="utf-8")
        self.assertIn('attributes("-alpha"', source)
        self.assertNotIn("WS_EX_LAYERED =", source)
        self.assertIn("_apply_safe_window_style", source)

    def test_overlay_settings_are_clamped_and_default_backwards_compatibly(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "settings.json"
            path.write_text('{"show_rooms": false, "opacity_percent": 2, "x_offset": 9000}', encoding="utf-8")
            settings = overlay_mod.load_overlay_settings(path)
        self.assertFalse(settings["show_rooms"])
        self.assertEqual(20, settings["opacity_percent"])
        self.assertEqual(800, settings["x_offset"])
        self.assertEqual(18, settings["y_offset"])

    def test_agent_objective_requires_actual_dispatch_capture_for_plus_10_completion(self):
        snapshot = {"lanes": [{"id": "agent-a", "name": "Agent A", "human_required": True,
                               "surveyor_request": "Run game, wait for root dispatch +0x10, then publish"}]}
        live = {"generation_rooms": {"dungeon_root_resource_events_seen": 1}}
        pending = overlay_mod.build_agent_objectives(snapshot, live, True)["objectives"][0]
        self.assertFalse(pending["complete"])
        self.assertIn("+0x10 DISPATCH STILL NEEDED", pending["status"])
        live["root_dispatch_capture"] = {"captured": True}
        complete = overlay_mod.build_agent_objectives(snapshot, live, True)["objectives"][0]
        self.assertTrue(complete["complete"])
        self.assertTrue(complete["keep_game_open"])
        self.assertIn("WAITING FOR UPLOAD", complete["status"])

    def test_overlay_controls_live_in_main_surveyor_not_overlay(self):
        controller = (ROOT / "tools" / "surveyor_controller.py").read_text(encoding="utf-8")
        overlay = (ROOT / "overlay" / "derelict_overlay.py").read_text(encoding="utf-8")
        self.assertIn('"In-game overlay display"', controller)
        self.assertIn('"Horizontal position"', controller)
        self.assertIn('"Vertical position"', controller)
        self.assertIn('"Opacity"', controller)
        self.assertNotIn("tk.Checkbutton(", overlay)

    def test_overlay_detects_stale_heartbeat(self):
        view = overlay_mod.summarize_status({"heartbeat_epoch": 100.0}, now_epoch=110.0)
        self.assertEqual("stale", view["state"])
        self.assertIn("HEARTBEAT LOST", view["headline"])

    def test_shared_live_status_contains_main_and_overlay_fields(self):
        status = {
            "heartbeat_epoch": 1000.0,
            "probe_version": "0.3.41",
            "state": "recording",
            "recording": True,
            "blue_crates": 4,
            "rooms": 2,
            "position": {"x": 1, "y": 2, "z": 3},
            "position_source": "player.mPosition",
            "generation_rooms": {
                "logical_entry_candidate_count": 52,
                "logical_entry_unique_callers_observed": 3,
                "logical_entry_known_candidate_hits": 1,
                "last_dungeon_logical_entry_exact_external_caller_offset_hex": "0x02BFCC17",
            },
        }
        view = overlay_mod.summarize_status(status, now_epoch=1001.0, nms_running=True)
        self.assertEqual("Running", view["nms"])
        self.assertEqual("Connected — probe 0.3.41", view["probe"])
        self.assertEqual("Recording", view["capture"])
        self.assertIn("Watching all 52 refs", view["caller_scan"])
        self.assertIn("0x02BFCC17", view["exact_root_caller"])
        for key in (
            "detail", "telemetry", "counts", "auto_crates", "loot_summary", "room_loot",
            "trace", "generation", "event", "hotkeys_1", "hotkeys_2",
        ):
            self.assertIn(key, view)

    def test_controller_uses_shared_overlay_status_and_exposes_extension_refresh(self):
        source = (ROOT / "tools" / "surveyor_controller.py").read_text(encoding="utf-8")
        self.assertIn("from overlay.derelict_overlay import summarize_status", source)
        self.assertIn('("Check lane extensions", self._check_agent_ui_extensions)', source)
        self.assertIn('"Updates available: {updates}. Use Update all extensions', source)
        self.assertIn('text="Check extensions"', source)
        self.assertIn('text="Update all extensions"', source)

    def test_verified_baseline_001_is_51_crates(self):
        fixture = json.loads((ROOT / "corpus" / "verified" / "baseline-001_51-crates.json").read_text(encoding="utf-8"))
        self.assertEqual(51, fixture["historical_reported_blue_crates"])
        self.assertEqual(51, fixture["current_observed_blue_crates"])
        self.assertTrue(fixture["match_historical"])
        self.assertEqual(51, fixture["manual_markers"]["blue_crates"])
        self.assertEqual(7, fixture["manual_markers"]["rooms"])
        self.assertEqual(0, fixture["manual_markers"]["room_zero"])
        self.assertEqual(1, fixture["manual_markers"]["vertical_transitions"])
        self.assertEqual(1, fixture["manual_markers"]["engineering"])

    def test_probe_has_cosmos_position_and_environment_fallbacks(self):
        source = (ROOT / "mod" / "derelict_baseline_probe.py").read_text(encoding="utf-8")
        self.assertIn("player.mPosition", source)
        self.assertIn("env.mPlayerTM.pos", source)
        self.assertIn('meta["environment_location_live"]', source)
        self.assertIn('meta["environment_location_stable"]', source)
        self.assertIn('meta["environment_location"] = "AbandonedFreighter"', source)
        self.assertIn('@on_key_pressed("f5")', source)
        self.assertIn('@on_key_pressed("f11")', source)
        self.assertIn('order = ["unknown", "C", "B", "A", "S"]', source)
        self.assertIn('"engineering_module_class": "F11"', source)
        self.assertIn('self._add_marker("room_zero")', source)
        self.assertIn('"position_source": pos_source', source)
        self.assertIn('LIVE_STATUS_INTERVAL_SECONDS = 0.20', source)

    def test_preview_and_compare_support_room_zero(self):
        a = json.loads(json.dumps(self.sample))
        a.setdefault("markers", []).append({"type":"room_zero","ordinal":1,"x":0,"y":0,"z":0})
        html = preview.build_html(a)
        self.assertIn("Room 0 / dead ends", html)
        self.assertIn("0 = Room 0 / dead end", html)
        b = json.loads(json.dumps(a))
        result = compare_mod.compare(a, b)
        self.assertTrue(result["same_marked_room_zero_count"])

    def test_module_rank_contract_is_c_to_s(self):
        schema = json.loads((ROOT / "schema" / "live-status-v1.schema.json").read_text(encoding="utf-8"))
        self.assertEqual(["unknown", "C", "B", "A", "S"], schema["properties"]["engineering_module_class"]["enum"])
        source = (ROOT / "mod" / "derelict_baseline_probe.py").read_text(encoding="utf-8")
        self.assertIn('self._session["manual"]["engineering_module_class"] = new_value', source)
        self.assertIn('Module rank set to {display} (F11)', source)


    def test_verified_baseline_002_is_35_crates_s_class(self):
        fixture = json.loads((ROOT / "corpus" / "verified" / "baseline-002_35-crates_S.json").read_text(encoding="utf-8"))
        self.assertEqual(35, fixture["observed_blue_crates"])
        self.assertEqual("S", fixture["engineering_module_class"])
        self.assertEqual(7, fixture["manual_markers"]["rooms"])
        self.assertEqual(1, fixture["manual_markers"]["room_zero"])
        self.assertEqual(2, fixture["manual_markers"]["vertical_transitions"])
        self.assertEqual(1, fixture["manual_markers"]["shuttle_bays"])

    def test_crate_trace_analyzer_extracts_seed_candidates(self):
        session = json.loads(json.dumps(self.sample))
        session["markers"].extend([
            {"type": "blue_crate", "ordinal": 2, "x": 1, "y": 2, "z": 3},
            {"type": "blue_crate", "ordinal": 3, "x": 2, "y": 2, "z": 3},
        ])
        session.setdefault("manual", {})["engineering_module_class"] = "S"
        session["auto_crates"] = {
            "events": [
                {"kind": "node_probe", "countable": True, "target_id": "ABAND_CRATE_M", "instance_key": "00000001", "method": "Engine.AddNodes"},
                {"kind": "node_probe", "countable": True, "target_id": "FOOTLOCKER", "instance_key": "00000002", "method": "Engine.AddNodes"},
                {"kind": "node_probe", "countable": True, "target_id": "FOOTLOCKER", "instance_key": "00000002", "method": "Engine.AddGroupNode"},
            ],
            "final_summary": {"count": 2, "salvage_crates": 1, "crew_footlockers": 1, "status": "live", "confidence": "high", "method": "Engine.AddNodes"},
        }
        session["trace"] = {"events": [
            {"kind": "resource_add", "resource_name": "MODELS/SPACE/POI/PARTS/DUNGEON_A.SCENE.MBIN",
             "primary_seed": {"seed_hex": "0000000000001111"}, "secondary_seed": {"seed_hex": "0000000000002222"}},
            {"kind": "reward", "reward_id": "TEST", "seed": {"seed_hex": "0000000000003333"}},
        ]}
        report = crate_analyzer.analyze(session)
        self.assertEqual(3, report["observed_blue_crates"])
        self.assertEqual("S", report["engineering_module_class"])
        self.assertEqual(1, report["resource_event_count"])
        self.assertEqual(1, report["reward_event_count"])
        self.assertEqual(3, report["unique_seed_count"])
        self.assertEqual(2, report["auto_blue_crates"])
        self.assertFalse(report["auto_crate_matches_manual"])

    def test_extracted_asset_indexer_counts_salvage_crate_refs(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "room_a.exml").write_text("ABAND_CRATE_M x ABAND_CRATE_M", encoding="utf-8")
            (root / "room_b.json").write_text('{"id":"ABAND_CRATE_M","other":"FOOTLOCKER"}', encoding="utf-8")
            (root / "room_c.txt").write_text("FOOTLOCKER FOOTLOCKER", encoding="utf-8")
            (root / "ignore.bin").write_bytes(b"ABAND_CRATE_M FOOTLOCKER")
            result = crate_indexer.build_index(root)
            self.assertEqual(3, result["files_with_target_containers"])
            self.assertEqual(3, result["total_salvage_crate_refs"])
            self.assertEqual(3, result["total_crew_footlocker_refs"])
            self.assertEqual(2, result["entries"][0]["target_container_refs"])

    def test_probe_has_crate_seed_trace_hooks(self):
        source = (ROOT / "mod" / "derelict_baseline_probe.py").read_text(encoding="utf-8")
        self.assertIn("@nms.Engine.AddResource.before", source)
        self.assertIn("@nms.cGcRewardManager.GiveGenericReward.before", source)
        self.assertIn('"kind": "resource_add"', source)
        self.assertIn('"kind": "reward"', source)
        self.assertIn('"trace": self._trace_summary()', source)
        self.assertIn("TRACE_PRESESSION_SECONDS = 60.0", source)

    def test_probe_has_experimental_auto_crate_instance_hooks(self):
        source = (ROOT / "mod" / "derelict_baseline_probe.py").read_text(encoding="utf-8")
        self.assertIn('SALVAGE_CRATE_ID = "ABAND_CRATE_M"', source)
        self.assertIn('CREW_FOOTLOCKER_ID = "FOOTLOCKER"', source)
        self.assertIn('@nms.Engine.AddResource.after', source)
        self.assertIn('@nms.Engine.AddNodes.after', source)
        self.assertIn('@nms.Engine.AddGroupNode.after', source)
        self.assertIn('@nms.cTkResource.cTkResource.after', source)
        self.assertIn('@nms.cTkResourceManager.FindResourceA.after', source)
        self.assertIn('_resource_from_return_pointer', source)
        self.assertIn('ctypes.POINTER(nms.cTkResource)', source)
        self.assertIn('obj.mHandle', source)
        self.assertIn('obj.msName', source)
        self.assertIn('getattr(value, "_value", None)', source)
        self.assertIn('nms.Engine.GetResourceHandleForNode', source)
        self.assertIn('nms.Engine.GetNodeName', source)
        self.assertIn('\"parent_node_name\"', source)
        self.assertIn('"scene_probe"', source)
        self.assertIn('"raw_resources"', source)
        self.assertIn('"auto_crates": self._auto_crate_summary()', source)
        self.assertIn('"final_summary"', source)


    def test_v034_findresource_diagnostic_captures_decoder_failure(self):
        fixture = json.loads((ROOT / "corpus" / "research" / "baseline-001_findresource-diagnostic-v0.3.4.json").read_text(encoding="utf-8"))
        self.assertEqual(51, fixture["known_verified_target_container_count"])
        self.assertEqual(0, fixture["automatic_target_count"])
        self.assertGreater(fixture["resource_find_calls"], 600000)
        self.assertEqual("cTkResource*", fixture["diagnosis"]["current_symbol_return_type"])
        self.assertEqual("pyMHF c_char_p64", fixture["diagnosis"]["char_pointer_wrapper"])
        self.assertEqual("1EE5E3C00986D42A", fixture["nonzero_reward_seed_hex"])

    def test_overlay_distinguishes_unknown_scanning_and_live_auto_crates(self):
        base = {
            "heartbeat_epoch": 1000.0, "probe_version": "0.3.10", "state": "recording",
            "recording": True, "detail": "recording", "last_event": "",
        }
        unknown = overlay_mod.summarize_status({**base, "auto_crates": {"count": 0, "status": "waiting-for-node-signal"}}, now_epoch=1001.0)
        self.assertIn("AUTO TARGET ?", unknown["auto_crates"])
        scanning = overlay_mod.summarize_status({**base, "auto_crates": {"count": 0, "salvage_crates": 0, "crew_footlockers": 0, "status": "scanning", "target_ids": ["ABAND_CRATE_M", "FOOTLOCKER"], "scene_probe_events": 365, "resolved_resource_names": 120, "resource_index_size": 900, "resource_find_mapped": 777}}, now_epoch=1001.0)
        self.assertIn("AUTO TARGET 0", scanning["auto_crates"])
        self.assertIn("RAW 365", scanning["auto_crates"])
        self.assertIn("RESOLVED 120", scanning["auto_crates"])
        self.assertIn("INDEX 900", scanning["auto_crates"])
        self.assertIn("FINDMAP 777", scanning["auto_crates"])
        embedded = overlay_mod.summarize_status({**base, "auto_crates": {"count": 0, "status": "embedded-in-room-scenes", "scene_probe_events": 100, "resolved_resource_names": 95, "resource_index_size": 19000}}, now_epoch=1001.0)
        self.assertIn("AUTO TARGET ?", embedded["auto_crates"])
        self.assertIn("EMBEDDED IN ROOM SCENES", embedded["auto_crates"])
        live = overlay_mod.summarize_status({**base, "auto_crates": {"count": 51, "salvage_crates": 39, "crew_footlockers": 12, "status": "live", "method": "Engine.AddNodes"}}, now_epoch=1001.0)
        self.assertIn("AUTO TARGET 51", live["auto_crates"])
        self.assertIn("SALVAGE 39", live["auto_crates"])
        self.assertIn("FOOTLOCKER 12", live["auto_crates"])


    def test_scene_crate_index_follows_nested_scene_aliases(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            dungeon = root / "MODELS" / "SPACE" / "POI" / "DUNGEON" / "CARG"
            target = root / "MODELS" / "PLANETS" / "BIOMES" / "COMMON" / "BUILDINGS" / "PARTS" / "BUILDABLEPARTS" / "DECORATION"
            dungeon.mkdir(parents=True)
            target.mkdir(parents=True)
            (target / "CRATEM_PLACEMENT.SCENE.MXML").write_text("ABAND_CRATE_M", encoding="utf-8")
            (target / "FOOT_LOCKER_PLACEMENT.SCENE.MXML").write_text("FOOTLOCKER", encoding="utf-8")
            (dungeon / "CHILD.SCENE.MXML").write_text(
                'MODELS/PLANETS/BIOMES/COMMON/BUILDINGS/PARTS/BUILDABLEPARTS/DECORATION/CRATEM_PLACEMENT.SCENE.MBIN\n'
                'MODELS/PLANETS/BIOMES/COMMON/BUILDINGS/PARTS/BUILDABLEPARTS/DECORATION/FOOT_LOCKER_PLACEMENT.SCENE.MBIN',
                encoding="utf-8",
            )
            (dungeon / "ROOM.SCENE.MXML").write_text(
                'MODELS/SPACE/POI/DUNGEON/CARG/CHILD.SCENE.MBIN\n'
                'MODELS/SPACE/POI/DUNGEON/CARG/CHILD.SCENE.MBIN',
                encoding="utf-8",
            )
            result = scene_indexer.build_index(root)
            by_scene = {row["scene_path"]: row for row in result["entries"]}
            row = by_scene["MODELS/SPACE/POI/DUNGEON/CARG/ROOM.SCENE.MBIN"]
            self.assertEqual(2, row["salvage_crates"])
            self.assertEqual(2, row["crew_footlockers"])
            self.assertEqual(4, row["target_containers"])
            self.assertTrue(all(v["scene_export_found"] for v in result["alias_validation"]))
            self.assertTrue(all(v["contains_expected_id"] for v in result["alias_validation"]))

    def test_session_asset_calculator_sums_unique_dungeon_instances(self):
        session = {
            "session_id": "s", "probe_version": "x",
            "started_utc": "2026-09-29T14:00:00Z", "ended_utc": "2026-09-29T14:05:00Z",
            "runtime_start": {"universe_address_hex": "ABC"},
            "markers": [],
            "scene_probe": {"events": [
                {"utc": "2026-09-29T14:00:01Z", "instance_key": "1", "resource_name": "MODELS/SPACE/POI/DUNGEON/CARG/A.SCENE.MBIN"},
                {"utc": "2026-09-29T14:00:02Z", "instance_key": "2", "resource_name": "MODELS/SPACE/POI/DUNGEON/CARG/A.SCENE.MBIN"},
                {"utc": "2026-09-29T14:00:03Z", "instance_key": "2", "resource_name": "MODELS/SPACE/POI/DUNGEON/CARG/A.SCENE.MBIN"},
            ]},
        }
        index = {"entries": [{"scene_path": "MODELS/SPACE/POI/DUNGEON/CARG/A.SCENE.MBIN", "salvage_crates": 2, "crew_footlockers": 1, "target_containers": 3}]}
        result = session_asset_calc.calculate(session, index)
        self.assertEqual(2, result["dungeon_scene_instances"])
        self.assertEqual(6, result["predicted_target_containers"])
        self.assertEqual(4, result["predicted_salvage_crates"])
        self.assertEqual(2, result["predicted_crew_footlockers"])

    def test_hgpak_filters_cover_dungeon_and_two_target_aliases(self):
        filters = asset_extract.FILTERS
        self.assertTrue(any("MODELS/SPACE/POI/DUNGEON" in x for x in filters))
        self.assertTrue(any("CRATEM_PLACEMENT.SCENE.MBIN" in x for x in filters))
        self.assertTrue(any("FOOT_LOCKER_PLACEMENT.SCENE.MBIN" in x for x in filters))

    def test_v035_resource_resolution_fixture(self):
        fixture = json.loads((ROOT / "corpus" / "research" / "baseline-001-resource-resolution-v0.3.5.json").read_text(encoding="utf-8"))
        self.assertEqual(51, fixture["known_verified_target_container_count"])
        self.assertEqual(0, fixture["automatic_target_count"])
        self.assertGreater(fixture["resolved_resource_names"], 1000)
        self.assertGreater(fixture["resource_index_size"], 19000)
        self.assertIn("CORNER_CRATES00.SCENE.MBIN", fixture["last_candidate_name"])


    def test_scene_index_does_not_double_count_id_plus_alias_for_same_target(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            dungeon = root / "MODELS" / "SPACE" / "POI" / "DUNGEON" / "CARG"
            dungeon.mkdir(parents=True)
            (dungeon / "ONE.SCENE.MXML").write_text(
                'ABAND_CRATE_M\nMODELS/PLANETS/BIOMES/COMMON/BUILDINGS/PARTS/BUILDABLEPARTS/DECORATION/CRATEM_PLACEMENT.SCENE.MBIN',
                encoding="utf-8",
            )
            result = scene_indexer.build_index(root)
            row = next(x for x in result["entries"] if x["scene_path"].endswith("ONE.SCENE.MBIN"))
            self.assertEqual(1, row["salvage_crates"])
            self.assertEqual(1, row["target_containers"])


    def test_crate_discovery_ranks_entity_refs_from_used_scenes(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            dungeon = root / "MODELS" / "SPACE" / "POI" / "DUNGEON" / "CARG"
            dungeon.mkdir(parents=True)
            (dungeon / "ROOM.SCENE.MXML").write_text(
                'MODELS/SPACE/POI/DUNGEON/CARG/LOOTBOX.ENTITY.MBIN\nCRATE_MARKER', encoding="utf-8")
            (dungeon / "LOOTBOX.ENTITY.MXML").write_text(
                'GcInteractionComponentData REWARD_LOOT CRATE', encoding="utf-8")
            session = {
                "session_id":"s", "probe_version":"x",
                "started_utc":"2026-09-29T14:00:00Z", "ended_utc":"2026-09-29T14:01:00Z",
                "runtime_start":{"universe_address_hex":"ABC"},
                "scene_probe":{"events":[
                    {"utc":"2026-09-29T14:00:01Z","instance_key":"1","resource_name":"MODELS/SPACE/POI/DUNGEON/CARG/ROOM.SCENE.MBIN"},
                    {"utc":"2026-09-29T14:00:02Z","instance_key":"2","resource_name":"MODELS/SPACE/POI/DUNGEON/CARG/ROOM.SCENE.MBIN"}
                ]}
            }
            result = crate_discovery.analyze(root, session)
            self.assertEqual(2, result["used_dungeon_scene_instances"])
            self.assertEqual("MODELS/SPACE/POI/DUNGEON/CARG/LOOTBOX.ENTITY.MBIN", result["weighted_entity_refs"][0]["path"])
            self.assertEqual(2, result["weighted_entity_refs"][0]["weighted_refs"])
            self.assertTrue(result["entity_details"][0]["export_found"])
            self.assertIn("LOOT", result["entity_details"][0]["semantic_hints"])

    def test_v036_asset_fixture_records_salvage_gap(self):
        fixture = json.loads((ROOT / "corpus" / "research" / "baseline-001-asset-calculation-v0.3.6.json").read_text(encoding="utf-8"))
        self.assertEqual(126, fixture["session_calculation"]["resolved_scene_instances"])
        self.assertEqual(0, fixture["session_calculation"]["predicted_salvage_crates"])
        self.assertEqual(19, fixture["session_calculation"]["predicted_crew_footlockers"])
        self.assertEqual(0, fixture["index"]["salvage_positive_scenes"])
        self.assertEqual(31, fixture["index"]["footlocker_positive_scenes"])

    def test_hgpak_filters_include_mapping_tables_for_dynamic_target_discovery(self):
        filters = asset_extract.FILTERS
        self.assertTrue(any("BASEBUILDINGOBJECTSTABLE.MBIN" in x for x in filters))
        self.assertTrue(any("BASEBUILDINGPARTSTABLE.MBIN" in x for x in filters))
        self.assertTrue(any("FREIGHTERDUNGEONSTABLE.MBIN" in x for x in filters))

    def test_scene_index_counts_exact_cratem_and_foot_locker_node_tokens(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            dungeon = root / "MODELS" / "SPACE" / "POI" / "DUNGEON" / "CARG"
            dungeon.mkdir(parents=True)
            (dungeon / "ROOM.SCENE.MXML").write_text(
                "CRATEM REFCRATEM CRATEM REFCRATEM1 FOOT_LOCKER REFFOOTLOCKER",
                encoding="utf-8",
            )
            result = scene_indexer.build_index(root)
            row = next(x for x in result["entries"] if x["scene_path"].endswith("ROOM.SCENE.MBIN"))
            self.assertEqual(2, row["salvage_crates"])
            self.assertEqual(1, row["crew_footlockers"])
            self.assertEqual(3, row["target_containers"])
            self.assertEqual(2, row["node_salvage_crate_refs"])
            self.assertEqual(1, row["node_crew_footlocker_refs"])

    def test_v037_cratem_node_correlation_matches_verified_51(self):
        fixture = json.loads((ROOT / "corpus" / "research" / "baseline-001-cratem-node-correlation-v0.3.7.json").read_text(encoding="utf-8"))
        nodes = fixture["weighted_exact_node_tokens"]
        self.assertEqual(32, nodes["CRATEM"])
        self.assertEqual(19, nodes["FOOT_LOCKER"])
        self.assertEqual(51, nodes["CRATEM"] + nodes["FOOT_LOCKER"])
        self.assertEqual(fixture["known_verified_target_container_count"], fixture["combined_exact_node_tokens"])
        self.assertEqual(32, fixture["reference_partition_validation"]["CRATEM"]["sum"])


    def test_dungeon_generation_table_parser_normalizes_and_preserves_unknown_rules(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            mxml = root / "FREIGHTERDUNGEONSTABLE.MXML"
            mxml.write_text("""<Data template=\"GcFreighterDungeonsTable\">
<Property name=\"Dungeons\">
  <Property value=\"GcFreighterDungeonParams.xml\">
    <Property name=\"Name\" value=\"CARGO_TEST\" />
    <Property name=\"DungeonParams\" value=\"GcDungeonGenerationParams.xml\">
      <Property name=\"SizeX\" value=\"8\" /><Property name=\"SizeY\" value=\"2\" /><Property name=\"SizeZ\" value=\"9\" />
      <Property name=\"EntranceX\" value=\"1\" /><Property name=\"EntranceY\" value=\"0\" /><Property name=\"EntranceZ\" value=\"2\" />
      <Property name=\"Rooms\" value=\"12\" /><Property name=\"XProbability\" value=\"0.4\" />
      <Property name=\"YProbability\" value=\"0.1\" /><Property name=\"ZProbability\" value=\"0.5\" /><Property name=\"StraightMultiplier\" value=\"1.25\" />
      <Property name=\"MainRoomTypes\"><Property value=\"GcDungeonRoomParams.xml\"><Property name=\"RoomId\" value=\"CARG\" /><Property name=\"BranchProbability\" value=\"0.25\" /></Property></Property>
      <Property name=\"BranchRoomTypes\"><Property value=\"NMSString0x10.xml\"><Property name=\"Value\" value=\"BARRACKS\" /></Property></Property>
      <Property name=\"GenerationRules\">
        <Property value=\"GcRoomCountRule.xml\"><Property name=\"RoomID\" value=\"CARG\" /><Property name=\"Min\" value=\"2\" /><Property name=\"Max\" value=\"5\" /></Property>
        <Property value=\"GcFutureRule.xml\"><Property name=\"Foo\" value=\"Bar\" /></Property>
      </Property>
      <Property name=\"PruningRules\"><Property value=\"NMSString0x10.xml\"><Property name=\"Value\" value=\"NO_DEADENDS\" /></Property></Property>
    </Property>
  </Property>
</Property></Data>""", encoding="utf-8")
            path = dungeon_table.find_table(root)
            doc = dungeon_table.ET.parse(path).getroot()
            items = [dungeon_table.prop_to_obj(el) for el in dungeon_table.iter_dungeon_items(doc)]
            self.assertEqual(1, len(items))
            d = dungeon_table.normalize_dungeon(items[0])
            self.assertEqual("CARGO_TEST", d["name"])
            self.assertEqual(12, d["rooms"])
            self.assertEqual(8, d["size"]["x"])
            self.assertEqual("CARG", d["main_room_types"][0]["room_id"])
            self.assertEqual(["BARRACKS"], d["branch_room_types"])
            self.assertEqual(2, d["generation_rules"][0]["min"])
            self.assertEqual("Bar", d["generation_rules"][1]["fields"]["Foo"])
            self.assertEqual(["NO_DEADENDS"], d["pruning_rules"])


    def test_dungeon_generation_table_parser_unwraps_cosmos_nested_rules(self):
        item = {
            "value": "GcRoomCountRule",
            "children": [{
                "name": "GcRoomCountRule", "value": None,
                "children": [
                    {"name": "RoomID", "value": "R_CARG", "children": []},
                    {"name": "Min", "value": 2, "children": []},
                    {"name": "Max", "value": 100, "children": []},
                ],
            }],
        }
        params = {"children": [{"name": "GenerationRules", "value": None, "children": [item]}]}
        rules = dungeon_table.parse_rules(params)
        self.assertEqual("R_CARG", rules[0]["room_id"])
        self.assertEqual(2, rules[0]["min"])
        self.assertEqual(100, rules[0]["max"])

    def test_v0310_generation_fingerprint_matches_verified_51(self):
        fixture = json.loads((ROOT / "corpus" / "research" / "baseline-001-generation-fingerprint-v0.3.10.json").read_text(encoding="utf-8"))
        self.assertEqual("0001550006607CAC", fixture["universe_address_hex"])
        self.assertEqual("CARGO_FLOATERS", fixture["preset_inference"]["preset"])
        self.assertEqual("high", fixture["preset_inference"]["confidence"])
        self.assertEqual(126, fixture["dungeon_scene_instances"])
        self.assertEqual(9, fixture["logical_generated_chunks"])
        self.assertEqual(7, fixture["base_room_count_from_table"])
        self.assertEqual(32, fixture["predicted_salvage_crates"])
        self.assertEqual(19, fixture["predicted_crew_footlockers"])
        self.assertEqual(51, fixture["predicted_target_containers"])
        seeds={x["seed_hex"] for x in fixture["reward_seed_candidates"]}
        self.assertEqual({"1EE5E3C00986D42A"}, seeds)
        self.assertEqual("0x155", fixture["historical_16_system_block_hypothesis"]["solar_system_index_hex"])
        self.assertEqual("0x150", fixture["historical_16_system_block_hypothesis"]["block_start_hex"])
        rules = fixture["selected_preset_config"]["generation_rules"]
        self.assertEqual("R_FLO_BARR", rules[0]["room_id"])
        self.assertEqual(1, rules[0]["min"])
        self.assertEqual(1, rules[0]["max"])
        self.assertEqual("R_W_END", rules[4]["quest_item_id"])

    def test_v038_verified_asset_calculation_is_51(self):
        fixture = json.loads((ROOT / "corpus" / "research" / "baseline-001-asset-calculation-v0.3.8.json").read_text(encoding="utf-8"))
        self.assertEqual(126, fixture["dungeon_scene_instances"])
        self.assertEqual(126, fixture["resolved_scene_instances"])
        self.assertEqual(32, fixture["predicted_salvage_crates"])
        self.assertEqual(19, fixture["predicted_crew_footlockers"])
        self.assertEqual(51, fixture["predicted_target_containers"])

    def test_v0311_room_model_matches_verified_51_and_35(self):
        a = json.loads((ROOT / "corpus" / "research" / "baseline-001-generation-fingerprint-v0.3.11.json").read_text(encoding="utf-8"))
        b = json.loads((ROOT / "corpus" / "research" / "baseline-002-generation-fingerprint-v0.3.11.json").read_text(encoding="utf-8"))
        self.assertEqual((7, 2, 9, 51), (a["observed_main_rooms"], a["observed_dead_end_rooms"], a["observed_total_rooms"], a["predicted_target_containers"]))
        self.assertEqual((7, 1, 8, 35), (b["observed_main_rooms"], b["observed_dead_end_rooms"], b["observed_total_rooms"], b["predicted_target_containers"]))
        self.assertTrue(a["main_room_count_matches_table"])
        self.assertTrue(b["main_room_count_matches_table"])

    def test_dead_end_classifier_rejects_room_deadend_wall_piece(self):
        dead, evidence = generation_baseline.is_dead_end_group([
            "MODELS/SPACE/POI/DUNGEON/BARRACKS/ROOM_FLOOR0.SCENE.MBIN",
            "MODELS/SPACE/POI/DUNGEON/EMPTY/ROOM_DEADEND_R_2.SCENE.MBIN",
            "MODELS/SPACE/POI/DUNGEON/BARRACKS/WALL_BUNK00.SCENE.MBIN",
            "MODELS/SPACE/POI/DUNGEON/EMPTY/ROOM_WALL_2.SCENE.MBIN",
            "MODELS/SPACE/POI/DUNGEON/EMPTY/ROOM_INCORNER_2.SCENE.MBIN",
        ])
        self.assertFalse(dead)
        self.assertEqual([], evidence)

    def test_dead_end_classifier_accepts_compact_family_deadend_group(self):
        dead, evidence = generation_baseline.is_dead_end_group([
            "MODELS/SPACE/POI/DUNGEON/BARRACKS/DEADEND_BUNK0.SCENE.MBIN",
            "MODELS/SPACE/POI/DUNGEON/COMM/STRAIGHT08A.SCENE.MBIN",
            "MODELS/SPACE/POI/DUNGEON/EMPTY/CORRIDOR_STRAIGHT.SCENE.MBIN",
        ])
        self.assertTrue(dead)
        self.assertEqual(1, len(evidence))

    def test_poi_context_is_reclassified_when_it_matches_universe_address(self):
        session={
            "runtime_start":{"universe_address_hex":"00001A0004E84EFD"},
            "trace":{"events":[
                {"kind":"space_poi_description","poi_type_value":6,"poi_type_name":"AbandonedFreighter","raw_argument_hex":"00001A0004E84EFD","raw_argument_u64":0x00001A0004E84EFD,"interpretation":"poi-context-u64"},
            ]},
            "scene_probe":{"events":[]},
        }
        rows=generation_baseline.poi_seed_candidates(session)
        self.assertEqual(1,len(rows))
        # Reclassification occurs in build_baseline because it needs runtime UA.
        self.assertEqual("poi-context-u64",rows[0]["interpretation"])

    def test_room_parent_name_parser_and_repeat_fixture(self):
        fixture=json.loads((ROOT / "corpus" / "research" / "baseline-002-repeat-generation-v0.3.11.json").read_text(encoding="utf-8"))
        groups=fixture["logical_groups"]
        indices=[]
        for g in groups:
            idx=generation_baseline.room_index_from_parent_names(g.get("parent_node_names") or [])
            g["room_index"]=idx
            g["stream_order"]=g.get("generation_order")
            indices.append(idx)
        self.assertEqual(list(range(8)), sorted(indices))
        dead=[g for g in groups if g.get("room_kind")=="dead_end"]
        self.assertEqual(1,len(dead))
        self.assertEqual(5,dead[0]["room_index"])
        layout_sig, stream_sig, canonical=generation_baseline.layout_signatures(groups)
        self.assertNotEqual(layout_sig, stream_sig)
        self.assertEqual(list(range(8)), [g["room_index"] for g in canonical])
        self.assertEqual([1,15,10,3,4,0,1,1],[g["target_containers"] for g in canonical])

    def test_generation_measurement_summary_keeps_comparable_rows(self):
        fixture = json.loads((ROOT / "corpus" / "research" / "baseline-002-generation-fingerprint-v0.3.11.json").read_text(encoding="utf-8"))
        row = generation_measure.compact_row(fixture)
        self.assertEqual("00001A0004E84EFD", row["universe_address_hex"])
        self.assertEqual("CARGO_FLOATERS", row["preset"])
        self.assertEqual(7, row["main_rooms"])
        self.assertEqual(1, row["dead_end_rooms"])
        self.assertEqual(35, row["target_containers"])
        self.assertEqual(8, len(row["room_sequence"]))
        self.assertIn("layout_signature_sha256", row)

    def test_probe_contains_read_only_space_poi_context_hook(self):
        source=(ROOT / "mod" / "derelict_baseline_probe.py").read_text(encoding="utf-8")
        self.assertIn("@nms.cGcSpacePoiSiteComponent.GeneratePoiDescription.before", source)
        self.assertIn("poi-context-u64", source)
        self.assertIn("universe address", source)
        self.assertIn("_raw_u64_bits", source)
        self.assertIn("@nms.cGcSpacePoiSiteComponent.GeneratePoiDescription.after", source)
        self.assertIn("return_value_hex", source)
        self.assertIn("@nms.cGcSpacePoiSiteComponent.Prepare.before", source)
        self.assertIn("@nms.cGcSpacePoiSiteComponent.Prepare.after", source)
        self.assertIn("poi_prepare_scope_component_hexes", source)
        self.assertIn("@nms.cGcSpacePoiSiteComponent.OnActivate.before", source)
        self.assertIn("@nms.cGcSpacePoiSiteComponent.OnActivate.after", source)
        self.assertIn("@nms.cGcSpacePoiSiteComponent.AdvanceLifecycle.before", source)
        self.assertIn("@nms.cGcSpacePoiSiteComponent.AdvanceLifecycle.after", source)
        self.assertIn("poi_activation_scope_component_hexes", source)
        self.assertIn("poi_lifecycle_scope_component_hexes", source)
        self.assertIn("@nms.cTkResourceManager.AddResource.before", source)
        self.assertIn("descriptor_pointer_hex", source)
        self.assertIn("from pymhf.core.hooking import get_caller, on_key_pressed", source)
        self.assertGreaterEqual(source.count("@get_caller"), 2)
        self.assertIn("caller_return_offset_hex", source)
        self.assertIn("caller_code_window", source)
        self.assertIn("ReadProcessMemory", source)

    def test_overlay_shows_generation_room_measurement_line(self):
        status={
            "heartbeat_epoch":1000.0,"probe_version":"0.3.11","state":"recording","recording":True,
            "detail":"recording","blue_crates":0,"rooms":0,"room_zero_rooms":0,"vertical_transitions":0,"shuttle_bays":0,
            "engineering_marked":False,"engineering_module_class":"unknown","last_event":"",
            "generation_rooms":{"total_rooms_seen":8,"main_rooms_seen":7,"dead_end_rooms_seen":1,"room_parent_names_seen":8,"poi_context_arguments":["00001A0004E84EFD"],"poi_context_matches_universe_address":True},
        }
        view=overlay_mod.summarize_status(status,now_epoch=1000.5)
        self.assertIn("GEN ROOMS 8",view["generation"])
        self.assertIn("MAIN 7",view["generation"])
        self.assertIn("DEAD END 1",view["generation"])
        self.assertIn("POI-UA",view["generation"])
        self.assertIn("00001A0004E84EFD",view["generation"])

    def test_v0337_runtime_probe_captures_all_call_registers_at_shared_entry(self):
        probe=(ROOT / "mod" / "derelict_baseline_probe.py").read_text(encoding="utf-8")
        self.assertIn('PROBE_VERSION = "0.3.38"', probe)
        exact=probe.index('exact_external = self._logical_entry_external_match_for_descriptor(descriptor_ptr)')
        entry_capture=probe.index('phase="logical-entry-after-external-call"')
        root_add_capture=probe.index('phase="root-resource-add"', exact)
        self.assertLess(probe.index('def _trace_resource_descriptor_walk_entry'), entry_capture)
        self.assertLess(entry_capture, root_add_capture)
        self.assertIn('"capture_phase": phase', probe)
        self.assertIn('"capture_utc": _utc_now()', probe)
        self.assertIn('"external_owner_plus_0x10_capture_at_entry": frame.get("external_owner_plus_0x10_capture")', probe)
        self.assertIn('exact_external["owner_plus_0x10_capture_at_root_add"]', probe)
        self.assertIn('exact_external["owner_plus_0x10_capture_at_entry"] = entry_capture', probe)
        self.assertIn('"external_call_register_snapshot_at_entry": frame.get("external_call_register_snapshot")', probe)
        self.assertIn('"rcx_hex":', probe)
        self.assertIn('"rdx_hex": f"{owner_pointer:016X}"', probe)
        self.assertIn('"rdx_plus_0x10_capture": frame["external_owner_plus_0x10_capture"]', probe)
        self.assertIn('"external_call_register_snapshot_at_entry": exact.get("external_call_register_snapshot_at_entry")', probe)
        self.assertIn('"static_direct_reference_count": len(CURRENT_BUILD_LOGICAL_ENTRY_CALLER_RETURNS)', probe)
        self.assertIn('not 52 breakpoints', probe)
        self.assertIn('"root_dispatch_capture": self._root_dispatch_capture_payload()', probe)
        self.assertIn('"last_dungeon_root_owner_plus_0x10_capture": root_dispatch_capture', probe)
        self.assertIn('kernel32.ReadProcessMemory(', probe)
        self.assertNotIn('WriteProcessMemory', probe)
        persist = probe[probe.index('def _persist_root_event'):probe.index('def _persist_exact_root_caller')]
        self.assertIn('"universe_address_hex_at_capture": root_event.get("universe_address_hex_at_capture")', persist)
        self.assertIn('"runtime_metadata_at_capture": runtime_metadata', persist)
        self.assertIn('"root_event": root_event', persist)
        root_capture = probe.index('event["universe_address_hex_at_capture"] = runtime_metadata.get("universe_address_hex")')
        exact_persist = probe.index('self._persist_exact_root_caller(event, exact_external)')
        self.assertLess(root_capture, exact_persist)
        schema=json.loads((ROOT / "schema" / "live-status-v1.schema.json").read_text(encoding="utf-8"))
        self.assertIn("root_dispatch_capture",schema["properties"])
        self.assertIn("last_dungeon_root_owner_plus_0x10_capture",schema["properties"]["generation_rooms"]["properties"])

    def test_overlay_and_objective_show_real_owner_slot_capture(self):
        live={"root_dispatch_capture":{"captured":True,"slot_value_hex":"00007FF612345678","target_offset_hex":"01234567","target_identity":{"module_rva_hex":"01234567"}}}
        view=overlay_mod.summarize_status({"heartbeat_epoch":1000.0,"probe_version":"0.3.34","state":"ready","recording":False,**live},now_epoch=1000.5)
        self.assertIn("CAPTURED 00007FF612345678 -> NMS+01234567",view["root_dispatch"])
        snapshot={"lanes":[{"id":"runtime-dispatch","name":"Runtime-A","human_required":True,"surveyor_request":"Wait for Root dispatch +0x10 capture, then upload"}]}
        objective=overlay_mod.build_agent_objectives(snapshot,live,True)["objectives"][0]
        self.assertTrue(objective["complete"])
        self.assertTrue(objective["keep_game_open"])

    def test_overlay_exposes_root_resource_and_separates_pending_dispatch_capture(self):
        status={
            "heartbeat_epoch":1000.0,"probe_version":"0.3.33","state":"recording","recording":True,
            "generation_rooms":{"dungeon_root_resource_events_seen":2},
        }
        view=overlay_mod.summarize_status(status,now_epoch=1000.5)
        self.assertIn("MODELS/SPACE/POI/DUNGEON.SCENE.MBIN",view["root_resource"])
        self.assertIn("observed 2",view["root_resource"])
        self.assertIn("not captured",view["root_dispatch"].lower())
        self.assertIn("Runtime-A",view["root_dispatch"])
        probe=(ROOT / "mod" / "derelict_baseline_probe.py").read_text(encoding="utf-8")
        self.assertIn('"dungeon_root_resource_events_seen": dungeon_root_resource_events_seen',probe)
        self.assertIn('event_resource == DUNGEON_ROOT_SCENE',probe)

    def test_overlay_controls_and_capture_status_are_visible_in_controller(self):
        source=(ROOT / "tools" / "surveyor_controller.py").read_text(encoding="utf-8")
        self.assertIn('text="Start overlay"',source)
        self.assertIn('text="Stop overlay"',source)
        self.assertIn('"Root resource"',source)
        self.assertIn('"Root dispatch +0x10"',source)
        self.assertIn("OVERLAY_STOP_REQUEST.write_text",source)

    def test_seed_room_correlation_detects_repeat_address_stability(self):
        summary={"measurements":[
            {"universe_address_hex":"00001A0004E84EFD","preset":"CARGO_FLOATERS","target_containers":35,"reward_seed_hexes":["CE0669F299792E85"],"poi_seed_candidate_hexes":[],"layout_signature_sha256":"LAYOUT35","room_sequence":[]},
            {"universe_address_hex":"00001A0004E84EFD","preset":"CARGO_FLOATERS","target_containers":35,"reward_seed_hexes":["CE0669F299792E85"],"poi_seed_candidate_hexes":["00001A0004E84EFD"],"layout_signature_sha256":"LAYOUT35","room_sequence":[]},
            {"universe_address_hex":"0001550006607CAC","preset":"CARGO_FLOATERS","target_containers":51,"reward_seed_hexes":["1EE5E3C00986D42A"],"poi_seed_candidate_hexes":[],"layout_signature_sha256":"LAYOUT51","room_sequence":[]},
        ]}
        out=seed_room_correlation.analyze(summary)
        self.assertEqual(3,out["measurement_count"])
        self.assertEqual(2,out["unique_addresses"])
        g=next(x for x in out["address_groups"] if x["universe_address_hex"]=="00001A0004E84EFD")
        self.assertTrue(g["layout_stable_across_repeats"])
        self.assertTrue(g["reward_seed_stable_across_repeats"])
        self.assertTrue(g["poi_context_equals_universe_address"])

    def test_verified_51_fixture_exposes_dungeon_root_seed_candidate(self):
        fixture=json.loads((ROOT / "corpus" / "research" / "baseline-001-generation-fingerprint-v0.3.13.json").read_text(encoding="utf-8"))
        seeds=fixture.get("dungeon_root_seed_candidates") or []
        self.assertEqual(["00C9E8DF0327789E"],[x.get("seed_hex") for x in seeds])
        self.assertEqual("dungeon-root-resource-seed-candidate",fixture.get("layout_seed_status"))

    def test_51_repeat_confirms_same_room_multiset_with_full_room_indices(self):
        older=json.loads((ROOT / "corpus" / "research" / "baseline-001-generation-fingerprint-v0.3.13.json").read_text(encoding="utf-8"))
        repeat=json.loads((ROOT / "corpus" / "research" / "baseline-001-repeat-generation-v0.3.12.json").read_text(encoding="utf-8"))
        self.assertEqual(older.get("layout_multiset_signature_sha256"), repeat.get("layout_multiset_signature_sha256"))
        self.assertEqual(9,repeat.get("room_parent_index_coverage"))
        self.assertEqual(list(range(9)),[x.get("room_index") for x in repeat.get("canonical_room_sequence") or []])
        self.assertEqual(51,repeat.get("predicted_target_containers"))

    def test_generation_measurement_keeps_dungeon_root_seed(self):
        fixture=json.loads((ROOT / "corpus" / "research" / "baseline-001-generation-fingerprint-v0.3.13.json").read_text(encoding="utf-8"))
        row=generation_measure.compact_row(fixture)
        self.assertEqual(["00C9E8DF0327789E"],row.get("dungeon_root_seed_hexes"))

    def test_overlay_shows_dungeon_root_seed_candidate(self):
        status={
            "heartbeat_epoch":1000.0,"probe_version":"0.3.13","state":"recording","recording":True,
            "detail":"recording","blue_crates":0,"rooms":0,"room_zero_rooms":0,"vertical_transitions":0,"shuttle_bays":0,
            "engineering_marked":False,"engineering_module_class":"unknown","last_event":"",
            "generation_rooms":{"total_rooms_seen":9,"main_rooms_seen":7,"dead_end_rooms_seen":2,"room_parent_names_seen":9,"poi_context_arguments":["0001550006607CAC"],"poi_context_matches_universe_address":True,"last_dungeon_root_seed_hex":"00C9E8DF0327789E"},
        }
        view=overlay_mod.summarize_status(status,now_epoch=1000.5)
        self.assertIn("DUNGEON-SEED 00C9E8DF0327789E",view["generation"])

    def test_seed_room_correlation_tracks_dungeon_root_seed_stability(self):
        summary={"measurements":[
            {"universe_address_hex":"0001550006607CAC","target_containers":51,"reward_seed_hexes":["1EE5E3C00986D42A"],"dungeon_root_seed_hexes":["00C9E8DF0327789E"],"layout_multiset_signature_sha256":"LAYOUT51","room_sequence":[]},
            {"universe_address_hex":"0001550006607CAC","target_containers":51,"reward_seed_hexes":["1EE5E3C00986D42A"],"dungeon_root_seed_hexes":["00C9E8DF0327789E"],"layout_multiset_signature_sha256":"LAYOUT51","room_sequence":[]},
        ]}
        out=seed_room_correlation.analyze(summary)
        g=out["address_groups"][0]
        self.assertTrue(g["dungeon_root_seed_stable_across_repeats"])
        self.assertEqual(["00C9E8DF0327789E"],g["dungeon_root_seed_hexes"])
        self.assertEqual([],out["dungeon_root_seed_collisions_across_addresses"])

    def test_probe_filters_stale_poi_context_and_retains_dungeon_seed(self):
        source=(ROOT / "mod" / "derelict_baseline_probe.py").read_text(encoding="utf-8")
        self.assertIn("discarded_pre_session_poi_context_mismatches",source)
        self.assertIn("DUNGEON_SEED_RETENTION_SECONDS",source)
        self.assertIn("universe_address_hex_at_capture",source)

    def test_seed_room_correlation_requires_full_root_seed_coverage_for_stability(self):
        summary={"measurements":[
            {"universe_address_hex":"0001550006607CAC","dungeon_root_seed_hexes":["00C9E8DF0327789E"],"layout_multiset_signature_sha256":"L","room_sequence":[]},
            {"universe_address_hex":"0001550006607CAC","dungeon_root_seed_hexes":[],"layout_multiset_signature_sha256":"L","room_sequence":[]},
        ]}
        out=seed_room_correlation.analyze(summary)
        g=out["address_groups"][0]
        self.assertEqual(1,g["dungeon_root_seed_measurement_coverage"])
        self.assertIsNone(g["dungeon_root_seed_stable_across_repeats"])


    def test_resource_seed_lineage_keeps_order_and_ignores_zero_seeds(self):
        session={"trace":{"events":[
            {"kind":"resource_add","trace_sequence":8,"resource_name":"MODELS/SPACE/POI/DUNGEON/CARG/ROOM.SCENE.MBIN","primary_seed":{"seed_hex":"1111111111111111","use_seed_value":True}},
            {"kind":"resource_add","trace_sequence":7,"resource_name":"MODELS/SPACE/POI/DUNGEON.SCENE.MBIN","primary_seed":{"seed_hex":"2222222222222222","use_seed_value":True}},
            {"kind":"resource_find","trace_sequence":9,"resource_name":"MODELS/SPACE/POI/DUNGEON/EMPTY/X.SCENE.MBIN","primary_seed":{"seed_hex":"0000000000000000","use_seed_value":True}},
            {"kind":"resource_add","trace_sequence":10,"resource_name":"MODELS/PLANETS/IGNORED.SCENE.MBIN","primary_seed":{"seed_hex":"3333333333333333","use_seed_value":True}},
        ]}}
        out=generation_baseline.resource_seed_lineage(session)
        self.assertEqual("captured",out["status"])
        self.assertEqual(2,out["event_count"])
        self.assertEqual([7,8],[x["trace_sequence"] for x in out["events"]])
        self.assertEqual(["2222222222222222","1111111111111111"],out["unique_primary_seed_hexes"])
        self.assertEqual(64,len(out["ordered_signature_sha256"]))

    def test_generation_measurement_keeps_resource_seed_lineage_signature(self):
        row=generation_measure.compact_row({
            "session_id":"s","resource_seed_lineage":{
                "ordered_signature_sha256":"abc123",
                "unique_primary_seed_hexes":["A","B"],
            }
        })
        self.assertEqual("abc123",row["resource_seed_lineage_signature_sha256"])
        self.assertEqual(["A","B"],row["resource_seed_primary_hexes"])

    def test_seed_room_correlation_tracks_lineage_stability_when_fully_covered(self):
        summary={"measurements":[
            {"universe_address_hex":"A","resource_seed_lineage_signature_sha256":"SIG","room_sequence":[]},
            {"universe_address_hex":"A","resource_seed_lineage_signature_sha256":"SIG","room_sequence":[]},
        ]}
        out=seed_room_correlation.analyze(summary)
        group=out["address_groups"][0]
        self.assertTrue(group["resource_seed_lineage_stable_across_repeats"])
        self.assertEqual(2,group["resource_seed_lineage_measurement_coverage"])

    def test_probe_trace_events_have_monotonic_sequence_instrumentation(self):
        source=(ROOT / "mod" / "derelict_baseline_probe.py").read_text(encoding="utf-8")
        self.assertIn("self._trace_sequence += 1",source)
        self.assertIn('"trace_sequence": self._trace_sequence',source)


    def test_v0314_cross_address_dungeon_seed_discriminator_fixtures(self):
        baseline51=json.loads((ROOT / "corpus" / "research" / "baseline-001-repeat-generation-v0.3.13-reanalysis.json").read_text(encoding="utf-8"))
        baseline35=json.loads((ROOT / "corpus" / "research" / "baseline-002-generation-fingerprint-v0.3.13.json").read_text(encoding="utf-8"))
        older35=json.loads((ROOT / "corpus" / "research" / "baseline-002-generation-fingerprint-v0.3.12.json").read_text(encoding="utf-8"))
        seed51=(baseline51.get("dungeon_root_seed_candidates") or [])[0]["seed_hex"]
        seed35=(baseline35.get("dungeon_root_seed_candidates") or [])[0]["seed_hex"]
        self.assertEqual("00C9E8DF0327789E",seed51)
        self.assertEqual("9256392A2F5A74AC",seed35)
        self.assertNotEqual(seed51,seed35)
        self.assertEqual(51,baseline51.get("predicted_target_containers"))
        self.assertEqual(35,baseline35.get("predicted_target_containers"))
        self.assertEqual(older35.get("layout_multiset_signature_sha256"),baseline35.get("layout_multiset_signature_sha256"))

    def test_overlay_room_loot_view_prioritizes_human_readable_counts(self):
        status={
            "heartbeat_epoch":1000.0,"probe_version":"0.3.15","state":"recording","recording":True,
            "detail":"Entered derelict — recording started automatically","last_event":"",
            "generation_rooms":{
                "crate_index_status":"ready","salvage_crates_seen":31,"crew_footlockers_seen":4,"target_containers_seen":35,
                "total_rooms_seen":8,"main_rooms_seen":7,"dead_end_rooms_seen":1,"room_parent_names_seen":8,
                "rooms":[
                    {"room_index":0,"room_kind":"main_room","dominant_family":"BARRACKS","salvage_crates":0,"crew_footlockers":1,"target_containers":1},
                    {"room_index":1,"room_kind":"main_room","dominant_family":"CARG","salvage_crates":15,"crew_footlockers":0,"target_containers":15},
                    {"room_index":5,"room_kind":"dead_end","dominant_family":"BARRACKS","salvage_crates":0,"crew_footlockers":0,"target_containers":0},
                ],
            },
        }
        view=overlay_mod.summarize_status(status,now_epoch=1000.5)
        self.assertIn("LOOT SEEN 35",view["loot_summary"])
        self.assertIn("SALVAGE 31",view["loot_summary"])
        self.assertIn("FOOTLOCKERS 4",view["loot_summary"])
        self.assertIn("R1  CARGO",view["room_loot"])
        self.assertIn("15",view["room_loot"])
        self.assertIn("R5  DEAD END",view["room_loot"])

    def test_overlay_defaults_hide_research_noise_but_keep_rooms(self):
        self.assertTrue(overlay_mod.DEFAULT_VIEW_SETTINGS["show_rooms"])
        self.assertFalse(overlay_mod.DEFAULT_VIEW_SETTINGS["show_research"])
        self.assertFalse(overlay_mod.DEFAULT_VIEW_SETTINGS["show_position"])
        self.assertFalse(overlay_mod.DEFAULT_VIEW_SETTINGS["show_manual"])
        self.assertFalse(overlay_mod.DEFAULT_VIEW_SETTINGS["show_hotkeys"])

    def test_live_status_contract_has_per_room_loot(self):
        schema=json.loads((ROOT / "schema" / "live-status-v1.schema.json").read_text(encoding="utf-8"))
        generation=schema["properties"]["generation_rooms"]["properties"]
        self.assertIn("rooms",generation)
        self.assertIn("target_containers_seen",generation)
        room_props=generation["rooms"]["items"]["properties"]
        self.assertIn("salvage_crates",room_props)
        self.assertIn("crew_footlockers",room_props)
        self.assertIn("target_containers",room_props)

    def test_probe_uses_local_asset_index_for_live_room_loot(self):
        source=(ROOT / "mod" / "derelict_baseline_probe.py").read_text(encoding="utf-8")
        self.assertIn('"room-crate-index.json"',source)
        self.assertIn("def _load_live_crate_index",source)
        self.assertIn('"target_containers_seen"',source)
        self.assertIn('"rooms": room_rows',source)

    def test_repeat_35_v0314_confirms_root_seed_and_layout_again(self):
        previous=json.loads((ROOT / "corpus" / "research" / "baseline-002-generation-fingerprint-v0.3.13.json").read_text(encoding="utf-8"))
        repeat=json.loads((ROOT / "corpus" / "research" / "baseline-002-repeat-generation-v0.3.14.json").read_text(encoding="utf-8"))
        self.assertEqual(35,repeat["predicted_target_containers"])
        self.assertEqual(previous["layout_multiset_signature_sha256"],repeat["layout_multiset_signature_sha256"])
        self.assertEqual(previous["dungeon_root_seed_candidates"][0]["seed_hex"],repeat["dungeon_root_seed_candidates"][0]["seed_hex"])
        self.assertEqual("9256392A2F5A74AC",repeat["dungeon_root_seed_candidates"][0]["seed_hex"])

    def test_generation_analyzer_stamps_its_own_version(self):
        source=(ROOT / "tools" / "analyze_generation_baseline.py").read_text(encoding="utf-8")
        self.assertIn('ANALYSIS_TOOL_VERSION = "0.3.24"',source)
        self.assertIn('"analysis_tool_version":ANALYSIS_TOOL_VERSION',source)

    def test_resource_seed_context_lineage_widens_without_changing_dungeon_lineage(self):
        session={"trace":{"events":[
            {"kind":"resource_add","trace_sequence":5,"resource_name":"MODELS/SPACE/POI/ABANDONED/GENERATOR.SCENE.MBIN","primary_seed":{"seed_hex":"AAAAAAAAAAAAAAAA","use_seed_value":True}},
            {"kind":"resource_add","trace_sequence":6,"resource_name":"MODELS/SPACE/POI/DUNGEON.SCENE.MBIN","primary_seed":{"seed_hex":"BBBBBBBBBBBBBBBB","use_seed_value":True}},
            {"kind":"reward","trace_sequence":7,"resource_name":"MODELS/SPACE/POI/IGNORED.SCENE.MBIN","seed":{"seed_hex":"CCCCCCCCCCCCCCCC"}},
        ]}}
        dungeon=generation_baseline.resource_seed_lineage(session)
        context=generation_baseline.resource_seed_context_lineage(session)
        self.assertEqual(["BBBBBBBBBBBBBBBB"],dungeon["unique_primary_seed_hexes"])
        self.assertEqual(["AAAAAAAAAAAAAAAA","BBBBBBBBBBBBBBBB"],context["unique_primary_seed_hexes"])
        self.assertEqual("dungeon-only",dungeon["scope"])
        self.assertEqual("recorded-derelict-poi-context",context["scope"])

    def test_generation_measurement_keeps_seed_context_lineage_without_breaking_old_fields(self):
        row=generation_measure.compact_row({
            "session_id":"s",
            "resource_seed_lineage":{"ordered_signature_sha256":"old","unique_primary_seed_hexes":["ROOT"]},
            "resource_seed_context_lineage":{"ordered_signature_sha256":"wide","unique_primary_seed_hexes":["UPSTREAM","ROOT"]},
            "poi_generation_trace":{
                "description_return_hexes":["DERIVED"],
                "description_results":[{"return_matches_dungeon_root_seed":True}],
                "dungeon_root_inside_prepare":True,
                "dungeon_root_engine_caller_offsets":["00123456"],
                "dungeon_root_manager_caller_offsets":["00654321"],
            },
        })
        self.assertEqual("old",row["resource_seed_lineage_signature_sha256"])
        self.assertEqual(["ROOT"],row["resource_seed_primary_hexes"])
        self.assertEqual("wide",row["resource_seed_context_signature_sha256"])
        self.assertEqual(["UPSTREAM","ROOT"],row["resource_seed_context_primary_hexes"])
        self.assertEqual(["DERIVED"],row["poi_description_return_hexes"])
        self.assertTrue(row["poi_description_return_matches_root_seed"])
        self.assertTrue(row["dungeon_root_inside_poi_prepare"])
        self.assertFalse(row["dungeon_root_inside_poi_activation"])
        self.assertFalse(row["dungeon_root_inside_poi_lifecycle"])
        self.assertEqual(0,row["resource_manager_root_event_count"])
        self.assertEqual(["00123456"],row["dungeon_root_engine_caller_offsets"])
        self.assertEqual(["00654321"],row["dungeon_root_manager_caller_offsets"])


    def test_v0316_context_fixture_proves_address_echo_before_distinct_root(self):
        fixture=json.loads((ROOT / "corpus" / "research" / "baseline-002-repeat-generation-v0.3.16-context.json").read_text(encoding="utf-8"))
        self.assertEqual("0.3.16",fixture.get("analysis_tool_version"))
        self.assertEqual("00001A0004E84EFD",fixture.get("universe_address_hex"))
        context=fixture.get("resource_seed_context_lineage") or {}
        self.assertEqual(58,context.get("event_count"))
        events=context.get("events") or []
        address_events=[e for e in events if e.get("primary_seed_hex")=="00001A0004E84EFD"]
        self.assertEqual(11,len(address_events))
        self.assertTrue(all("HULK" in str(e.get("resource_name") or "") or "ABAND" in str(e.get("resource_name") or "") for e in address_events))
        root=(fixture.get("dungeon_root_seed_candidates") or [])[0].get("seed_hex")
        self.assertEqual("9256392A2F5A74AC",root)
        self.assertNotEqual(fixture.get("universe_address_hex"),root)

    def test_poi_generation_summary_correlates_return_and_prepare_scope(self):
        session={"trace":{"events":[
            {"kind":"space_poi_description","trace_sequence":1,"raw_argument_hex":"00001A0004E84EFD","poi_type_value":6,"component_address_hex":"0000000000001234"},
            {"kind":"space_poi_description_result","trace_sequence":2,"raw_argument_hex":"00001A0004E84EFD","poi_type_value":6,"component_address_hex":"0000000000001234","return_value_hex":"9256392A2F5A74AC"},
            {"kind":"space_poi_prepare","trace_sequence":3,"phase":"before","raw_argument_hex":"00001A0004E84EFD","component_address_hex":"0000000000001234"},
            {"kind":"resource_add","trace_sequence":4,"resource_name":"MODELS/SPACE/POI/DUNGEON.SCENE.MBIN","primary_seed":{"seed_hex":"9256392A2F5A74AC"},"poi_prepare_scope_component_hexes":["0000000000001234"]},
            {"kind":"space_poi_prepare","trace_sequence":5,"phase":"after","raw_argument_hex":"00001A0004E84EFD","component_address_hex":"0000000000001234","duration_ms":12.5},
        ]}}
        summary=generation_baseline.poi_generation_summary(
            session,
            "00001A0004E84EFD",
            [{"seed_hex":"9256392A2F5A74AC"}],
        )
        self.assertEqual("captured",summary["status"])
        self.assertEqual(["9256392A2F5A74AC"],summary["description_return_hexes"])
        self.assertTrue(summary["description_results"][0]["return_matches_dungeon_root_seed"])
        self.assertFalse(summary["description_results"][0]["return_matches_universe_address"])
        self.assertEqual(2,summary["prepare_event_count"])
        self.assertTrue(summary["dungeon_root_inside_prepare"])

    def test_overlay_research_line_shows_poi_description_return_candidate(self):
        status={
            "heartbeat_epoch":1000.0,"probe_version":"0.3.17","state":"recording","recording":True,
            "detail":"recording","blue_crates":0,"rooms":0,"room_zero_rooms":0,"vertical_transitions":0,"shuttle_bays":0,
            "engineering_marked":False,"engineering_module_class":"unknown","last_event":"",
            "generation_rooms":{
                "total_rooms_seen":8,"main_rooms_seen":7,"dead_end_rooms_seen":1,"room_parent_names_seen":8,
                "poi_context_arguments":["00001A0004E84EFD"],"poi_context_matches_universe_address":True,
                "last_poi_description_return_hex":"9256392A2F5A74AC",
                "last_dungeon_root_seed_hex":"9256392A2F5A74AC",
            },
        }
        view=overlay_mod.summarize_status(status,now_epoch=1000.5)
        self.assertIn("POI-RET 9256392A2F5A74AC",view["generation"])
        self.assertIn("DUNGEON-SEED 9256392A2F5A74AC",view["generation"])

    def test_v0315_reanalysis_fixture_has_recovered_dungeon_lineage(self):
        fixture=json.loads((ROOT / "corpus" / "research" / "baseline-002-repeat-generation-v0.3.15-reanalysis.json").read_text(encoding="utf-8"))
        self.assertEqual("0.3.15",fixture.get("analysis_tool_version"))
        self.assertEqual(35,fixture.get("predicted_target_containers"))
        self.assertEqual("captured",fixture.get("resource_seed_lineage_status"))
        self.assertEqual(["9256392A2F5A74AC"],(fixture.get("resource_seed_lineage") or {}).get("unique_primary_seed_hexes"))


    def test_v0317_poi_boundary_fixture_rules_out_return_and_prepare(self):
        fixture=json.loads((ROOT / "corpus" / "research" / "baseline-002-repeat-generation-v0.3.17-poi-boundary.json").read_text(encoding="utf-8"))
        self.assertEqual("0.3.17",fixture.get("analysis_tool_version"))
        self.assertEqual("0.3.17",fixture.get("probe_version"))
        self.assertEqual(35,fixture.get("predicted_target_containers"))
        trace=fixture.get("poi_generation_trace") or {}
        self.assertEqual(["000000F2834FD400"],trace.get("description_return_hexes"))
        self.assertTrue(all(x.get("return_value_hex")==x.get("component_address_hex") for x in trace.get("description_results") or []))
        self.assertTrue(all(not x.get("return_matches_universe_address") for x in trace.get("description_results") or []))
        self.assertTrue(all(not x.get("return_matches_dungeon_root_seed") for x in trace.get("description_results") or []))
        self.assertEqual(0,trace.get("prepare_event_count"))
        self.assertFalse(trace.get("dungeon_root_inside_prepare"))

    def test_poi_generation_summary_tracks_activation_lifecycle_and_manager_boundary(self):
        session={"trace":{"events":[
            {"kind":"space_poi_description","trace_sequence":1,"raw_argument_hex":"00001A0004E84EFD","component_address_hex":"0000000000001234"},
            {"kind":"space_poi_activate","trace_sequence":2,"phase":"before","raw_argument_hex":"00001A0004E84EFD","component_address_hex":"0000000000001234","root_node":-1},
            {"kind":"space_poi_lifecycle","trace_sequence":3,"phase":"after","raw_argument_hex":"00001A0004E84EFD","component_address_hex":"0000000000001234","call_index":7,"dungeon_root_added_during_call":True,"root_node":99},
            {"kind":"resource_add","trace_sequence":4,"resource_name":"MODELS/SPACE/POI/DUNGEON.SCENE.MBIN","descriptor_pointer_hex":"0000000000ABCDEF","caller_return_offset_hex":"00123456","caller_code_window":{"start_offset_hex":"00123426","return_offset_hex":"00123456","return_index":48,"byte_count":80,"bytes_hex":"90"*80},"primary_seed":{"seed_hex":"9256392A2F5A74AC"},"poi_activation_scope_component_hexes":[],"poi_lifecycle_scope_component_hexes":["0000000000001234"]},
            {"kind":"resource_manager_add","trace_sequence":5,"resource_name":"MODELS/SPACE/POI/DUNGEON.SCENE.MBIN","descriptor_pointer_hex":"0000000000ABCDEF","caller_return_offset_hex":"00654321","primary_seed":{"seed_hex":"9256392A2F5A74AC"},"poi_lifecycle_scope_component_hexes":["0000000000001234"]},
            {"kind":"space_poi_activate","trace_sequence":6,"phase":"after","raw_argument_hex":"00001A0004E84EFD","component_address_hex":"0000000000001234","root_node":99},
        ]}}
        summary=generation_baseline.poi_generation_summary(session,"00001A0004E84EFD",[{"seed_hex":"9256392A2F5A74AC"}])
        self.assertEqual(2,summary["activation_event_count"])
        self.assertEqual(1,summary["lifecycle_event_count"])
        self.assertFalse(summary["dungeon_root_inside_activation"])
        self.assertTrue(summary["dungeon_root_inside_lifecycle"])
        self.assertEqual(1,summary["resource_manager_root_event_count"])
        self.assertEqual("0000000000ABCDEF",summary["resource_manager_root_events"][0]["descriptor_pointer_hex"])
        self.assertEqual(["00123456"],summary["dungeon_root_engine_caller_offsets"])
        self.assertEqual(["00654321"],summary["dungeon_root_manager_caller_offsets"])
        self.assertEqual(48,summary["dungeon_root_resource_events"][0]["caller_code_window"]["return_index"])


    def test_v0318_resource_boundary_fixture_rules_out_lifecycle_and_proves_descriptor_identity(self):
        fixture=json.loads((ROOT / "corpus" / "research" / "baseline-002-repeat-generation-v0.3.18-resource-boundary.json").read_text(encoding="utf-8"))
        self.assertEqual("0.3.18",fixture.get("analysis_tool_version"))
        self.assertEqual("0.3.18",fixture.get("probe_version"))
        self.assertEqual(35,fixture.get("predicted_target_containers"))
        trace=fixture.get("poi_generation_trace") or {}
        self.assertEqual(0,trace.get("activation_event_count"))
        self.assertEqual(0,trace.get("lifecycle_event_count"))
        self.assertFalse(trace.get("dungeon_root_inside_activation"))
        self.assertFalse(trace.get("dungeon_root_inside_lifecycle"))
        outer=(trace.get("dungeon_root_resource_events") or [])[0]
        inner=(trace.get("resource_manager_root_events") or [])[0]
        self.assertEqual("9256392A2F5A74AC",outer.get("primary_seed_hex"))
        self.assertEqual(outer.get("primary_seed_hex"),inner.get("primary_seed_hex"))
        self.assertEqual("000001F08178ED28",outer.get("descriptor_pointer_hex"))
        self.assertEqual(outer.get("descriptor_pointer_hex"),inner.get("descriptor_pointer_hex"))
        self.assertTrue(inner.get("user_call"))

    def test_v0319_short_run_captures_engine_callsite_without_room_traversal(self):
        fixture=json.loads((ROOT / "corpus" / "research" / "baseline-002-short-generation-v0.3.19-caller.json").read_text(encoding="utf-8"))
        self.assertEqual("0.3.19",fixture.get("probe_version"))
        self.assertEqual(0,fixture.get("predicted_target_containers"))
        trace=fixture.get("poi_generation_trace") or {}
        outer=(trace.get("dungeon_root_resource_events") or [])[0]
        self.assertEqual("9256392A2F5A74AC",outer.get("primary_seed_hex"))
        self.assertEqual("00635115",outer.get("caller_return_offset_hex"))
        decoded=generation_baseline.decode_direct_callsite(outer.get("caller_code_window"))
        self.assertEqual("00635110",decoded.get("call_instruction_offset_hex"))
        self.assertEqual("01831A10",decoded.get("call_target_offset_hex"))
        self.assertEqual("RDI",decoded.get("descriptor_argument_source_register"))
        self.assertTrue(decoded.get("descriptor_passed_unchanged_to_engine"))
        self.assertEqual("01831AA3",(trace.get("resource_manager_root_events") or [])[0].get("caller_return_offset_hex"))

    def test_offline_caller_extractor_decodes_same_rel32_call(self):
        fixture=json.loads((ROOT / "corpus" / "research" / "baseline-002-short-generation-v0.3.19-caller.json").read_text(encoding="utf-8"))
        window=((fixture.get("poi_generation_trace") or {}).get("dungeon_root_resource_events") or [])[0].get("caller_code_window")
        decoded=caller_extract.decode_rel32_call(window)
        self.assertEqual(0x00635115,decoded.get("return_rva"))
        self.assertEqual(0x00635110,decoded.get("call_rva"))
        self.assertEqual(0x01831A10,decoded.get("target_rva"))

    def test_offline_caller_extractor_maps_rva_in_synthetic_pe(self):
        import struct
        with tempfile.TemporaryDirectory() as td:
            exe=Path(td)/"NMS.exe"
            blob=bytearray(0x800)
            blob[0:2]=b"MZ"
            struct.pack_into("<I",blob,0x3C,0x80)
            blob[0x80:0x84]=b"PE\0\0"
            # COFF: machine, sections, timestamp, sym ptr/count, opt size, characteristics
            struct.pack_into("<HHIIIHH",blob,0x84,0x8664,1,0x12345678,0,0,0xF0,0x22)
            sh=0x80+24+0xF0
            blob[sh:sh+8]=b".text\0\0\0"
            struct.pack_into("<IIII",blob,sh+8,0x300,0x1000,0x300,0x400)
            for i in range(0x300): blob[0x400+i]=i & 0xFF
            exe.write_bytes(blob)
            ts,sections=caller_extract.parse_pe_sections(exe)
            self.assertEqual(0x12345678,ts)
            win=caller_extract.read_rva_window(exe,sections,0x1100,16,16)
            self.assertEqual(".text",win["section_name"])
            self.assertEqual("000010F0",win["start_rva_hex"])
            self.assertEqual(32,win["byte_count"])
            self.assertEqual(bytes((i & 0xFF) for i in range(0xF0,0x110)).hex().upper(),win["bytes_hex"])


    def test_v0322_version_marker(self):
        self.assertEqual("0.3.60", (ROOT / "VERSION.txt").read_text(encoding="utf-8").strip())

    def test_v0322_probe_exposes_background_research_buttons(self):
        source=(ROOT / "mod" / "derelict_baseline_probe.py").read_text(encoding="utf-8")
        for label in (
            "Set up GitHub uploads",
            "Check for Surveyor update",
            "Install Surveyor update",
            "Measure derelict generation + upload",
            "Extract dungeon caller code + upload",
        ):
            self.assertIn(label, source)
        self.assertIn("threading.Thread", source)
        self.assertIn("CREATE_NO_WINDOW", source)

    def test_v0322_installer_persists_source_project_root(self):
        source=(ROOT / "Start-Surveyor.ps1").read_text(encoding="utf-8")
        self.assertIn("project-root.txt", source)
        self.assertIn("$ProjectRoot", source)
        for name in ("Install-and-Start.ps1", "Install-and-Start-NoOverlay.ps1"):
            launcher=(ROOT / name).read_text(encoding="utf-8")
            self.assertIn("Start-Surveyor.ps1", launcher)

    def test_v0322_cmd_pause_is_suppressible_for_gui_actions(self):
        for name in (
            "Measure-Derelict-Generation.cmd",
            "Extract-Dungeon-Caller-Code.cmd",
            "Analyze-Generation-Baseline.cmd",
            "Analyze-Existing-Crate-Assets.cmd",
            "Compare-Generation-Measurements.cmd",
        ):
            source=(ROOT / name).read_text(encoding="utf-8")
            if "pause" in source.lower():
                self.assertIn("NMSDS_NONINTERACTIVE", source)

    def test_v0322_powershell_explorer_launch_is_suppressible(self):
        for name in (
            "Measure-Derelict-Generation.ps1",
            "Analyze-Generation-Baseline.ps1",
            "Analyze-Dungeon-Generation.ps1",
            "Prepare-Crate-Assets.ps1",
        ):
            source=(ROOT / name).read_text(encoding="utf-8")
            if "Start-Process explorer.exe" in source:
                self.assertIn("NMSDS_NONINTERACTIVE", source)

    def test_v0322_github_helper_uses_cli_credentials_not_embedded_pat(self):
        source=(ROOT / "tools" / "github_integration.py").read_text(encoding="utf-8")
        self.assertIn('gh, "auth", "login"', source)
        self.assertIn('gh, "auth", "status"', source)
        self.assertNotIn("GITHUB_TOKEN=", source)
        self.assertNotIn("Authorization: token", source)

    def test_v0322_research_upload_is_single_git_commit_with_hash_manifest(self):
        source=(ROOT / "tools" / "github_integration.py").read_text(encoding="utf-8")
        self.assertIn('run-manifest.json', source)
        self.assertIn('hashlib.sha256', source)
        self.assertIn('git/trees', source)
        self.assertIn('git/commits', source)
        self.assertIn('git/refs/heads', source)

    def test_v0323_gui_helpers_never_launch_sys_executable_directly(self):
        source=(ROOT / "mod" / "derelict_baseline_probe.py").read_text(encoding="utf-8")
        self.assertIn("def _python_executable", source)
        self.assertIn('if not base.startswith("python")', source)
        self.assertNotIn('[sys.executable, str(helper), subcommand]', source)
        self.assertNotIn('"{sys.executable}" "{helper}" upload', source)

    def test_v0323_launchers_persist_real_python_executable(self):
        source=(ROOT / "Start-Surveyor.ps1").read_text(encoding="utf-8")
        self.assertIn("python-executable.txt", source)
        self.assertIn("os.path.abspath(sys.executable)", source)
        self.assertIn("Could not resolve the external Python executable safely", source)

    def test_v0324_workflow_logging_is_persistent_and_mirrored(self):
        source=(ROOT / "mod" / "derelict_baseline_probe.py").read_text(encoding="utf-8")
        for token in (
            "workflow-latest.log",
            "workflow-diagnostic-latest.txt",
            'self._write_log("workflow_started"',
            'self._write_log("workflow_completed"',
            'self._write_log("workflow_failed"',
            'self._write_log("workflow_exception"',
            "Open workflow log",
            "Open workflow diagnostic",
            "Run GitHub diagnostic",
        ):
            self.assertIn(token, source)
        self.assertIn('self._workflow_detail = f"Failed at step {failed_step}. Open workflow diagnostic."', source)

    def test_v0324_github_helper_has_step_logging_and_diagnose(self):
        source=(ROOT / "tools" / "github_integration.py").read_text(encoding="utf-8")
        for token in (
            "github-integration.log",
            "github-diagnostic-latest.txt",
            'sub.add_parser("diagnose")',
            '"gh_discovery"',
            '"auth_status"',
            '"github_api_failure"',
            '"upload_outputs"',
            '"helper_failure"',
        ):
            self.assertIn(token, source)
        self.assertNotIn("GITHUB_TOKEN=", source)
        self.assertNotIn("Authorization: token", source)

    def test_v0324_github_web_auth_is_visible_on_windows(self):
        source=(ROOT / "tools" / "github_integration.py").read_text(encoding="utf-8")
        self.assertIn("CREATE_NEW_CONSOLE", source)
        self.assertIn('"auth", "login"', source)
        self.assertIn('"--web"', source)

    def test_v0325_gui_detail_uses_multiple_short_rows(self):
        source=(ROOT / "mod" / "derelict_baseline_probe.py").read_text(encoding="utf-8")
        self.assertIn('@STRING("Workflow message 1")', source)
        self.assertIn('@STRING("Workflow message 2")', source)
        self.assertIn('@STRING("Workflow message 3")', source)
        self.assertIn('textwrap.wrap(text, width=52', source)

    def test_v0325_upload_workflows_do_not_chain_cmd_strings(self):
        source=(ROOT / "mod" / "derelict_baseline_probe.py").read_text(encoding="utf-8")
        self.assertIn("def _launch_workflow_steps", source)
        self.assertIn('("Run research command", action_command)', source)
        self.assertIn('("Upload generated evidence", [python_exe, str(helper), "upload", "--action", upload_action])', source)
        self.assertIn('return [self._powershell_executable(), "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(ps1)]', source)
        self.assertNotIn('chain = f\'call "{cmd_path}" && \'', source)
        self.assertNotIn("&&", source[source.index('def _project_action'):source.index('def _integration_action')])

    def test_v0325_workflow_logs_each_step_and_failed_step(self):
        source=(ROOT / "mod" / "derelict_baseline_probe.py").read_text(encoding="utf-8")
        for token in (
            'workflow_step_started',
            'workflow_step_completed',
            'workflow_step_failed',
            "Step: {step or 'single'}",
            'Failed at step {failed_step}',
        ):
            self.assertIn(token, source)



    def test_v0326_upstream_function_boundary_and_descriptor_flow(self):
        start=0x1000
        fn=0x1040
        call=0x10A0
        raw=bytearray(b"\x90"*0xC0)
        raw[0x38:0x40]=b"\xCC"*8
        prologue=bytes.fromhex("488954241048894C24085553564155")
        raw[0x40:0x40+len(prologue)]=prologue
        raw[0x50:0x53]=bytes.fromhex("488BF2")
        raw[0x60:0x67]=bytes.fromhex("0F108638010000")
        raw[0x70:0x77]=bytes.fromhex("4438B640010000")
        raw[0x80:0x87]=bytes.fromhex("488DBE28010000")
        evidence={
            "call_instruction_rva_hex": f"{call:08X}",
            "code_window": {"start_rva_hex":f"{start:08X}","bytes_hex":raw.hex().upper()},
        }
        boundary=upstream_extract.find_function_start_from_padding(evidence)
        self.assertEqual("00001040", boundary["function_start_rva_hex"])
        flow=upstream_extract.analyze_descriptor_flow(evidence,fn)
        self.assertTrue(flow["second_argument_copied_to_rsi"])
        self.assertEqual("00000128",flow["descriptor_offset_from_second_argument_hex"])
        self.assertEqual("00000138",flow["primary_seed_offset_from_second_argument_hex"])
        self.assertEqual("00000010",flow["primary_seed_offset_from_descriptor_hex"])
        self.assertEqual("00000140",flow["use_seed_flag_offset_from_second_argument_hex"])
        self.assertTrue(flow["seed_observed_before_root_add"])

    def test_v0326_rel32_xref_scan(self):
        section_rva=0x2000
        target=0x2300
        raw=bytearray(b"\x90"*0x400)
        for idx,opcode in ((0x20,0xE8),(0x80,0xE9)):
            source=section_rva+idx
            disp=target-(source+5)
            raw[idx]=opcode
            raw[idx+1:idx+5]=int(disp).to_bytes(4,"little",signed=True)
        refs=upstream_extract.find_rel32_references(bytes(raw),section_rva,target)
        self.assertEqual(["call-rel32","jump-rel32"],[x["kind"] for x in refs])
        self.assertEqual(["00002020","00002080"],[x["instruction_rva_hex"] for x in refs])

    def test_v0326_gui_and_upload_contract(self):
        probe=(ROOT / "mod" / "derelict_baseline_probe.py").read_text(encoding="utf-8")
        helper=(ROOT / "tools" / "github_integration.py").read_text(encoding="utf-8")
        self.assertIn("Extract upstream callers + upload",probe)
        self.assertIn("extract_nms_upstream_callers.py",probe)
        self.assertIn('"extract-upstream": [WORK / "dungeon-upstream-callers-latest.json"]',helper)
        self.assertTrue((ROOT / "Extract-Dungeon-Upstream-Callers.cmd").is_file())

    def test_v0330_standalone_controller_is_primary_interface(self):
        controller=(ROOT / "tools" / "surveyor_controller.py").read_text(encoding="utf-8")
        probe=(ROOT / "mod" / "derelict_baseline_probe.py").read_text(encoding="utf-8")
        self.assertIn('self.window.title("NMS Derelict Surveyor")', controller)
        self.assertIn('text="Start NMS"', controller)
        self.assertIn('text="Restart Surveyor"', controller)
        self.assertIn('Standalone controller', controller)
        self.assertIn('@no_gui\nclass DerelictBaselineProbe', probe)
        self.assertTrue((ROOT / "Start-Surveyor.cmd").is_file())
        self.assertTrue((ROOT / "Start-NMS.ps1").is_file())

    def test_v0330_restart_surveyor_never_restarts_nms(self):
        controller=(ROOT / "tools" / "surveyor_controller.py").read_text(encoding="utf-8")
        restart=(ROOT / "Restart-Surveyor.ps1").read_text(encoding="utf-8")
        restart_block=controller[controller.index('def restart_controller'):controller.index('def _integration')]
        self.assertIn('surveyor_controller.py', restart_block)
        self.assertNotIn('NMS.exe', restart_block)
        self.assertNotIn('Stop-Process', restart_block)
        self.assertIn('NMS untouched', restart)
        self.assertNotIn('Stop-Process', restart)
        self.assertNotIn('CloseMainWindow', restart)

    def test_v0330_start_nms_is_separate_from_start_surveyor(self):
        start_surv=(ROOT / "Start-Surveyor.ps1").read_text(encoding="utf-8")
        start_nms=(ROOT / "Start-NMS.ps1").read_text(encoding="utf-8")
        legacy=(ROOT / "Start-Derelict-Probe.cmd").read_text(encoding="utf-8")
        self.assertIn('surveyor_controller.py', start_surv)
        self.assertNotIn('pymhf run nmspy', start_surv)
        self.assertIn("pymhf.exe", start_nms)
        self.assertIn("run nmspy", start_nms)
        self.assertIn('Start-Surveyor.cmd', legacy)

    def test_v0335_start_nms_restores_classic_console_launch(self):
        start_nms=(ROOT / "Start-NMS.ps1").read_text(encoding="utf-8")
        controller=(ROOT / "tools" / "surveyor_controller.py").read_text(encoding="utf-8")
        self.assertIn("classic NMS.py / pyMHF console", start_nms)
        self.assertIn("pymhf.exe", start_nms)
        self.assertIn('"$pymhfExe" run nmspy', start_nms)
        self.assertIn("Start-Process -FilePath $env:ComSpec", start_nms)
        self.assertIn("importlib.metadata", start_nms)
        self.assertIn("pymhf.local.toml", start_nms)
        self.assertNotIn("Test-Runtime", start_nms)
        self.assertNotIn("Python.Python.3.12", start_nms)
        self.assertNotIn("import pymhf; import nmspy", start_nms)
        self.assertIn('CONTROLLER_VERSION = "0.3.60"', controller)
        self.assertTrue((ROOT / "Start-NMS-With-Overlay.cmd").is_file())

    def test_github_update_buttons_use_a_separate_geometry_parent(self):
        source=(ROOT / "tools" / "surveyor_controller.py").read_text(encoding="utf-8")
        section=source[source.index('updates_group, updates ='):source.index('extensions_group, extensions =')]
        self.assertIn('update_buttons = ttk.Frame(updates)', section)
        self.assertIn('self._button_grid(update_buttons, [', section)
        self.assertNotIn('self._button_grid(updates, [', section)


    def test_v0336_launcher_avoids_trailing_backslash_and_bom_toml(self):
        start_nms=(ROOT / "Start-NMS.ps1").read_text(encoding="utf-8")
        cmd=(ROOT / "Start-NMS.cmd").read_text(encoding="utf-8")
        overlay=(ROOT / "Start-NMS-With-Overlay.cmd").read_text(encoding="utf-8")
        self.assertIn('set "ROOT=%~dp0."', cmd)
        self.assertIn('set "ROOT=%~dp0."', overlay)
        self.assertIn('Resolve-Path -LiteralPath $ProjectRoot', start_nms)
        self.assertIn('System.Text.UTF8Encoding($false)', start_nms)
        self.assertIn("overlay-stop.request", start_nms)
        self.assertIn('[System.IO.File]::WriteAllText', start_nms)
        self.assertNotIn('exe = "$nmsToml"', start_nms)
        self.assertNotIn('@ | Set-Content -Path $pymhfCfg -Encoding UTF8', start_nms)

    def test_v0330_controller_survives_nms_and_monitors_heartbeat(self):
        controller=(ROOT / "tools" / "surveyor_controller.py").read_text(encoding="utf-8")
        overlay=(ROOT / "overlay" / "derelict_overlay.py").read_text(encoding="utf-8")
        self.assertIn('LIVE_STATUS = ROOT / "live-status.json"', controller)
        self.assertIn('summarize_status(live, nms_running=running)', controller)
        self.assertIn('heartbeat_epoch', overlay)
        self.assertIn('Offline — Start NMS when needed', overlay)
        self.assertIn('Surveyor stays connected while the game is open.', controller)

    def test_v0330_controller_exposes_exact_update_versions(self):
        controller=(ROOT / "tools" / "surveyor_controller.py").read_text(encoding="utf-8")
        helper=(ROOT / "tools" / "github_integration.py").read_text(encoding="utf-8")
        self.assertIn('Loaded controller', controller)
        self.assertIn('Downloaded/source', controller)
        self.assertIn('Available', controller)
        self.assertIn('NMSDS_REMOTE_VERSION=', helper)
        self.assertIn('NMSDS_STATUS=Installed Surveyor {version}', helper)
        self.assertIn('Restart Surveyor to load the standalone controller update', helper)
        self.assertIn('installed_file = ROOT / "installed-mod-file.txt"', helper)
        self.assertIn('install-derelict-farming', helper)
        self.assertIn('Install Derelict Farming archive', controller)

    def test_v0330_probe_accepts_standalone_controller_commands(self):
        probe=(ROOT / "mod" / "derelict_baseline_probe.py").read_text(encoding="utf-8")
        for token in (
            'controller-command.json',
            'controller-command-ack.json',
            'def _poll_controller_command',
            'force_start_session',
            'stop_session',
            'undo_last_marker',
            'write_diagnostic_snapshot',
            'self._poll_controller_command(now)',
        ):
            self.assertIn(token, probe)

    def test_v0330_version(self):
        self.assertEqual("0.3.60", (ROOT / "VERSION.txt").read_text(encoding="utf-8").strip())
        self.assertEqual("0.3.33", seed_function.TOOL_VERSION)

    def test_v0328_seed_function_relrefs_classify_recursion(self):
        base=0x1000
        begin=0x1100
        end=0x1200
        raw=bytearray(b"\x90"*0x400)
        for src in (0x1080,0x1150):
            i=src-base
            raw[i]=0xE8
            raw[i+1:i+5]=(begin-(src+5)).to_bytes(4,"little",signed=True)
        refs=seed_function.find_rel32_refs(bytes(raw),base,begin,begin,end)
        self.assertEqual(2,len(refs))
        self.assertFalse(refs[0]["source_inside_target_function"])
        self.assertTrue(refs[1]["source_inside_target_function"])

    def test_v0328_seed_function_detects_common_seed_write(self):
        begin=0x5000
        raw=bytearray(b"\x90"*0x80)
        raw[0x10:0x17]=bytes.fromhex("48898638010000")
        raw[0x30:0x37]=bytes.fromhex("0F108638010000")
        refs=seed_function.scan_disp_references(bytes(raw),begin)
        seedrefs=[x for x in refs if x["field"]=="primary_seed"]
        self.assertEqual(2,len(seedrefs))
        self.assertEqual(1,sum(1 for x in seedrefs if x["possible_memory_write"]))

    def test_v0328_gui_and_upload_contract(self):
        probe=(ROOT / "mod" / "derelict_baseline_probe.py").read_text(encoding="utf-8")
        helper=(ROOT / "tools" / "github_integration.py").read_text(encoding="utf-8")
        self.assertIn("Analyze seed function + upload",probe)
        self.assertIn("analyze_nms_seed_function.py",probe)
        self.assertIn('"analyze-seed-function": [WORK / "dungeon-seed-function-analysis-latest.json"]',helper)
        self.assertTrue((ROOT / "Analyze-Dungeon-Seed-Function.cmd").is_file())

    def test_v0331_four_cc_boundary_beats_older_helper(self):
        start=0x1000
        call=0x1200
        raw=bytearray(b"\x90"*0x240)
        raw[0x40:0x48]=b"\xCC"*8
        raw[0x48:0x57]=bytes.fromhex("488954241048894C24085553564155")
        raw[0xB0:0xB4]=b"\xCC"*4
        raw[0xB4:0xC3]=bytes.fromhex("488954241048894C24085553564155")
        evidence={
            "call_instruction_rva_hex": f"{call:08X}",
            "code_window": {"start_rva_hex":f"{start:08X}","bytes_hex":raw.hex().upper()},
        }
        boundary=upstream_extract.find_function_start_from_padding(evidence)
        self.assertEqual("000010B4",boundary["function_start_rva_hex"])
        self.assertEqual(4,boundary["padding_byte_count"])

    def test_v0331_seed_analyzer_distinguishes_fragment_from_logical_entry(self):
        source=(ROOT / "tools" / "analyze_nms_seed_function.py").read_text(encoding="utf-8")
        self.assertIn('"root_runtime_fragment":rf', source)
        self.assertIn('"logical_function_entry": logical', source)
        self.assertIn('Root fragment is logical entry', source)

    def test_v0332_runtime_entry_trace_is_descriptor_correlated_and_read_only(self):
        probe=(ROOT / "mod" / "derelict_baseline_probe.py").read_text(encoding="utf-8")
        for token in (
            "_resource_descriptor_walk_entry",
            "_trace_resource_descriptor_walk_entry",
            "_logical_entry_matches_for_descriptor",
            'event["logical_entry_matches"]',
            'event["logical_entry_nearest_caller_return_offset_hex"]',
            "ReadProcessMemory",
        ):
            self.assertIn(token, probe)
        self.assertNotIn("WriteProcessMemory", probe)

    def test_v0332_baseline_surfaces_exact_logical_entry_caller(self):
        source=(ROOT / "tools" / "analyze_generation_baseline.py").read_text(encoding="utf-8")
        controller=(ROOT / "tools" / "surveyor_controller.py").read_text(encoding="utf-8")
        overlay=(ROOT / "overlay" / "derelict_overlay.py").read_text(encoding="utf-8")
        self.assertIn('"dungeon_logical_entry_caller_offsets"', source)
        self.assertIn('"logical_entry_nearest_caller_return_offset_hex"', source)
        self.assertIn('Exact root caller', controller)
        self.assertIn('last_dungeon_logical_entry_caller_offset_hex', overlay)


    def test_v0333_recursive_lineage_keeps_external_origin(self):
        probe=(ROOT / "mod" / "derelict_baseline_probe.py").read_text(encoding="utf-8")
        self.assertIn("self._logical_entry_tls = threading.local()", probe)
        self.assertIn("external_origin_caller_return_offset_hex", probe)
        self.assertIn("recursion_depth", probe)
        self.assertIn("_trace_resource_descriptor_walk_entry_after", probe)
        self.assertIn("stack.pop()", probe)
        self.assertIn("resolved_external_caller_return_offset_hex", probe)

    def test_v0333_all_52_callers_are_observed_in_one_hook(self):
        probe=(ROOT / "mod" / "derelict_baseline_probe.py").read_text(encoding="utf-8")
        self.assertIn("CURRENT_BUILD_LOGICAL_ENTRY_CALLER_RETURNS", probe)
        self.assertIn("CURRENT_BUILD_RECURSIVE_CALL_RETURN_RVA = 0x00634C63", probe)
        self.assertIn("_logical_entry_caller_hits", probe)
        self.assertIn("_logical_entry_external_match_for_descriptor", probe)
        self.assertIn('"all-callers-single-hook-exact-descriptor-correlation" if exact else', probe)
        self.assertNotIn("WriteProcessMemory", probe)

    def test_v0333_exact_external_caller_is_persisted_and_uploaded(self):
        probe=(ROOT / "mod" / "derelict_baseline_probe.py").read_text(encoding="utf-8")
        helper=(ROOT / "tools" / "github_integration.py").read_text(encoding="utf-8")
        analyzer=(ROOT / "tools" / "analyze_generation_baseline.py").read_text(encoding="utf-8")
        self.assertIn("exact-root-caller-latest.json", probe)
        self.assertIn('logical_entry_exact_external_caller_return_offset_hex', probe)
        self.assertIn('logical_entry_exact_external_caller_return_offset_hex', analyzer)
        self.assertIn('WORK / "exact-root-caller-latest.json"', helper)

    def test_crash_recovery_journals_events_and_preserves_pending_root_event(self):
        probe=(ROOT / "mod" / "derelict_baseline_probe.py").read_text(encoding="utf-8")
        controller=(ROOT / "tools" / "surveyor_controller.py").read_text(encoding="utf-8")
        self.assertIn('self._append_capture_journal(event)', probe)
        self.assertIn('os.fsync(fh.fileno())', probe)
        self.assertIn('self._atomic_write_json(self._root_event_path, payload)', probe)
        self.assertIn('"root-event-saved-caller-correlation-pending"', probe)
        self.assertIn('self._persist_root_event(event)', probe)
        self.assertIn('def _maybe_auto_upload_root_event(self)', controller)
        self.assertIn('"all-saved-evidence", "--only-if-changed"', controller)
        self.assertIn("AUTO_EVIDENCE_UPLOAD_INTERVAL_SECONDS = 30.0", controller)
        self.assertIn("recovery_evidence_last_upload >= AUTO_EVIDENCE_UPLOAD_INTERVAL_SECONDS", controller)

    def test_upload_all_discovers_root_event_and_capture_journals(self):
        with tempfile.TemporaryDirectory() as temp:
            original_root, original_work = github_integration.ROOT, github_integration.WORK
            try:
                github_integration.ROOT = Path(temp)
                github_integration.WORK = Path(temp) / "asset-work-v1"
                github_integration.WORK.mkdir()
                root_event = github_integration.WORK / "root-event-latest.json"
                root_event.write_text("{}", encoding="utf-8")
                journal = Path(temp) / "capture-journal-test.jsonl"
                journal.write_text('{"kind":"resource_add"}\n', encoding="utf-8")
                paths, producers = github_integration.all_saved_evidence_outputs()
                self.assertIn(root_event, paths)
                self.assertIn(journal, paths)
                self.assertIn("runtime-probe", producers[str(root_event.resolve())])
            finally:
                github_integration.ROOT, github_integration.WORK = original_root, original_work

    def test_v0333_controller_exposes_all_at_once_progress(self):
        controller=(ROOT / "tools" / "surveyor_controller.py").read_text(encoding="utf-8")
        overlay=(ROOT / "overlay" / "derelict_overlay.py").read_text(encoding="utf-8")
        self.assertIn('Caller scan', controller)
        self.assertIn('Exact root caller', controller)
        self.assertIn('Watching all {candidate_count} refs', overlay)
        self.assertIn('last_dungeon_logical_entry_exact_external_caller_offset_hex', overlay)


    def test_v0337_exact_root_caller_decodes_direct_call(self):
        base=0x1000
        ret=0x1020
        raw=bytearray(b"\x90"*0x80)
        call=ret-5
        target=0x1080
        raw[call-base]=0xE8
        raw[call-base+1:call-base+5]=(target-ret).to_bytes(4,"little",signed=True)
        result=exact_root_extract.decode_call_ending_at(bytes(raw),base,ret)
        self.assertEqual("decoded",result["status"])
        self.assertEqual("call-rel32",result["kind"])
        self.assertEqual("0000101B",result["instruction_rva_hex"])
        self.assertEqual("00001080",result["target_rva_hex"])

    def test_v0337_exact_root_caller_decodes_rip_indirect_call(self):
        base=0x2000
        ret=0x2046
        raw=bytearray(b"\x90"*0x100)
        start=ret-base-6
        raw[start:start+6]=bytes.fromhex("FF15 34000000")
        result=exact_root_extract.decode_call_ending_at(bytes(raw),base,ret)
        self.assertEqual("decoded",result["status"])
        self.assertEqual("call-indirect-ff2",result["kind"])
        self.assertEqual("0000207A",result["pointer_slot_rva_hex"])

    def test_v0337_exact_root_caller_workflow_is_exposed(self):
        controller=(ROOT / "tools" / "surveyor_controller.py").read_text(encoding="utf-8")
        helper=(ROOT / "tools" / "github_integration.py").read_text(encoding="utf-8")
        self.assertTrue((ROOT / "Extract-Exact-Root-Caller-Code.cmd").is_file())
        self.assertTrue((ROOT / "tools" / "extract_exact_root_caller_code.py").is_file())
        self.assertIn("Extract exact root caller + upload",controller)
        self.assertIn("extract-exact-root-caller-code.cmd",controller)
        self.assertIn('"extract-exact-root-caller": [WORK / "exact-root-caller-code-latest.json"]',helper)


if __name__ == "__main__":
    unittest.main()

class TestResolveExactRootVtable(unittest.TestCase):
    def test_vtable_tool_is_wired(self):
        root = Path(__file__).resolve().parents[1]
        self.assertTrue((root / "tools" / "resolve_exact_root_vtable.py").is_file())
        self.assertTrue((root / "Resolve-Exact-Root-VTable.cmd").is_file())
        controller = (root / "tools" / "surveyor_controller.py").read_text(encoding="utf-8")
        helper = (root / "tools" / "github_integration.py").read_text(encoding="utf-8")
        self.assertIn("Resolve root vtable + upload", controller)
        self.assertIn("resolve-exact-root-vtable.cmd", controller)
        self.assertIn('"resolve-root-vtable": [WORK / "exact-root-vtable-latest.json"]', helper)

    def test_vtable_parser_helpers(self):
        import importlib.util
        root = Path(__file__).resolve().parents[1]
        spec = importlib.util.spec_from_file_location("resolve_exact_root_vtable", root / "tools" / "resolve_exact_root_vtable.py")
        mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
        self.assertEqual(mod.DEFAULT_TARGET_RVA, 0x00634BC0)
        self.assertEqual(mod.DEFAULT_VIRTUAL_SLOT, 0x10)
