"""Teste de fumaça do Langfuse: manda UM trace de teste pelo pipeline real do chat (com guardrails e um feedback) e
confere se o trace e as notas chegaram ao servidor.

Uso (na pasta 00-site-chat), com as chaves do SEU projeto Langfuse e o servidor no ar:

    $env:LANGFUSE_PUBLIC_KEY = "pk-lf-..."
    $env:LANGFUSE_SECRET_KEY = "sk-lf-..."
    $env:LANGFUSE_BASE_URL   = "http://localhost:3000"        # ou https://cloud.langfuse.com
    ../.venv/Scripts/python -m evaluation.langfuse_smoke

(as variáveis também podem estar num .env na pasta do projeto ou na raiz do workspace)

Não chama nenhum LLM (usa um provedor falso, sem custo). O trace vai para o ambiente ``portfolio-smoke`` do Langfuse,
que você pode filtrar ou apagar depois sem misturar com dados reais.
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import create_app
from app.retrieval import KnowledgeBase
from portfolio_core import LLMChunk, Settings, Usage, get_tracer
from portfolio_core.config import load_dotenv_if_present

KNOWLEDGE = Path(__file__).resolve().parent.parent / "knowledge"
EXPECTED = {"chat-turn", "retrieval", "generation"}
EXPECTED_SCORES = {"injection_suspect", "pii_in_input", "no_context", "unsupported_links", "prompt_leak_suspect",
                   "pii_in_output", "knowledge_gap", "user_feedback"}


class FakeProvider:
    async def stream(self, *, system, messages, tools=None):
        yield LLMChunk(text="Resposta de teste do ")
        yield LLMChunk(text="teste de fumaça.")
        yield LLMChunk(done=True, stop_reason="end_turn", usage=Usage(123, 7))


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8", errors="replace")
    load_dotenv_if_present()
    os.environ.setdefault("LANGFUSE_TRACING_ENVIRONMENT", "portfolio-smoke")

    tracer = get_tracer()
    if not tracer.enabled:
        print("Langfuse desligado: defina LANGFUSE_PUBLIC_KEY e LANGFUSE_SECRET_KEY (e LANGFUSE_BASE_URL).", file=sys.stderr)
        return 2
    client = tracer._client  # noqa: SLF001  (o script de fumaça precisa do cliente para ler de volta)
    host = os.environ.get("LANGFUSE_BASE_URL") or os.environ.get("LANGFUSE_HOST") or "https://cloud.langfuse.com"

    try:
        ok = client.auth_check()
    except Exception as exc:  # servidor fora do ar, URL errada...
        print(f"Não consegui falar com o Langfuse em {host}: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 3
    if not ok:
        print(f"O Langfuse em {host} recusou as chaves (auth_check falhou). Confira as chaves e o projeto.", file=sys.stderr)
        return 3
    print(f"Conectado ao Langfuse em {host} (ambiente: {os.environ['LANGFUSE_TRACING_ENVIRONMENT']}).")

    kb = KnowledgeBase.from_paths([KNOWLEDGE])
    settings = Settings(provider="echo", model="smoke-test-model", rate_limit_per_minute=100)
    with TestClient(create_app(settings, FakeProvider(), kb, tracer)) as app_client:
        reply = app_client.post("/chat", json={"message": "Teste de fumaça: onde o Heriberto trabalha?"})
        session_id = reply.text.split('"session_id": "')[1].split('"')[0]
        trace_id = reply.text.split('"trace_id": "')[1].split('"')[0]
        fb = app_client.post("/feedback", json={"session_id": session_id, "trace_id": trace_id, "helpful": True})
        assert fb.status_code == 200, fb.text
    tracer.flush()
    print(f"Trace enviado (sessão {session_id}). Esperando o servidor processar...")

    deadline, seen = time.monotonic() + 45, {}
    while time.monotonic() < deadline:
        try:
            page = client.api.observations.get_many(session_id=session_id, limit=20, fields="core,basic,usage,model")
            seen = {o.name: o for o in page.data}
        except Exception as exc:
            print(f"  (leitura ainda falhou: {type(exc).__name__}; tentando de novo)")
        if EXPECTED <= set(seen):
            break
        time.sleep(3)

    missing = EXPECTED - set(seen)
    if missing:
        print(f"FALHA: não chegaram as observações {sorted(missing)} em 45 s. O servidor está processando a fila "
              "(worker/ClickHouse no ar?). Chegaram: " + (", ".join(sorted(seen)) or "nenhuma"), file=sys.stderr)
        return 1

    gen = seen["generation"]
    print("OK: chegaram as 3 observações (chat-turn, retrieval, generation).")

    # As notas (7 guardrails + o feedback) vão por outro caminho e a leitura delas pode demorar no servidor.
    deadline, found = time.monotonic() + 45, set()
    while time.monotonic() < deadline and not EXPECTED_SCORES <= found:
        try:
            found = {s.name for s in client.api.scores.get_many(trace_id=trace_id, limit=50).data}
        except Exception:
            pass
        if not EXPECTED_SCORES <= found:
            time.sleep(3)
    if EXPECTED_SCORES <= found:
        print(f"OK: chegaram as {len(EXPECTED_SCORES)} notas (guardrails + user_feedback).")
    else:
        print(f"AVISO: ainda não consigo ler as notas {sorted(EXPECTED_SCORES - found)}. Elas foram enviadas; a leitura de scores "
              "pode demorar vários minutos no servidor. Confira na interface (Traces > o trace > Scores).")
    print(f"  generation: modelo={getattr(gen, 'provided_model_name', None) or getattr(gen, 'model', None)}, "
          f"uso={getattr(gen, 'usage_details', None)}")
    try:
        print("  veja em:", client.get_trace_url(trace_id=gen.trace_id))
    except Exception:
        pass
    tracer.shutdown()
    return 0


if __name__ == "__main__":
    sys.exit(main())
