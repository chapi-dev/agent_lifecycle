"""HTTP server for the synthetic bar AgentOps classroom."""

from __future__ import annotations

import json
import hmac
import os
import sys
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

from engine import catalog, evaluate, run_case
from model import ModelBusy, explain

HTML = Path(__file__).with_name("index.html")
source_root = os.environ.get("HEALTHOPS_SOURCE_ROOT")
ROOT = Path(source_root) if source_root else Path(__file__).resolve().parents[2]
PREVIEW = ROOT / "apps" / "frontend" / "preview"
sys.path.insert(0, str(PREVIEW))
from build_preview import build as build_restaurant_preview

RESTAURANT = build_restaurant_preview().replace(
    "<body>",
    """<body>
<nav class="classroom-nav" aria-label="Navegación de la clase">
  <span>BAR AGENTOPS <b>· EL CAMBIO COBRA VIDA</b></span>
  <a href="/lab">Abrir el dashboard →</a>
</nav>
<div class="classroom-note">Sala y chat simulados · el recorrido del pedido ejecuta reglas reales en la API · solo datos ficticios.</div>""",
    1,
).replace(
    "</style>",
    """.classroom-nav { position:fixed; z-index:1200; top:0; left:0; right:0; display:flex;
      align-items:center; justify-content:space-between; gap:12px; padding:12px 20px;
      background:rgba(10,15,31,.94); border-bottom:1px solid #69513a;
      color:#f5e6ca; font:700 12px/1.3 system-ui,sans-serif; letter-spacing:.06em; }
    .classroom-nav b { color:#e4af61; }
    .classroom-nav a { color:#ffe0a2; white-space:nowrap; text-decoration:none; }
    .classroom-nav a:focus-visible { outline:3px solid #ffe0a2; }
    .classroom-note { position:fixed; z-index:1100; top:52px; left:0; right:0;
      padding:5px 16px; background:rgba(10,15,31,.85); text-align:center;
      color:#f5e6ca; font:12px/1.4 system-ui,sans-serif; }
    .interior { padding-top:80px; }
    @media(max-width:600px) { .classroom-nav { font-size:10px; padding:10px; }
      .classroom-note { top:43px; } }
</style>""",
    1,
).replace(
    '<link rel="stylesheet" href="preview.css">',
    '<link rel="stylesheet" href="preview.css"><link rel="stylesheet" href="bar.css">',
    1,
).replace(
    '<main class="sala">',
    """<main class="sala">
<section class="bar-control" aria-label="Experimento de la sala">
  <div><small>EXPERIMENTO EN EL BAR · SOLO EN ESTE NAVEGADOR</small>
    <strong id="bar-version">Cargando versión…</strong>
    <span id="bar-case">Agua con gas agotada</span></div>
  <button type="button" id="bar-run">▶ Ejecutar pedido</button>
  <p id="bar-status" role="status" aria-live="polite">La animación representa los eventos reales de la API.</p>
  <div class="bar-stages" aria-label="Estado de los componentes">
    <span id="bar-stage-0">Camarero</span><span id="bar-stage-1">Barra</span>
    <span id="bar-stage-2">Cocina</span><span id="bar-stage-3">Caja</span>
  </div>
</section>""",
    1,
).replace("</body>", '<script src="bar.js"></script></body>', 1).encode("utf-8")


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
            "default-src 'none'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; "
            "connect-src 'self'; img-src 'self' data:; base-uri 'none'; frame-ancestors 'none'",
        )
        self.end_headers()
        self.wfile.write(data)

    def json(self, code: int, value: object) -> None:
        self.send(code, json.dumps(value, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")

    def do_GET(self) -> None:
        path = urlsplit(self.path).path
        if path == "/":
            self.send(200, RESTAURANT, "text/html; charset=utf-8")
        elif path == "/lab":
            self.send(200, HTML.read_bytes(), "text/html; charset=utf-8")
        elif path in {"/preview.css", "/preview.js", "/bar.css", "/bar.js"}:
            asset = (HTML.parent if path.startswith("/bar.") else PREVIEW) / path[1:]
            kind = "text/css; charset=utf-8" if path.endswith(".css") else "text/javascript; charset=utf-8"
            self.send(200, asset.read_bytes(), kind)
        elif path == "/healthz":
            self.json(200, {"status": "ok"})
        elif path == "/api/cases":
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
    print(f"Bar AgentOps: http://{host}:{server.server_port}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
