"""Mede a recuperação do chat (sem LLM): BM25 (usado no app) vs embeddings vs híbrida.

Uso (na pasta 00-site-chat):

    ../.venv/Scripts/python -m evaluation.run_retrieval                       # só BM25 (o que o app usa)
    ../.venv/Scripts/python -m evaluation.run_retrieval --embedder ollama     # + embeddings locais (nomic-embed-text)
    ../.venv/Scripts/python -m evaluation.run_retrieval --embedder google_genai   # + Google (precisa de GOOGLE_API_KEY)

Métricas: acerto@k (algum trecho esperado entre os k primeiros) e MRR.
"""

from __future__ import annotations

import argparse
import math
import os
import sys
from collections import defaultdict
from pathlib import Path

from app.retrieval import KnowledgeBase, retrieval_query

from .cases import CASES, Case

KNOWLEDGE = Path(__file__).resolve().parent.parent / "knowledge"
RRF_K = 60
KS = (1, 3, 5)


def matches(chunk, case: Case) -> bool:
    return any(chunk.source == src and part.lower() in chunk.heading.lower() for src, part in case.expect)


def make_embedder(kind: str):
    if kind == "ollama":
        from langchain_ollama import OllamaEmbeddings

        return OllamaEmbeddings(model=os.environ.get("LOCAL_EMBEDDING_MODEL", "nomic-embed-text"),
                                base_url=os.environ.get("LOCAL_LLM_BASE_URL", "http://localhost:11434"))
    if kind == "google_genai":
        from langchain_google_genai import GoogleGenerativeAIEmbeddings

        return GoogleGenerativeAIEmbeddings(model=os.environ.get("EMBEDDING_MODEL", "gemini-embedding-001"))
    raise SystemExit(f"embedder desconhecido: {kind}")


def cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    return dot / ((math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b))) or 1.0)


def rank_with(strategy: str, kb: KnowledgeBase, case: Case, vectors, embedder, k: int = 5):
    query = retrieval_query(case.messages)
    chunks = kb.chunks
    lexical = kb.search(query, k=len(chunks))  # ordem BM25 (sem o teto de contexto do app)
    if strategy == "bm25":
        return kb.search(query, k=k)
    qv = embedder.embed_query(query)
    sims = sorted(range(len(chunks)), key=lambda i: cosine(qv, vectors[i]), reverse=True)
    dense = [chunks[i] for i in sims]
    if strategy == "embedding":
        return dense[:k]
    score: dict[int, float] = defaultdict(float)  # híbrida: RRF entre as duas listas
    index = {id(c): i for i, c in enumerate(chunks)}
    for ranking in (lexical, dense):
        for r, chunk in enumerate(ranking, 1):
            score[index[id(chunk)]] += 1 / (RRF_K + r)
    return [chunks[i] for i in sorted(score, key=score.get, reverse=True)[:k]]


def evaluate(kb: KnowledgeBase, strategy: str, vectors=None, embedder=None) -> list[dict]:
    rows = []
    for case in CASES:
        ranked = rank_with(strategy, kb, case, vectors, embedder)
        first = next((i for i, c in enumerate(ranked, 1) if matches(c, case)), None)
        rows.append({"id": case.id, "group": case.group, "first": first, "top": [f"{c.source}:{c.heading}" for c in ranked[:3]]})
    return rows


def summarize(rows: list[dict], group: str | None = None) -> dict:
    rows = [r for r in rows if group is None or r["group"] == group]
    n = len(rows) or 1
    out = {f"hit@{k}": sum(1 for r in rows if r["first"] and r["first"] <= k) / n for k in KS}
    out["mrr"] = sum(1 / r["first"] for r in rows if r["first"]) / n
    out["n"] = len(rows)
    return out


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8", errors="replace")
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--embedder", choices=["ollama", "google_genai"], help="inclui embeddings e híbrida na comparação")
    p.add_argument("--prefix", type=int, default=None, help="radical do BM25 (0 = palavras inteiras); padrão: o do app")
    args = p.parse_args()

    kb = (KnowledgeBase.from_paths([KNOWLEDGE]) if args.prefix is None
          else KnowledgeBase.from_paths([KNOWLEDGE], prefix=args.prefix or None))
    print(f"{len(kb)} trechos · {len(CASES)} perguntas\n")
    strategies = {"bm25": evaluate(kb, "bm25")}
    if args.embedder:
        embedder = make_embedder(args.embedder)
        vectors = embedder.embed_documents([f"{c.heading}\n{c.text}" for c in kb.chunks])
        strategies["embedding"] = evaluate(kb, "embedding", vectors, embedder)
        strategies["híbrida"] = evaluate(kb, "híbrida", vectors, embedder)

    header = f"{'estratégia':<11} {'grupo':<15} {'n':>3} {'acerto@1':>9} {'acerto@3':>9} {'acerto@5':>9} {'MRR':>6}"
    print(header)
    for name, rows in strategies.items():
        for group in (None, "factual", "portfolio", "projetos", "acompanhamento", "morfologia", "en"):
            s = summarize(rows, group)
            print(f"{name:<11} {group or 'todas':<15} {s['n']:>3} {s['hit@1']:>9.2f} {s['hit@3']:>9.2f} {s['hit@5']:>9.2f} {s['mrr']:>6.2f}")
    print("\nPerguntas em que o BM25 não achou o trecho esperado entre os 5 primeiros:")
    for r in strategies["bm25"]:
        if not r["first"]:
            print(f"  {r['id']}: trouxe {r['top']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
