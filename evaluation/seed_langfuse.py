"""Envia as conversas de exemplo (as mesmas do ``capture_traces``) para um servidor Langfuse DE VERDADE, pelo pipeline
real do chat, para você ver traces, notas e latências na interface e tirar os prints da documentação.

Uso (na pasta 00-site-chat), com o servidor no ar, as chaves do projeto e um provedor de LLM:

    $env:LANGFUSE_PUBLIC_KEY = "pk-lf-..."; $env:LANGFUSE_SECRET_KEY = "sk-lf-..."; $env:LANGFUSE_BASE_URL = "http://localhost:3300"
    $env:GOOGLE_API_KEY = "..."
    ../.venv/Scripts/python -m evaluation.seed_langfuse            # LLM real (cerca de 10 chamadas do Flash-Lite)
    ../.venv/Scripts/python -m evaluation.seed_langfuse --offline  # provedor falso, sem custo (as respostas não fazem sentido)

Os traces vão para o ambiente ``portfolio-demo`` (filtre por ele na interface). Rodar de novo cria conversas novas.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import os
import sys

from fastapi.testclient import TestClient

from app.main import create_app
from app.retrieval import KnowledgeBase
from portfolio_core import Settings, get_provider, get_tracer
from portfolio_core.config import load_dotenv_if_present

from .capture_traces import ROOT, SCENARIOS, FakeProvider


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8", errors="replace")
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--offline", action="store_true", help="provedor falso (sem LLM, sem custo)")
    args = p.parse_args()

    load_dotenv_if_present()
    os.environ.setdefault("LANGFUSE_TRACING_ENVIRONMENT", "portfolio-demo")
    tracer = get_tracer()
    if not tracer.enabled:
        print("Langfuse desligado: defina LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY e LANGFUSE_BASE_URL.", file=sys.stderr)
        return 2
    if not tracer._client.auth_check():  # noqa: SLF001
        print("O Langfuse recusou as chaves (ou não respondeu).", file=sys.stderr)
        return 3

    base = Settings.from_env()
    settings = dataclasses.replace(base, provider="echo" if args.offline else base.provider, rate_limit_per_minute=1000).resolved()
    if settings.provider == "echo" and not args.offline:
        print("Nenhum provedor configurado. Defina GOOGLE_API_KEY (ou use --offline).", file=sys.stderr)
        return 2
    provider = FakeProvider() if args.offline else get_provider(settings)
    kb = KnowledgeBase.from_paths([ROOT / "knowledge"])

    sent = 0
    with TestClient(create_app(settings, provider, kb, tracer)) as app:
        for messages, helpful in SCENARIOS:
            session_id = trace_id = None
            for text in messages:
                reply = app.post("/chat", json={"message": text, "session_id": session_id})
                meta = json.loads(reply.text.split("event: meta\ndata: ")[1].split("\n")[0])
                session_id, trace_id = meta["session_id"], meta["trace_id"]
                sent += 1
                print(f"  {'ERR' if 'event: error' in reply.text else 'OK '} {text[:70]}")
            if helpful is not None:
                app.post("/feedback", json={"session_id": session_id, "trace_id": trace_id, "helpful": helpful})
    tracer.shutdown()  # envia o que ficou na fila
    host = os.environ.get("LANGFUSE_BASE_URL") or os.environ.get("LANGFUSE_HOST")
    print(f"\n{sent} perguntas em {len(SCENARIOS)} conversas enviadas ao ambiente "
          f"'{os.environ['LANGFUSE_TRACING_ENVIRONMENT']}' ({host}). Abra a interface e filtre por esse ambiente.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
