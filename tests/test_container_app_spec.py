"""Tests for the deployment script's Container Apps template rendering."""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "deploy-container-apps.sh"
MARKER = 'python3 - "$spec_file" "$image" "$storage_name" "${env_vars[@]}" <<\'PY\'\n'


class ContainerAppSpecTests(unittest.TestCase):
    def render(self, storage: str) -> dict:
        renderer = SCRIPT.read_text(encoding="utf-8").split(MARKER, 1)[1].split("\nPY\n", 1)[0]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "spec.json"
            path.write_text(
                json.dumps({
                    "properties": {
                        "configuration": {"registries": [{"server": "old"}]},
                        "template": {
                            "containers": [{"image": "old", "volumeMounts": [{"volumeName": "old"}]}],
                            "scale": {"minReplicas": 0, "maxReplicas": 4},
                            "volumes": [{"name": "old"}],
                        },
                    }
                }),
                encoding="utf-8",
            )
            subprocess.run(
                [sys.executable, "-c", renderer, str(path), "example/image:sha", storage, "A=x=y"],
                check=True,
            )
            return json.loads(path.read_text(encoding="utf-8"))["properties"]["template"]

    def test_persistent_app_uses_the_named_mount(self) -> None:
        template = self.render("memory-share")
        self.assertEqual(template["volumes"], [{
            "name": "data", "storageType": "AzureFile", "storageName": "memory-share",
        }])
        self.assertEqual(template["containers"][0]["volumeMounts"], [
            {"volumeName": "data", "mountPath": "/data"},
        ])
        self.assertEqual(template["containers"][0]["env"], [{"name": "A", "value": "x=y"}])
        self.assertEqual(template["scale"], {"minReplicas": 1, "maxReplicas": 1})

    def test_stateless_app_does_not_mount_a_database(self) -> None:
        template = self.render("")
        self.assertEqual(template["volumes"], [])
        self.assertNotIn("volumeMounts", template["containers"][0])


if __name__ == "__main__":
    unittest.main()
