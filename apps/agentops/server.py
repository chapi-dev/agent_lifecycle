"""Local classroom control room for the restaurant's real cashier tests."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = Path(__file__).resolve().parents[2]
CASHIER = ROOT / "agents" / "cashier" / "src" / "cashier_agent"
CONTRACTS = ROOT / "packages" / "contracts" / "src"
HTML = Path(__file__).with_name("index.html")
ORIGINAL = "line_total=unit * served.quantity,"
MUTATION = "line_total=unit,"
REGRESSION_TEST = "test_every_served_line_is_priced_once_with_its_served_quantity"
LOCK = threading.Lock()


def evaluate(mode: str) -> dict:
    if not isinstance(mode, str) or mode not in {"original", "regression"}:
        raise ValueError("Invalid scenario")
    source = (CASHIER / "cashier_agent" / "pricing.py").read_text(encoding="utf-8")
    if source.count(ORIGINAL) != 1:
        raise RuntimeError("The pricing code changed; update the classroom scenario before running it.")
    with tempfile.TemporaryDirectory(prefix="restaurant-agentops-") as directory:
        work = Path(directory)
        shutil.copytree(CASHIER / "cashier_agent", work / "cashier_agent", ignore=shutil.ignore_patterns("__pycache__"))
        shutil.copytree(CASHIER / "tests", work / "tests", ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache"))
        if mode == "regression":
            (work / "cashier_agent" / "pricing.py").write_text(source.replace(ORIGINAL, MUTATION), encoding="utf-8")
        env = os.environ.copy()
        env["PYTHONPATH"] = os.pathsep.join((str(work), str(CONTRACTS)))
        env["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONUTF8"] = "1"
        result = subprocess.run(
            [sys.executable, "-m", "pytest", "tests/test_pricing.py", "-q", "--color=no", "-p", "no:cacheprovider"],
            cwd=work, env=env, capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=120,
        )
    output = (result.stdout + "\n" + result.stderr).strip()
    detected = result.returncode == 1 and REGRESSION_TEST in output and "FAILED" in output
    status = "passed" if result.returncode == 0 else "failed" if result.returncode == 1 and "FAILED" in output else "error"
    return {
        "scenario": mode,
        "status": status,
        "regression_detected": detected if mode == "regression" else False,
        "exit_code": result.returncode,
        "source_sha256": hashlib.sha256(source.encode("utf-8")).hexdigest(),
        "output": output[-16000:],
    }


class Handler(BaseHTTPRequestHandler):
    def _send(self, status: int, data: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(data)

    def _local_host(self) -> bool:
        return self.headers.get("Host") == f"127.0.0.1:{self.server.server_port}"

    def do_GET(self) -> None:
        if not self._local_host() or self.path != "/":
            self._send(404, b"Not found", "text/plain")
            return
        self._send(200, HTML.read_bytes(), "text/html; charset=utf-8")

    def do_POST(self) -> None:
        origin = f"http://127.0.0.1:{self.server.server_port}"
        if not self._local_host() or self.headers.get("Origin") != origin or self.path != "/evaluate":
            self._send(403, b"Forbidden", "text/plain")
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 128 or self.headers.get_content_type() != "application/json":
                raise ValueError("Invalid request")
            payload = json.loads(self.rfile.read(length))
            if not isinstance(payload, dict) or set(payload) != {"scenario"}:
                raise ValueError("Invalid request")
            if not LOCK.acquire(blocking=False):
                self._send(409, b'{"error":"Evaluation already running"}', "application/json")
                return
            try:
                result = evaluate(payload["scenario"])
            finally:
                LOCK.release()
            self._send(200, json.dumps(result, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")
        except (ValueError, json.JSONDecodeError):
            self._send(400, b'{"error":"Invalid request"}', "application/json")
        except (OSError, RuntimeError, subprocess.TimeoutExpired) as exc:
            self._send(500, json.dumps({"error": str(exc)}).encode("utf-8"), "application/json")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        original, regression = evaluate("original"), evaluate("regression")
        print(json.dumps({"original": original, "regression": regression}, ensure_ascii=False, indent=2))
        if original["status"] != "passed" or not regression["regression_detected"]:
            raise SystemExit(1)
        return
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"Panel local: http://127.0.0.1:{server.server_port}/", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
