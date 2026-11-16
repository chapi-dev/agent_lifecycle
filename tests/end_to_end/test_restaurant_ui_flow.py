"""Exercise the original Streamlit view against the scripted end-to-end stack.

The waiter and chef use scripted models, but the BFF, seating MCP, bar and
cashier communicate through their real HTTP/A2A interfaces.
"""

from __future__ import annotations

import os
import time
import uuid
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

BFF_URL = os.environ.get("E2E_CASHIER_BFF_URL")
pytestmark = pytest.mark.skipif(not BFF_URL, reason="E2E_CASHIER_BFF_URL is not set")
APP = Path(__file__).resolve().parents[2] / "apps" / "frontend" / "src" / "frontend" / "app.py"


def _markup(app: AppTest) -> str:
    return "\n".join(element.value for element in app.markdown)


def _say(app: AppTest, text: str) -> AppTest:
    return app.chat_input(key="redactor").set_value(text).run()


def test_original_view_seats_serves_bills_and_pays(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FRONTEND_BFF_URL", BFF_URL)
    monkeypatch.setenv("FRONTEND_FAREWELL_SECONDS", "30")
    app = AppTest.from_file(str(APP), default_timeout=45).run()
    assert not app.exception
    assert 'class="escena cerrada"' in _markup(app)

    app.text_input(key="name").input(f"UI {uuid.uuid4().hex[:8]}")
    app = app.button(key="enter").click().run()
    assert not app.exception
    assert 'class="escena abriendo"' in _markup(app)
    app = app.run()
    app = _say(app, "Hola, somos dos")
    assert not app.exception
    assert app.session_state["visit"].snapshot.seating.proposal is not None
    app = next(button for button in app.button if button.label == "Confirmar").click().run()
    assert not app.exception
    assert app.session_state["visit"].snapshot.seating.status == "seated"
    assert "comensal cliente-propio caminando" in _markup(app)

    app = _say(app, "Ponme una morcilla a la brasa y un agua con gas")
    assert not app.exception
    assert 'class="msg cocina"' in _markup(app)
    assert 'class="msg barra"' in _markup(app)
    visit = app.session_state["visit"]
    kitchen = next(message.kitchen for message in reversed(visit.snapshot.messages) if message.kitchen)
    deadline = time.monotonic() + 20
    while kitchen.result.order_id not in visit.snapshot.served_orders:
        assert time.monotonic() < deadline, "The kitchen order was not served"
        time.sleep(0.5)
        visit.refresh_service()

    app = _say(app, "La cuenta, por favor")
    assert not app.exception
    assert app.session_state["visit"].snapshot.pending_bill is not None
    assert "10,70 €" in _markup(app)
    assert 'class="caja pendiente"' in _markup(app)
    app = next(button for button in app.button if button.label == "Tarjeta").click().run()
    assert not app.exception
    assert app.session_state["visit"].snapshot.visit_closed
    assert "Pagado con tarjeta" in _markup(app)
