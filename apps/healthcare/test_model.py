import json
import os
import threading
import unittest
from http.server import ThreadingHTTPServer
from types import SimpleNamespace
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import model
from server import Handler


class ModelTests(unittest.TestCase):
    def setUp(self):
        model._calls.clear()
        model._busy = False
        self.settings = patch.dict(os.environ, {
            "HEALTHOPS_MODEL_ENDPOINT": "https://example.test",
            "HEALTHOPS_MODEL_DEPLOYMENT": "demo",
        })
        self.settings.start()
        self.addCleanup(self.settings.stop)

    @patch("azure.identity.get_bearer_token_provider", return_value=lambda: "token")
    @patch("azure.identity.AzureCliCredential")
    @patch("openai.OpenAI")
    def test_candidate_discrepancy_is_computed_by_rules(self, client, credential, token):
        client.return_value.responses.create.return_value = SimpleNamespace(
            status="completed", output_text="Explicación sintética.", model="demo"
        )
        result = model.explain("missing", "candidate")
        self.assertEqual((result["observed"], result["reference"]), ("ready", "hold"))
        self.assertTrue(result["discrepancy"])
        self.assertEqual(result["text"], "Explicación sintética.")
        prompt = client.return_value.responses.create.call_args.kwargs["input"]
        self.assertIn("Resultado observado: ready", prompt)
        self.assertIn("Referencia estable: hold", prompt)

    @patch("azure.identity.get_bearer_token_provider", return_value=lambda: "token")
    @patch("azure.identity.AzureCliCredential")
    @patch("openai.OpenAI")
    def test_incomplete_response_fails_and_releases_concurrency(self, client, credential, token):
        client.return_value.responses.create.return_value = SimpleNamespace(
            status="incomplete", output_text="", model="demo"
        )
        with self.assertRaises(RuntimeError):
            model.explain("complete", "stable")
        self.assertFalse(model._busy)

    def test_invalid_case_never_consumes_budget(self):
        with self.assertRaises(ValueError):
            model.explain("not-a-case", "stable")
        self.assertEqual(len(model._calls), 0)

    def test_hourly_limit_and_concurrency_fail_closed(self):
        model._calls.extend([model.monotonic()] * 20)
        with self.assertRaises(model.ModelBusy):
            model.explain("complete", "stable")
        model._calls.clear()
        model._busy = True
        with self.assertRaises(model.ModelBusy):
            model.explain("complete", "stable")


class ModelEndpointTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def post(self, token):
        request = Request(
            f"http://127.0.0.1:{self.server.server_port}/api/model",
            data=json.dumps({"case": "complete", "version": "stable"}).encode(),
            headers={"Content-Type": "application/json", "X-Demo-Token": token},
            method="POST",
        )
        try:
            with urlopen(request, timeout=5) as response:
                return response.status
        except HTTPError as error:
            with error:
                return error.code

    def test_restaurant_entry_and_healthcare_lab_are_available(self):
        base = f"http://127.0.0.1:{self.server.server_port}"
        with urlopen(base + "/?estado=dentro", timeout=5) as response:
            page = response.read().decode()
            self.assertIn("RECREACIÓN VISUAL", page)
            self.assertIn('href="/lab"', page)
            self.assertIn('class="escena', page)
        with urlopen(base + "/lab", timeout=5) as response:
            self.assertIn("El viaje del expediente", response.read().decode())
        for asset in ("/preview.css", "/preview.js"):
            with self.subTest(asset=asset), urlopen(base + asset, timeout=5) as response:
                self.assertEqual(response.status, 200)

    @patch("server.explain")
    def test_access_fails_closed_and_provider_failures_are_generic(self, explain):
        with patch.dict(os.environ, {"HEALTHOPS_DEMO_TOKEN": ""}):
            self.assertEqual(self.post(""), 403)
        with patch.dict(os.environ, {"HEALTHOPS_DEMO_TOKEN": "secret"}):
            self.assertEqual(self.post("wrong"), 403)
            explain.assert_not_called()
            explain.side_effect = RuntimeError("sensitive provider detail")
            self.assertEqual(self.post("secret"), 503)


if __name__ == "__main__":
    unittest.main()
