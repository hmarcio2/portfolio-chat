"""Converte os spans OpenTelemetry que o SDK do Langfuse produz (e as notas interceptadas) em JSON simples.

Serve para **documentar** os traces sem um servidor Langfuse no ar: o JSON tem exatamente o que o Langfuse receberia
(nomes, tempos, entrada/saída, modelo, tokens, nível, tags, sessão) e alimenta o visualizador estático em
``docs/observabilidade/``. Não é uma captura da interface do Langfuse.
"""

from __future__ import annotations

import json
from collections import defaultdict
from typing import Any

_META_PREFIX = "langfuse.observation.metadata."


def _loads(value: Any) -> Any:
    """Os atributos do SDK guardam objetos como texto JSON; devolve o objeto, ou o texto se não for JSON."""
    if isinstance(value, str):
        try:
            return json.loads(value)
        except ValueError:
            return value
    return value


def _ms(ns: int, origin_ns: int) -> float:
    return round((ns - origin_ns) / 1e6, 2)


def spans_to_traces(spans: list[Any], scores: list[dict] | None = None) -> list[dict]:
    """``spans``: ``ReadableSpan``s (ex.: do InMemorySpanExporter); ``scores``: payloads de POST /api/public/scores."""
    by_trace: dict[str, list[Any]] = defaultdict(list)
    for span in spans:
        by_trace[format(span.context.trace_id, "032x")].append(span)

    scores_by_trace: dict[str, list[dict]] = defaultdict(list)
    for s in scores or []:
        scores_by_trace[s["traceId"]].append({
            "name": s["name"], "value": s["value"], "data_type": s.get("dataType"), "comment": s.get("comment"),
        })

    traces = []
    for trace_id, group in by_trace.items():
        group.sort(key=lambda s: s.start_time)
        origin = group[0].start_time
        root = next((s for s in group if s.parent is None), group[0])
        observations = []
        for s in group:
            a = dict(s.attributes or {})
            ttft = None
            if "langfuse.observation.completion_start_time" in a:  # tempo até o primeiro token
                from datetime import datetime

                started = datetime.fromisoformat(str(_loads(a["langfuse.observation.completion_start_time"])).replace("Z", "+00:00"))
                ttft = round(started.timestamp() * 1000 - (s.start_time / 1e6), 1)
            observations.append({
                "id": format(s.context.span_id, "016x"),
                "parent_id": format(s.parent.span_id, "016x") if s.parent else None,
                "name": s.name,
                "type": a.get("langfuse.observation.type", "span"),
                "start_ms": _ms(s.start_time, origin),
                "duration_ms": round((s.end_time - s.start_time) / 1e6, 2),
                "model": a.get("langfuse.observation.model.name"),
                "model_parameters": _loads(a.get("langfuse.observation.model.parameters")),
                "usage": _loads(a.get("langfuse.observation.usage_details")),
                "ttft_ms": ttft,
                "input": _loads(a.get("langfuse.observation.input")),
                "output": _loads(a.get("langfuse.observation.output")),
                "metadata": {k[len(_META_PREFIX):]: _loads(v) for k, v in a.items() if k.startswith(_META_PREFIX)},
                "level": a.get("langfuse.observation.level"),
                "status_message": a.get("langfuse.observation.status_message"),
            })
        ra = dict(root.attributes or {})
        tags = ra.get("langfuse.trace.tags") or ()
        traces.append({
            "trace_id": trace_id,
            "name": ra.get("langfuse.trace.name", root.name),
            "session_id": ra.get("session.id"),
            "environment": ra.get("langfuse.environment"),
            "tags": list(tags),
            "duration_ms": round((root.end_time - root.start_time) / 1e6, 2),
            "observations": observations,
            "scores": scores_by_trace.get(trace_id, []),
        })
    traces.sort(key=lambda t: t["observations"][0]["start_ms"] if t["observations"] else 0)
    return traces
