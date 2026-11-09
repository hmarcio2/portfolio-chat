import json
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.retrieval import KnowledgeBase
from portfolio_core import LLMChunk, LLMError, Settings, Span, Tracer, Usage, mask_pii

KNOWLEDGE = Path(__file__).resolve().parent.parent / "knowledge"


@pytest.fixture(scope="module")
def kb():
    return KnowledgeBase.from_paths([KNOWLEDGE])


# ---------- um tracer falso que grava tudo ----------

class RecSpan(Span):
    def __init__(self, log, name, kind="span", **kw):
        self.log, self.name, self.kind, self.kw, self.updates, self.ended = log, name, kind, kw, [], False
        self.scores = []
        if kind == "trace":
            self._tid = uuid.uuid4().hex  # como o Langfuse: 32 caracteres hex
        log.append(self)

    def child(self, name, *, as_type="span", **kw):
        return RecSpan(self.log, name, as_type, **kw)

    def update(self, **kw):
        self.updates.append({k: v for k, v in kw.items() if v is not None})

    @property
    def trace_id(self):
        return getattr(self, "_tid", None)

    def score(self, name, value, *, data_type="NUMERIC", comment=None):
        self.scores.append((name, value, data_type, comment))

    def end(self):
        self.ended = True

    @property
    def merged(self):
        out = {}
        for u in self.updates:
            out.update(u)
        return out


class RecTracer(Tracer):
    enabled = True

    def __init__(self):
        self.log = []
        self.late_scores = []
        self.shut = False

    def start(self, name, **kw):
        return RecSpan(self.log, name, "trace", **kw)

    def score_trace(self, trace_id, name, value, *, data_type="NUMERIC", comment=None):
        self.late_scores.append((trace_id, name, value, data_type, comment))

    def shutdown(self):
        self.shut = True


class Scripted:
    def __init__(self, *chunks, error=None):
        self.chunks, self.error = chunks, error

    async def stream(self, *, system, messages, tools=None):
        for c in self.chunks:
            yield c
        if self.error:
            raise self.error


def ok_chunks():
    return [LLMChunk(text="Trabalha na "), LLMChunk(text="Dhauz."),
            LLMChunk(done=True, stop_reason="end_turn", usage=Usage(120, 8, 30))]


def run(kb, provider, tracer, messages, settings=None):
    settings = settings or Settings(provider="echo", model="gemini-flash-lite-latest", rate_limit_per_minute=100)
    texts = []
    with TestClient(create_app(settings, provider, kb, tracer)) as client:
        sid = None
        for m in messages:
            r = client.post("/chat", json={"message": m, "session_id": sid})
            sid = r.text.split('"session_id": "')[1].split('"')[0]
            texts.append(r.text)
    return sid, texts


def by_name(tracer):
    return {s.name: s for s in tracer.log}


def test_a_turn_becomes_one_trace_with_retrieval_and_generation(kb):
    tracer = RecTracer()
    sid, _ = run(kb, Scripted(*ok_chunks()), tracer, ["Onde o Heriberto trabalha?"])
    s = by_name(tracer)
    assert [x.name for x in tracer.log] == ["chat-turn", "retrieval", "generation"]
    root, retrieval, gen = s["chat-turn"], s["retrieval"], s["generation"]

    assert root.kw["session_id"] == sid and root.kw["input"] == "Onde o Heriberto trabalha?"
    assert root.kw["metadata"]["model"] == "gemini-flash-lite-latest" and root.kw["metadata"]["turn"] == 1
    assert retrieval.kind == "retriever" and retrieval.merged["output"][0]["heading"]
    assert retrieval.merged["metadata"]["chunks"] >= 1

    assert gen.kind == "generation" and gen.kw["model"] == "gemini-flash-lite-latest"
    assert gen.kw["input"][0]["role"] == "system" and "<contexto>" in gen.kw["input"][0]["content"]  # o que o modelo viu
    assert gen.kw["input"][-1] == {"role": "user", "content": "Onde o Heriberto trabalha?"}
    u = gen.merged
    assert u["output"] == "Trabalha na Dhauz." and u["usage"].input_tokens == 120 and u["usage"].cache_read_input_tokens == 30
    assert u["completion_start_time"] is not None and u["metadata"]["stop_reason"] == "end_turn"
    assert root.merged["output"] == "Trabalha na Dhauz." and root.merged["metadata"]["sources"]
    assert all(x.ended for x in tracer.log) and tracer.shut


