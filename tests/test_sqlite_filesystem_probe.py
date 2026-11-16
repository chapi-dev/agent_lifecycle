"""Tests for the two-client SQLite filesystem probe."""

import subprocess
import sys
import tempfile
import unittest
import uuid
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "verify_sqlite_filesystem.py"


class SharedProbeTests(unittest.TestCase):
    def test_two_independent_processes_complete_and_clean_up(self):
        with tempfile.TemporaryDirectory() as directory:
            run_id = uuid.uuid4().hex
            base = [sys.executable, str(SCRIPT), "--run-id", run_id, "--timeout", "10"]
            coordinator = subprocess.Popen(
                [*base, "--role", "coordinator", directory],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            )
            try:
                peer = subprocess.run(
                    [*base, "--role", "peer", directory],
                    capture_output=True, text=True, timeout=30,
                )
                stdout, stderr = coordinator.communicate(timeout=30)
            finally:
                if coordinator.poll() is None:
                    coordinator.kill()
                    coordinator.communicate()
            self.assertEqual(peer.returncode, 0, peer.stderr)
            self.assertEqual(coordinator.returncode, 0, stderr)
            self.assertIn("PASS", stdout)
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_missing_peer_fails_and_retains_files(self):
        with tempfile.TemporaryDirectory() as directory:
            run_id = uuid.uuid4().hex
            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--role", "coordinator",
                 "--run-id", run_id, "--timeout", "0.2", directory],
                capture_output=True, text=True, timeout=10,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Timed out waiting for peer-ready", result.stderr)
            self.assertTrue((Path(directory) / f"sqlite-probe-peer-{run_id}" / "probe.db").is_file())

    def test_invalid_run_id_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--role", "coordinator",
                 "--run-id", "../unsafe", directory],
                capture_output=True, text=True, timeout=10,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(list(Path(directory).iterdir()), [])


if __name__ == "__main__":
    unittest.main()
