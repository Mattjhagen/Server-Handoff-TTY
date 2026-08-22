import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from command_center import watcher


class WatcherTests(unittest.TestCase):
    def worker(self, directory):
        return {"id":"dev","enabled":True,"auto_restart":False,"process_marker":"unique-marker",
                "report_path":str(Path(directory)/"report"),"log_path":str(Path(directory)/"log"),
                "stale_after_seconds":60}

    @mock.patch("command_center.watcher._find_process", return_value=123)
    def test_healthy_requires_process_and_fresh_log(self, _process):
        with tempfile.TemporaryDirectory() as directory:
            log = Path(directory)/"log"; log.write_text("progress")
            status = watcher.evaluate(self.worker(directory), {}, time.time())
            self.assertEqual(status.verdict, "HEALTHY")

    @mock.patch("command_center.watcher._find_process", return_value=0)
    def test_recent_exit_is_degraded_not_failed(self, _process):
        with tempfile.TemporaryDirectory() as directory:
            log = Path(directory)/"log"; log.write_text("saved")
            status = watcher.evaluate(self.worker(directory), {}, time.time())
            self.assertEqual(status.verdict, "DEGRADED")

    def test_policy_permissions_are_enforced(self):
        with tempfile.TemporaryDirectory() as directory:
            policy=Path(directory)/"policy.json"; policy.write_text('{"workers":[]}'); policy.chmod(0o644)
            with self.assertRaises(SystemExit):
                watcher.main(["--policy",str(policy),"--once"])


if __name__ == "__main__":
    unittest.main()
