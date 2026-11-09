import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import build_system, create_app
from app.retrieval import KnowledgeBase
from portfolio_core import EchoProvider, LLMChunk, LLMError, Settings

BASE = Path(__file__).resolve().parent.parent


@pytest.fixture
def kb():
    return KnowledgeBase.from_paths([BASE / "knowledge"])


def parse_sse(text: str) -> list[tuple[str, dict]]:
    events = []
    for block in text.strip().split("\n\n"):
        name, data = block.split("\n", 1)
        events.append((name.removeprefix("event: "), json.loads(data.removeprefix("data: "))))
    return events


def make_client(kb, provider=None, **overrides):
    settings = Settings(provider="echo", **overrides)
    return TestClient(create_app(settings, provider or EchoProvider(), kb))


def test_retrieval_finds_relevant_chunk(kb):
    assert len(kb) > 5
    top = kb.search("Como foi o projeto de agente com DuckDB e planilhas?", k=3)
    assert any("DuckDB" in c.text for c in top)


def test_retrieval_handles_accents_and_empty_query(kb):
    assert kb.search("") == []
    assert kb.search("formacao UFPB")  # sem acento ainda encontra "Formação"


def test_build_system_has_context_block(kb):
    system = build_system(kb.search("churn"))
    assert "<contexto>" in system and "churn" in system.lower()


def test_health(kb):
    r = make_client(kb).get("/health")
    assert r.status_code == 200 and r.json()["status"] == "ok"


def test_chat_streams_and_keeps_history(kb):
    client = make_client(kb)
    r = client.post("/chat", json={"message": "Olá"})
    assert r.status_code == 200
    events = parse_sse(r.text)
    assert events[0][0] == "meta"
    assert events[-1][0] == "done"
    assert "Olá" in "".join(d["text"] for n, d in events if n == "delta")

    sid = events[0][1]["session_id"]
    r2 = client.post("/chat", json={"message": "Outra", "session_id": sid})
    assert parse_sse(r2.text)[0][1]["session_id"] == sid


def test_chat_rejects_long_message(kb):
    r = make_client(kb, max_message_chars=10).post("/chat", json={"message": "x" * 11})
    assert r.status_code == 422


def test_chat_rate_limited(kb):
    client = make_client(kb, rate_limit_per_minute=1)
    assert client.post("/chat", json={"message": "a"}).status_code == 200
    r = client.post("/chat", json={"message": "b"})
    assert r.status_code == 429 and "Retry-After" in r.headers


def test_chat_daily_cap(kb):
    client = make_client(kb, daily_message_cap=1, rate_limit_per_minute=100)
    assert client.post("/chat", json={"message": "a"}).status_code == 200
    assert client.post("/chat", json={"message": "b"}).status_code == 429


class RefusingProvider:
    async def stream(self, *, system, messages):
        yield LLMChunk(done=True, stop_reason="refusal")


class FailingProvider:
    async def stream(self, *, system, messages):
        raise LLMError("indisponível")
        yield  # pragma: no cover


def test_chat_refusal_is_reported(kb):
    events = parse_sse(make_client(kb, RefusingProvider()).post("/chat", json={"message": "oi"}).text)
    assert events[-1][0] == "error"


def test_chat_api_failure_is_reported(kb):
    events = parse_sse(make_client(kb, FailingProvider()).post("/chat", json={"message": "oi"}).text)
    assert events[-1][0] == "error"
