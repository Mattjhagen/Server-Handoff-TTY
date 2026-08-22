import json
import tempfile
import time
import unittest
import threading
import urllib.request
from pathlib import Path
from unittest import mock

from command_center.webui.config import NodeConfig, load_webui_config
from command_center.webui.sanitize import basename_only, sanitize_text
from command_center.webui.todos import TodoCache, parse_todos
from command_center.webui.workflow import WorkflowError, is_forward, validate_state
from command_center.webui.config import WebUIConfig
from command_center.webui.service import build_server
from command_center.webui.assistant import ask, live_status


class SanitizeTests(unittest.TestCase):
    def test_removes_ansi_controls_and_caps(self):
        self.assertEqual(sanitize_text("\x1b[31mhello\x00\x1b[0m", 20), "hello")
        self.assertEqual(sanitize_text("abcdefgh", 5), "abcd…")

    def test_process_is_basename_without_arguments(self):
        self.assertEqual(basename_only("/snap/bin/opencode run --token secret"), "opencode")


class TodoTests(unittest.TestCase):
    def test_parse_states_and_sanitize(self):
        raw = json.dumps({"agent_id":"dev-r510","updated_at_epoch_s":100,"items":[
            {"status":"active","label":"Build\x1b[31m UI","activity":"writing"},
            {"status":"unknown","label":"Later"}]})
        panel = parse_todos(raw, stale_after_s=50, now_s=120)
        self.assertEqual(panel.items[0].label, "Build UI")
        self.assertEqual(panel.items[0].glyph, "•")
        self.assertEqual(panel.items[1].status, "pending")
        self.assertFalse(panel.stale)

    def test_cache_survives_empty_live_state(self):
        with tempfile.TemporaryDirectory() as directory:
            cache = TodoCache(Path(directory))
            panel = parse_todos(json.dumps({"agent_id":"a","updated_at_epoch_s":10,
                "items":[{"status":"active","label":"Work"}]}), stale_after_s=5, now_s=10)
            cache.store("a", panel)
            restored = TodoCache(Path(directory)).load("a")
            self.assertEqual(restored.items[0].label, "Work")
            self.assertEqual(restored.source, "cached")


class WorkflowTests(unittest.TestCase):
    def test_only_next_stage_or_intake(self):
        self.assertTrue(is_forward("development", "security-review"))
        self.assertTrue(is_forward("security-review", "intake"))
        self.assertFalse(is_forward("development", "merged"))
        with self.assertRaises(WorkflowError):
            validate_state("finished-ish")


class ConfigTests(unittest.TestCase):
    def test_agent_identity_is_independent_from_card_id(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "webui.toml"
            path.write_text('[[nodes]]\nnode_id="r510-dev"\nagent_id="dev-r510"\nrole="Developer"\nhost_alias="R510"\nssh_destination="r510"\n')
            cfg, warnings = load_webui_config(path, enforce_permissions=False)
            self.assertFalse(warnings)
            self.assertEqual(cfg.nodes[0].agent_id, "dev-r510")


class ServiceTests(unittest.TestCase):
    def test_health_api_and_csp(self):
        server = build_server(WebUIConfig(host="127.0.0.1", port=0, demo_mode=True))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            base = f"http://127.0.0.1:{server.server_address[1]}"
            with urllib.request.urlopen(base + "/healthz", timeout=2) as response:
                self.assertEqual(response.read(), b"ok")
                self.assertIn("default-src 'self'", response.headers["Content-Security-Policy"])
            with urllib.request.urlopen(base + "/api/state", timeout=2) as response:
                state = json.load(response)
                self.assertEqual(state["schema"], "server-handoff-dashboard-state/v1")
                self.assertEqual(len(state["nodes"]), 4)
            with urllib.request.urlopen(base + "/manifest.webmanifest", timeout=2) as response:
                manifest = json.load(response)
                self.assertEqual(response.headers["Content-Type"], "application/manifest+json; charset=utf-8")
                self.assertEqual(manifest["display"], "standalone")
            with urllib.request.urlopen(base + "/sw.js", timeout=2) as response:
                self.assertEqual(response.headers["Service-Worker-Allowed"], "/")
                self.assertIn(b"server-handoff-shell", response.read())
        finally:
            server.shutdown()
            server.server_close()

    def test_assistant_safe_ui_command_needs_no_model(self):
        reply = ask("show r410", {})
        self.assertEqual(reply.ui_action, "focus:r410-sec")
        self.assertIn("R410", reply.answer)

    def test_live_status_summarizes_sanitized_snapshot_without_model(self):
        status = live_status({
            "github_reachable": True,
            "github_stale": False,
            "workflow": {"current_stage": "development", "state": "working", "item_label": "Northstar"},
            "nodes": [
                {"host_alias": "T310", "status": "reachable", "opencode_state": "idle"},
                {"host_alias": "R510", "status": "reachable", "opencode_state": "working"},
                {"host_alias": "R410", "status": "offline", "opencode_state": "idle"},
            ],
            "queue": [{"state": "blocked"}],
        })
        self.assertIn("development / working — Northstar", status)
        self.assertIn("R410 not healthy", status)
        self.assertIn("1 blocked queue item", status)
        self.assertIn("Active worker: R510", status)


if __name__ == "__main__":
    unittest.main()
