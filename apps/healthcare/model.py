"""Optional LLM explanation of a predefined synthetic case."""

from __future__ import annotations

import os
from collections import deque
from threading import Lock
from time import monotonic, perf_counter

from engine import run_case

_lock = Lock()
_calls = deque()
_busy = False


class ModelBusy(Exception):
    pass


def explain(case: str, version: str) -> dict:
    global _busy
    result = run_case(case, version)
    reference = run_case(case, "stable")
    endpoint = os.environ.get("HEALTHOPS_MODEL_ENDPOINT", "").rstrip("/")
    deployment = os.environ.get("HEALTHOPS_MODEL_DEPLOYMENT", "")
    if not endpoint or not deployment:
        raise RuntimeError("Model not configured")

    now = monotonic()
    with _lock:
        while _calls and now - _calls[0] >= 3600:
            _calls.popleft()
        if _busy or len(_calls) >= 20:
            raise ModelBusy()
        _busy = True
        _calls.append(now)
    try:
        from azure.identity import AzureCliCredential, ManagedIdentityCredential, get_bearer_token_provider
        from openai import OpenAI

        credential = (ManagedIdentityCredential() if os.environ.get("HEALTHOPS_IDENTITY") == "managed"
                      else AzureCliCredential())
        token = get_bearer_token_provider(credential, "https://cognitiveservices.azure.com/.default")
        prompt = (
            "Eres un asistente para una clase de AgentOps sobre un bar ficticio. "
            "Explica en español, en tres frases breves, "
            "el resultado observado, compáralo con la referencia y señala si hay discrepancia. "
            "No propongas acciones sobre personas o sistemas reales.\n"
            f"Caso: {result['title']}. Productos agotados: {', '.join(result['missing']) or 'ninguno'}. "
            f"Versión: {version}. Resultado observado: {result['status']}. "
            f"Referencia estable: {reference['status']}."
        )
        start = perf_counter()
        client = OpenAI(base_url=endpoint + "/openai/v1/", api_key=token, timeout=30, max_retries=0)
        response = client.responses.create(model=deployment, input=prompt, max_output_tokens=400)
        if response.status != "completed" or not response.output_text.strip():
            raise RuntimeError("Incomplete model response")
        return {
            "text": response.output_text.strip(),
            "model": response.model,
            "duration_ms": round((perf_counter() - start) * 1000),
            "observed": result["status"],
            "reference": reference["status"],
            "discrepancy": result["status"] != reference["status"],
        }
    finally:
        with _lock:
            _busy = False
