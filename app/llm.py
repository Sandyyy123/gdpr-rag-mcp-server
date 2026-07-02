"""
Local LLM answer generation via Ollama (Qwen3 14B by default).

No external LLM API is ever called - generation runs on the German host, so no
tenant data leaves the machine. If Ollama is not reachable, a transparent
extractive fallback assembles an answer from the retrieved context so the demo
still returns something useful and the request path stays intact.
"""
from __future__ import annotations

import os
from typing import List

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
MODEL = os.getenv("OLLAMA_MODEL", "qwen3:14b")

SYSTEM_DE = (
    "Du bist ein praeziser Wissensassistent. Beantworte die Frage ausschliesslich "
    "auf Basis des bereitgestellten Kontexts. Wenn der Kontext die Antwort nicht "
    "enthaelt, sage das offen. Antworte auf Deutsch."
)


def _build_prompt(query: str, contexts: List[str]) -> str:
    ctx = "\n\n".join(f"[{i+1}] {c}" for i, c in enumerate(contexts) if c)
    return f"{SYSTEM_DE}\n\nKontext:\n{ctx}\n\nFrage: {query}\n\nAntwort:"


def generate_answer(query: str, contexts: List[str]) -> str:
    prompt = _build_prompt(query, contexts)
    try:
        import requests

        r = requests.post(
            f"{OLLAMA_URL}/api/generate",
            json={"model": MODEL, "prompt": prompt, "stream": False},
            timeout=float(os.getenv("OLLAMA_TIMEOUT", "120")),
        )
        r.raise_for_status()
        return r.json().get("response", "").strip()
    except Exception:
        return _extractive_fallback(query, contexts)


def _extractive_fallback(query: str, contexts: List[str]) -> str:
    if not any(contexts):
        return "Der Kontext enthaelt keine passende Information zu dieser Frage."
    top = next(c for c in contexts if c)
    return f"(lokales Modell nicht erreichbar - extraktive Antwort) {top}"