def test_turns_of_one_conversation_share_the_session_id(kb):
    tracer = RecTracer()
    sid, _ = run(kb, Scripted(*ok_chunks()), tracer, ["Fale do projeto DSS", "e a stack?"])
    roots = [x for x in tracer.log if x.name == "chat-turn"]
    assert len(roots) == 2 and {r.kw["session_id"] for r in roots} == {sid}
    assert [r.kw["metadata"]["turn"] for r in roots] == [1, 2]


def test_provider_failure_marks_trace_and_generation_as_error(kb):
    tracer = RecTracer()
    run(kb, Scripted(error=LLMError("429 cota")), tracer, ["oi"])
    s = by_name(tracer)
    for name in ("generation", "chat-turn"):
        assert s[name].merged["level"] == "ERROR" and "429" in s[name].merged["status_message"]
        assert s[name].ended


def test_refusal_is_a_warning(kb):
    tracer = RecTracer()
    run(kb, Scripted(LLMChunk(done=True, stop_reason="refusal")), tracer, ["oi"])
    assert by_name(tracer)["chat-turn"].merged["level"] == "WARNING"


def test_rejected_requests_create_no_trace(kb):
    tracer = RecTracer()
    settings = Settings(provider="echo", rate_limit_per_minute=1, max_message_chars=10)
    with TestClient(create_app(settings, Scripted(*ok_chunks()), kb, tracer)) as client:
        assert client.post("/chat", json={"message": "x" * 11}).status_code == 422
        assert client.post("/chat", json={"message": "oi"}).status_code == 200
        assert client.post("/chat", json={"message": "oi"}).status_code == 429
    assert len([x for x in tracer.log if x.name == "chat-turn"]) == 1  # só a que foi atendida


# ---------- com o SDK real do Langfuse (exportador em memória) ----------

langfuse = pytest.importorskip("langfuse")
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter  # noqa: E402

from portfolio_core.tracing import LangfuseTracer  # noqa: E402


def real_tracer(**kw):
    exporter = InMemorySpanExporter()
    client = langfuse.Langfuse(public_key=f"pk-{uuid.uuid4()}", secret_key="sk-test", host="http://127.0.0.1:9",
                               span_exporter=exporter, environment="portfolio-test", mask=lambda *, data, **k: mask_pii(data))
    tracer = LangfuseTracer(client, tags=["portfolio-chat"], **kw)

    def spans():
        client.flush()
        return {s.name: dict(s.attributes) for s in exporter.get_finished_spans()}

    return tracer, spans


def test_full_pipeline_with_the_real_sdk(kb):
    tracer, spans = real_tracer()
    sid, _ = run(kb, Scripted(*ok_chunks()), tracer, ["Meu email é visitante@exemplo.com, onde ele trabalha?"])
    s = spans()
    assert set(s) == {"chat-turn", "retrieval", "generation"}
    assert all(a["session.id"] == sid and "portfolio-chat" in a["langfuse.trace.tags"] for a in s.values())
    assert "visitante@exemplo.com" not in json.dumps(s, ensure_ascii=False)  # e-mail mascarado em todo lugar
    assert json.loads(s["generation"]["langfuse.observation.usage_details"]) == {"input": 120, "output": 8, "cache_read_input_tokens": 30}
    assert s["generation"]["langfuse.observation.model.name"] == "gemini-flash-lite-latest"
    assert s["chat-turn"]["langfuse.observation.output"] == "Trabalha na Dhauz."


def test_full_pipeline_without_content_capture_keeps_only_metrics(kb):
    tracer, spans = real_tracer(capture_content=False)
    run(kb, Scripted(*ok_chunks()), tracer, ["Quais as habilidades secretas dele?"])
    blob = json.dumps(spans(), ensure_ascii=False)
    assert "habilidades secretas" not in blob and "Dhauz" not in blob and "<contexto>" not in blob
    assert "conteúdo não registrado" in blob and "usage_details" in blob  # métricas continuam
