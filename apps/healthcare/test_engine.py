import unittest

from engine import CASES, catalog, evaluate, run_case


class HealthcareDemoTests(unittest.TestCase):
    def test_baseline_passes_all_administrative_cases(self):
        result = evaluate("stable")
        self.assertTrue(result["passed"])
        self.assertEqual(len(result["results"]), len(CASES))

    def test_candidate_fails_the_missing_referral_case(self):
        result = evaluate("candidate")
        self.assertFalse(result["passed"])
        missing = next(item for item in result["results"] if item["case"] == "missing")
        self.assertEqual((missing["expected"], missing["observed"]), ("hold", "ready"))
        self.assertFalse(missing["passed"])

    def test_missing_consent_remains_blocked_in_both_versions(self):
        for version in ("stable", "candidate"):
            with self.subTest(version=version):
                self.assertEqual(run_case("consent", version)["status"], "hold")

    def test_every_event_is_synthetic_and_no_external_action_is_taken(self):
        result = run_case("complete", "stable")
        self.assertEqual([event["agent"] for event in result["events"]],
                         ["Recepción", "Verificación documental", "Coordinación", "Auditoría"])
        self.assertIn("Sin paciente real", result["events"][-1]["detail"])
        self.assertNotIn("name", catalog()[0])

    def test_invalid_inputs_are_rejected(self):
        for case, version in (("bad", "stable"), ("complete", []), ([], "stable"), ("complete", "other")):
            with self.subTest(case=case, version=version), self.assertRaises(ValueError):
                run_case(case, version)


if __name__ == "__main__":
    unittest.main()
