import subprocess
import unittest
from unittest.mock import patch

import server


class EvaluateTests(unittest.TestCase):
    def test_scenario_rejects_unexpected_input(self):
        for value in ("other", [], None):
            with self.subTest(value=value), self.assertRaises(ValueError):
                server.evaluate(value)

    def test_regression_is_applied_only_to_the_temporary_copy(self):
        original = (server.CASHIER / "cashier_agent" / "pricing.py").read_text(encoding="utf-8")

        def fake_run(command, **kwargs):
            copy = (kwargs["cwd"] / "cashier_agent" / "pricing.py").read_text(encoding="utf-8")
            self.assertIn(server.MUTATION, copy)
            self.assertNotIn(server.ORIGINAL, copy)
            return subprocess.CompletedProcess(command, 1, f"FAILED {server.REGRESSION_TEST}", "")

        with patch.object(server.subprocess, "run", side_effect=fake_run):
            result = server.evaluate("regression")
        self.assertTrue(result["regression_detected"])
        self.assertEqual((server.CASHIER / "cashier_agent" / "pricing.py").read_text(encoding="utf-8"), original)

    def test_collection_error_is_not_a_detected_regression(self):
        failure = subprocess.CompletedProcess([], 2, "collection error", "")
        with patch.object(server.subprocess, "run", return_value=failure):
            result = server.evaluate("regression")
        self.assertEqual(result["status"], "error")
        self.assertFalse(result["regression_detected"])


if __name__ == "__main__":
    unittest.main()
