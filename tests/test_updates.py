"""APT update counting tests: respect Ubuntu's phased-update policy."""
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "monitor.py"
spec = importlib.util.spec_from_file_location("ubuntu_monitor", SCRIPT)
monitor = importlib.util.module_from_spec(spec)
spec.loader.exec_module(monitor)

LISTING = """Listing...
openssl/noble-updates 3.0.2-2ubuntu1 amd64 [upgradable from: 3.0.2-2ubuntu0]
phasedpkg/noble-updates 2.0-1 amd64 [upgradable from: 1.0-1]
heldpkg/noble-updates 4.0-1 amd64 [upgradable from: 3.0-1]
"""


class UpdateCountingTests(unittest.TestCase):
    @staticmethod
    def completed(stdout, code=0):
        return SimpleNamespace(stdout=stdout, returncode=code)

    def test_phased_and_kept_back_not_actionable(self):
        def mock_run(argv, seconds=8):
            if argv[0] == "apt":
                return self.completed(LISTING)
            return self.completed("Inst openssl [3.0.2-2ubuntu0] (3.0.2-2ubuntu1 Ubuntu:24.04/noble-updates [amd64])\n")
        with patch.object(monitor, "run", side_effect=mock_run):
            count, ready, deferred, other, total = monitor.pending_updates()
        self.assertEqual((count, deferred, total), (1, 2, 3))
        self.assertEqual([p["package"] for p in ready], ["openssl"])
        self.assertEqual({p["package"] for p in other}, {"phasedpkg", "heldpkg"})

    def test_only_phased_means_zero_actionable(self):
        with patch.object(monitor, "run", side_effect=[
            self.completed(LISTING),
            self.completed("0 upgraded, 0 newly installed, 0 to remove and 3 not upgraded.\n"),
        ]):
            count, ready, deferred, other, total = monitor.pending_updates()
        self.assertEqual(count, 0)
        self.assertEqual(ready, [])
        self.assertEqual((deferred, total), (3, 3))

    def test_failed_simulation_is_unknown_not_zero(self):
        with patch.object(monitor, "run", side_effect=[
            self.completed(LISTING),
            self.completed("", 100),
        ]):
            count, ready, deferred, details, total = monitor.pending_updates()
        self.assertIsNone(count)
        self.assertIsNone(deferred)
        self.assertIsNone(total)

    def test_multiarch_package_matched(self):
        listing = "libfoo:amd64/noble-updates 2.0 amd64 [upgradable from: 1.0]\n"
        with patch.object(monitor, "run", side_effect=[
            self.completed(listing),
            self.completed("Inst libfoo:amd64 [1.0] (2.0 Ubuntu [amd64])\n"),
        ]):
            count, ready, deferred, _, total = monitor.pending_updates()
        self.assertEqual((count, deferred, total), (1, 0, 1))
        self.assertEqual(ready[0]["package"], "libfoo:amd64")


if __name__ == "__main__":
    unittest.main()
