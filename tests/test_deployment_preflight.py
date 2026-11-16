"""Verify that deployment safety checks run before Azure mutations."""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "deploy-container-apps.sh"
EXAMPLE = ROOT / "scripts" / "container-apps.env.example"
GIT_BASH = Path(r"C:\Program Files\Git\bin\bash.exe")
BASH = str(GIT_BASH) if os.name == "nt" and GIT_BASH.exists() else shutil.which("bash")


@unittest.skipUnless(BASH, "bash is required for deployment preflight tests")
class DeploymentPreflightTests(unittest.TestCase):
    def run_preflight(
        self, substitutions: dict[str, str], fake_script: str | None = None,
    ) -> subprocess.CompletedProcess:
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            fake_az = directory / "az"
            fake_az.write_text(
                fake_script or "#!/usr/bin/env bash\necho AZ_WAS_CALLED >&2\nexit 42\n",
                encoding="utf-8",
            )
            fake_az.chmod(0o755)
            config = EXAMPLE.read_text(encoding="utf-8")
            for old, new in substitutions.items():
                config = config.replace(old, new)
            config_path = directory / "config.env"
            config_path.write_text(config, encoding="utf-8")
            env = os.environ.copy()
            env["PATH"] = str(directory) + os.pathsep + env["PATH"]
            return subprocess.run(
                [BASH, str(SCRIPT), str(config_path)],
                env=env, capture_output=True, text=True, timeout=30,
            )

    def test_unverified_mounts_fail_before_calling_azure(self) -> None:
        result = self.run_preflight({})
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Validate SQLite locking", result.stderr)
        self.assertNotIn("AZ_WAS_CALLED", result.stderr)

    def test_duplicate_mounts_fail_before_calling_azure(self) -> None:
        result = self.run_preflight({
            'MEMORY_STORAGE_NAME="replace-memory-storage"': 'MEMORY_STORAGE_NAME="replace-bff-storage"',
            'SQLITE_MOUNTS_VALIDATED="false"': 'SQLITE_MOUNTS_VALIDATED="true"',
        })
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("distinct registered storage mounts", result.stderr)
        self.assertNotIn("AZ_WAS_CALLED", result.stderr)

    def test_existing_app_is_never_updated(self) -> None:
        fake_az = """#!/usr/bin/env bash
case "$*" in
  *" create "*|*" update "*|*" assign "*) echo AZ_MUTATION_CALLED >&2; exit 42 ;;
esac
case "$1 $2 $3" in
  "group exists "*) echo true ;;
  "containerapp env storage") echo ReadWrite ;;
esac
exit 0
"""
        result = self.run_preflight({
            "00000000-0000-0000-0000-000000000000": "11111111-1111-1111-1111-111111111111",
            'SQLITE_MOUNTS_VALIDATED="false"': 'SQLITE_MOUNTS_VALIDATED="true"',
            "replace-owner": "example",
            "replace-with-git-sha": "0123456789abcdef",
            "replace-with-model-deployment": "model",
        }, fake_az)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("already exists; this script only supports a fresh deployment", result.stderr)
        self.assertNotIn("AZ_MUTATION_CALLED", result.stderr)


if __name__ == "__main__":
    unittest.main()
