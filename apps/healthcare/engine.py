"""Deterministic bar-service scenarios for the AgentOps classroom."""

from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter


@dataclass(frozen=True)
class Case:
    id: str
    title: str
    drink_available: bool
    food_available: bool
    expected: str


CASES = (
    Case("complete", "Todo disponible", True, True, "ready"),
    Case("missing", "Agua con gas agotada", False, True, "hold"),
    Case("food", "Tortilla agotada", True, False, "hold"),
    Case("both", "Bebida y comida agotadas", False, False, "hold"),
)
VERSIONS = frozenset({"stable", "candidate"})


def run_case(case_id: str, version: str) -> dict:
    if not isinstance(case_id, str) or not isinstance(version, str) or version not in VERSIONS:
        raise ValueError("Invalid scenario")
    case = next((item for item in CASES if item.id == case_id), None)
    if case is None:
        raise ValueError("Invalid scenario")

    start = perf_counter()
    missing = []
    if not case.drink_available:
        missing.append("agua con gas")
    if not case.food_available:
        missing.append("tortilla")
    # The candidate deliberately skips the bar's stock check for the classroom.
    bar_accepts = case.drink_available or version == "candidate"
    kitchen_accepts = case.food_available
    status = "ready" if bar_accepts and kitchen_accepts else "hold"
    bar_error = not case.drink_available and bar_accepts
    events = [
        {
            "agent": "Camarero", "action": "Recibir pedido",
            "detail": "Una mesa ficticia pide agua con gas y tortilla.", "state": "ok",
        },
        {
            "agent": "Barra", "action": "Comprobar bebida",
            "detail": ("La candidata acepta agua con gas aunque no hay stock." if bar_error else
                       "Agua con gas disponible." if case.drink_available else
                       "Agua con gas agotada: se detiene el pedido."),
            "state": "error" if bar_error else "ok",
        },
        {
            "agent": "Cocina", "action": "Comprobar comida",
            "detail": "Tortilla disponible." if case.food_available else "Tortilla agotada: se detiene el pedido.",
            "state": "ok",
        },
        {
            "agent": "Caja", "action": "Preparar propuesta",
            "detail": ("Pedido propuesto para servir; no se ejecuta ningún cobro." if status == "ready" else
                       "Pedido retenido; no se ejecuta ningún cobro."),
            "state": "ok",
        },
    ]
    return {
        "case": case.id, "title": case.title, "version": version,
        "status": status, "missing": missing, "events": events,
        "duration_ms": round((perf_counter() - start) * 1000, 3),
    }


def evaluate(version: str) -> dict:
    results = []
    for case in CASES:
        observed = run_case(case.id, version)["status"]
        results.append({
            "case": case.id, "title": case.title, "expected": case.expected,
            "observed": observed, "passed": observed == case.expected,
        })
    return {"version": version, "passed": all(item["passed"] for item in results), "results": results}


def catalog() -> list[dict]:
    return [{"id": c.id, "title": c.title} for c in CASES]
