"""Synthetic, non-clinical referral administration for the teaching demo."""

from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter


@dataclass(frozen=True)
class Case:
    id: str
    title: str
    service: str
    has_referral: bool
    consent: bool
    expected: str


CASES = (
    Case("complete", "Documentación completa", "Rehabilitación", True, True, "ready"),
    Case("missing", "Falta la derivación", "Rehabilitación", False, True, "hold"),
    Case("consent", "Falta el consentimiento administrativo", "Pruebas", True, False, "hold"),
    Case("both", "Faltan ambos documentos", "Consultas", False, False, "hold"),
)
VERSIONS = frozenset({"stable", "candidate"})


def _case(case_id: str) -> Case:
    return next(case for case in CASES if case.id == case_id)


def run_case(case_id: str, version: str) -> dict:
    if not isinstance(case_id, str) or not isinstance(version, str) or version not in VERSIONS:
        raise ValueError("Invalid scenario")
    try:
        case = _case(case_id)
    except StopIteration as exc:
        raise ValueError("Invalid scenario") from exc

    start = perf_counter()
    events = []
    events.append({
        "agent": "Recepción", "action": "Clasificar solicitud",
        "detail": f"Trámite administrativo sintético para {case.service}.",
    })
    missing = []
    if not case.has_referral:
        missing.append("derivación")
    if not case.consent:
        missing.append("consentimiento administrativo")
    events.append({
        "agent": "Verificación documental", "action": "Comprobar requisitos",
        "detail": "Falta: " + ", ".join(missing) + "." if missing else "Documentación completa.",
    })

    # The candidate is a deliberately defective example, never a real decision.
    blocking = [item for item in missing if version != "candidate" or item != "derivación"]
    status = "hold" if blocking else "ready"
    events.append({
        "agent": "Coordinación", "action": "Proponer siguiente paso",
        "detail": "Solicitar documentación pendiente." if status == "hold"
        else "Preparar expediente para revisión humana.",
    })
    events.append({
        "agent": "Auditoría", "action": "Registrar resultado",
        "detail": "Sin paciente real, sin diagnóstico y sin acción externa.",
    })
    return {
        "case": case.id, "title": case.title, "service": case.service,
        "version": version, "status": status, "missing": missing, "events": events,
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
    passed = all(result["passed"] for result in results)
    return {"version": version, "passed": passed, "results": results}


def catalog() -> list[dict]:
    return [{"id": c.id, "title": c.title, "service": c.service} for c in CASES]
