"""Unit tests for the root-owned maintenance helper; no APT commands are run."""
import importlib.util
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from types import SimpleNamespace

HELPER_PATH = Path(__file__).parents[1] / "scripts" / "maintenance_helper.py"
spec = importlib.util.spec_from_file_location("maintenance_helper", HELPER_PATH)
helper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helper)


class MaintenanceTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        base = Path(self.temp.name)
        self.patches = [
            patch.object(helper, "STATE_DIR", base),
            patch.object(helper, "STATE_FILE", base / "maintenance.json"),
            patch.object(helper, "LOCK_FILE", base / "maintenance.lock"),
        ]
        for replacement in self.patches:
            replacement.start()
            self.addCleanup(replacement.stop)

    def test_rejects_unsupported_action(self):
        with patch.object(helper.os, "geteuid", return_value=0):
            with patch.object(helper.sys, "argv", ["helper", "arbitrary-command"]):
                with self.assertRaisesRegex(ValueError, "Unsupported"):
                    helper.main()

    def test_check_queues_systemd_job_without_shell(self):
        with patch.object(helper.subprocess, "run", return_value=SimpleNamespace(returncode=0)) as run:
            response = helper.start_job("check")
        self.assertTrue(response["accepted"])
        args = run.call_args.args[0]
        self.assertEqual(args[0], "/usr/bin/systemd-run")
        self.assertIn("worker", args)
        self.assertIn("check", args)
        self.assertFalse(run.call_args.kwargs.get("shell", False))
        self.assertEqual(json.loads(helper.STATE_FILE.read_text())["state"], "queued")

    def test_worker_records_success(self):
        unit = "ha-ubuntu-apt-1234-5678.service"
        helper.save_state({"unit": unit, "state": "queued", "operation": "install"})
        with patch.object(helper.subprocess, "run", return_value=SimpleNamespace(returncode=0)) as run:
            helper.execute_worker("install", unit)
        self.assertEqual(helper.read_state()["state"], "success")
        self.assertEqual(run.call_count, 2)
        self.assertEqual(run.call_args_list[0].args[0][1], "update")
        self.assertEqual(run.call_args_list[1].args[0][-1], "upgrade")

    def test_worker_rejects_unregistered_unit(self):
        with self.assertRaisesRegex(ValueError, "not scheduled"):
            helper.execute_worker("install", "ha-ubuntu-apt-1234-5678.service")

    def test_reboot_blocked_during_job(self):
        helper.save_state({"state": "running", "unit": "ha-ubuntu-apt-1234-5678.service"})
        with patch.object(helper, "active", return_value=True):
            with self.assertRaisesRegex(ValueError, "blocked"):
                helper.reboot()


if __name__ == "__main__":
    unittest.main()
