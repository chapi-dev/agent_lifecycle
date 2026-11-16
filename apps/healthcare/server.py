"""HTTP server for the synthetic healthcare administration classroom."""

from __future__ import annotations

import json
import hmac
import os
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from engine import catalog, evaluate, run_case
from model import ModelBusy, explain

HTML = Path(__file__).with_name("index.html")


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:
        pass

    def send(self, code: int, data: bytes, kind: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; "
            "connect-src 'self'; img-src 'self' data:; base-uri 'none'; frame-ancestors 'none'",
        )
        self.end_headers()
        self.wfile.write(data)

    def json(self, code: int, value: object) -> None:
        self.send(code, json.dumps(value, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")

    def do_GET(self) -> None:
        if self.path == "/":
            self.send(200, HTML.read_bytes(), "text/html; charset=utf-8")
        elif self.path == "/healthz":
            self.json(200, {"status": "ok"})
        elif self.path == "/api/cases":
            self.json(200, {"cases": catalog()})
        else:
            self.json(404, {"error": "Not found"})

    def do_POST(self) -> None:
        if self.path not in {"/api/run", "/api/evaluate", "/api/model"}:
            self.json(404, {"error": "Not found"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 128 or self.headers.get_content_type() != "application/json":
                raise ValueError("Invalid request")
            body = json.loads(self.rfile.read(length))
            if not isinstance(body, dict):
                raise ValueError("Invalid request")
            if self.path == "/api/model":
                expected = os.environ.get("HEALTHOPS_DEMO_TOKEN", "")
                supplied = self.headers.get("X-Demo-Token", "")
                if not expected or not hmac.compare_digest(expected.encode(), supplied.encode()):
                    self.json(403, {"error": "Acceso al modelo no autorizado o no configurado."})
                    return
            if self.path == "/api/run" and set(body) == {"case", "version"}:
                result = run_case(body["case"], body["version"])
            elif self.path == "/api/model" and set(body) == {"case", "version"}:
                result = explain(body["case"], body["version"])
            elif self.path == "/api/evaluate" and set(body) == {"version"}:
                result = evaluate(body["version"])
            else:
                raise ValueError("Invalid request")
            self.json(200, result)
        except (ValueError, UnicodeDecodeError, json.JSONDecodeError):
            self.json(400, {"error": "Invalid request"})
        except ModelBusy:
            self.json(429, {"error": "Límite temporal del modelo alcanzado; inténtalo más tarde."})
        except Exception:
            self.json(503, {"error": "El modelo no está disponible. Las reglas y la evaluación siguen funcionando."})


def main() -> None:
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "8765"))
    server = ThreadingHTTPServer((host, port), Handler)
    print(f"Healthcare AgentOps: http://{host}:{server.server_port}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
