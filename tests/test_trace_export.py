import json
import time
import uuid
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

langfuse = pytest.importorskip("langfuse")
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter  # noqa: E402

from app.main import create_app  # noqa: E402
from app.retrieval import KnowledgeBase  # noqa: E402
from evaluation.trace_export import spans_to_traces  # noqa: E402
from portfolio_core import LLMChunk, Settings, Usage, mask_pii  # noqa: E402
from portfolio_core.tracing import LangfuseTracer  # noqa: E402

KB = KnowledgeBase.from_paths([Path(__file__).resolve().parent.parent / "knowledge"])


class Slow:
    async def stream(self, *, system, messages, tools=None):
        yield LLMChunk(text="Trabalha na ")
        time.sleep(0.05)
        yield LLMChunk(text="Dhauz.")
        yield LLMChunk(done=True, stop_reason="end_turn", usage=Usage(120, 8))


def pipeline():
    exporter, scores = InMemorySpanExporter(), []

    def handler(request: httpx.Request):
        if request.url.path.endswith("/api/public/scores"):
            body = json.loads(request.content)
            scores.extend(body if isinstance(body, list) else [body])
        return httpx.Response(200, json={})

    client = langfuse.Langfuse(public_key=f"pk-{uuid.uuid4()}", secret_key="sk", host="http://127.0.0.1:9", span_exporter=exporter,
                               environment="portfolio-demo", httpx_client=httpx.Client(transport=httpx.MockTransport(handler)), flush_at=1, flush_interval=0.1,
                               mask=lambda *, data, **k: mask_pii(data))
    return LangfuseTracer(client, tags=["portfolio-chat"], environment="portfolio-demo"), client, exporter, scores


def test_export_has_the_tree_timing_tokens_scores_and_masking():
    tracer, client, exporter, scores = pipeline()
    with TestClient(create_app(Settings(provider="echo", model="m"), Slow(), KB, tracer)) as app:
        meta = json.loads(app.post("/chat", json={"message": "Meu email é a@b.co. Onde ele trabalha?"}).text
                          .split("event: meta\ndata: ")[1].split("\n")[0])
        app.post("/feedback", json={"session_id": meta["session_id"], "trace_id": meta["trace_id"], "helpful": True})
    client.flush()
    end = time.monotonic() + 8
    while len(scores) < 8 and time.monotonic() < end:
        time.sleep(0.1)

    (trace,) = spans_to_traces(exporter.get_finished_spans(), scores)
    assert trace["trace_id"] == meta["trace_id"] and trace["session_id"] == meta["session_id"]
    assert trace["environment"] == "portfolio-demo" and trace["tags"] == ["portfolio-chat"] and trace["name"] == "chat-turn"

    by = {o["name"]: o for o in trace["observations"]}
    assert set(by) == {"chat-turn", "retrieval", "generation"}
    root = by["chat-turn"]
    assert root["parent_id"] is None and by["retrieval"]["parent_id"] == root["id"] == by["generation"]["parent_id"]
    assert "a@b.co" not in json.dumps(trace, ensure_ascii=False)             # mascarado também no export
    gen = by["generation"]
    assert gen["type"] == "generation" and gen["model"] == "m" and gen["usage"] == {"input": 120, "output": 8}
    assert gen["output"] == "Trabalha na Dhauz." and gen["input"][0]["role"] == "system"
    assert gen["ttft_ms"] is not None and 0 <= gen["ttft_ms"] <= gen["duration_ms"]
    assert gen["duration_ms"] >= 50 and trace["duration_ms"] >= gen["duration_ms"]  # o sleep de 50 ms aparece no tempo
    assert by["retrieval"]["type"] == "retriever" and by["retrieval"]["output"][0]["heading"]

    names = {s["name"]: s for s in trace["scores"]}
    assert len(names) == 8 and names["user_feedback"]["value"] == 1.0 and names["injection_suspect"]["value"] == 0.0
    assert all(isinstance(o["start_ms"], float) and o["start_ms"] >= 0 for o in trace["observations"])


def test_two_traces_are_separated_and_ordered_in_time():
    tracer, client, exporter, scores = pipeline()
    with TestClient(create_app(Settings(provider="echo", model="m"), Slow(), KB, tracer)) as app:
        app.post("/chat", json={"message": "primeira"})
        app.post("/chat", json={"message": "segunda"})
    client.flush()
    traces = spans_to_traces(exporter.get_finished_spans(), scores)
    assert len(traces) == 2 and traces[0]["observations"][0]["input"] == "primeira"
    assert len({t["trace_id"] for t in traces}) == 2


def test_no_spans_gives_no_traces():
    assert spans_to_traces([], []) == []
