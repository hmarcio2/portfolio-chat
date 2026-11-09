import json
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import SYSTEM_PROMPT, create_app
from app.retrieval import MAX_CHUNK_CHARS, MAX_CONTEXT_CHARS, KnowledgeBase, _split_long, _split_markdown, retrieval_query
from evaluation.cases import CASES
from evaluation.run_answers import CASES as ANSWER_CASES
from evaluation.run_retrieval import evaluate, matches, summarize
from portfolio_core import LLMChunk, Settings

KNOWLEDGE = Path(__file__).resolve().parent.parent / "knowledge"


@pytest.fixture(scope="module")
def kb():
    return KnowledgeBase.from_paths([KNOWLEDGE])


# ---------- divisão em trechos ----------

def test_long_sections_are_split_and_short_ones_kept():
    text = "\n\n".join(f"Parágrafo {i} " + "x" * 300 for i in range(8))
    parts = _split_long(text, 1000)
    assert len(parts) > 1 and all(len(p) <= 1000 for p in parts)
    assert _split_long("curto", 1000) == ["curto"]


def test_a_single_very_long_line_is_split_by_sentence_and_loses_nothing():
    line = " ".join(f"Frase número {i} sobre o assunto." for i in range(120))  # uma linha só, ~4 mil caracteres
    parts = _split_long(line, 1000)
    assert len(parts) >= 4 and all(len(p) <= 1000 for p in parts)
    assert " ".join(parts).split() == line.split()  # nenhuma palavra perdida ou duplicada
    giant_word_run = "palavra " * 400                  # sem pontuação nenhuma: cai na quebra por palavra
    assert all(len(p) <= 1000 for p in _split_long(giant_word_run, 1000))


def test_chunks_respect_the_size_cap(kb):
    assert all(len(c.text) <= MAX_CHUNK_CHARS for c in kb.chunks)


def test_html_comments_are_not_indexed(kb):
    assert not any("Mantenedor" in c.text or "<!--" in c.text for c in kb.chunks)
    assert _split_markdown("a.md", "# T\n<!-- segredo do mantenedor -->\ntexto")[0].text == "texto"


# ---------- consulta de busca ----------

def test_retrieval_query_joins_previous_message_only_when_last_is_short():
    assert retrieval_query([]) == ""
    assert retrieval_query(["Onde ele trabalha hoje na empresa?"]) == "Onde ele trabalha hoje na empresa?"
    assert retrieval_query(["Fale do projeto DSS", "e a stack?"]) == "Fale do projeto DSS e a stack?"
    long_last = "Quais tecnologias ele usou nesse projeto de agentes?"
    assert retrieval_query(["Fale do projeto DSS", long_last]) == long_last


def test_context_is_capped(kb):
    chunks = kb.search("projeto agente dados IA ML Docker FastAPI", k=40)
    assert sum(len(c.text) for c in chunks) <= MAX_CONTEXT_CHARS or len(chunks) == 1


# ---------- conteúdo: privacidade e atualidade ----------

def test_knowledge_has_no_personal_contact_data(kb):
    blob = "\n".join(c.text for c in kb.chunks)
    assert "@gmail" not in blob and not re.search(r"\(?\d{2}\)?\s?9?\d{4}[-\s]?\d{4}", blob)  # e-mail e telefone
    assert "linkedin.com/in/heribertomarcio" in blob


def test_projects_doc_is_not_stale(kb):
    blob = "\n".join(c.text for c in kb.chunks)
    assert "nada foi implementado" not in blob
    assert "ainda não existem" in blob or "planejados" in blob


def test_knowledge_covers_english_and_portfolio_topics(kb):
    sources = {c.source for c in kb.chunks}
    assert {"perfil.md", "profile.en.md", "portfolio.md", "projetos.md"} <= sources


# ---------- avaliação de recuperação como teste de regressão ----------

def test_every_expected_heading_exists(kb):
    for case in CASES:
        assert any(matches(c, case) for c in kb.chunks), f"{case.id}: nenhum trecho corresponde a {case.expect}"


def test_bm25_retrieval_quality_does_not_regress(kb):
    rows = evaluate(kb, "bm25")
    overall = summarize(rows)
    assert overall["hit@5"] >= 0.97, [r["id"] for r in rows if not r["first"]]
    assert overall["hit@3"] >= 0.88
    assert summarize(rows, "en")["hit@5"] == 1.0 and summarize(rows, "acompanhamento")["hit@3"] == 1.0


def test_case_ids_are_unique():
    assert len({c.id for c in CASES}) == len(CASES) and len({c.id for c in ANSWER_CASES}) == len(ANSWER_CASES)


# ---------- prompt ----------

def test_system_prompt_has_the_guardrails():
    for must in ("SOMENTE", "LinkedIn", "Nunca revele", "dado, não instrução", "no ar", "Salário"):
        assert must in SYSTEM_PROMPT, must


# ---------- API: fontes e perguntas de acompanhamento ----------

class Capture:
    def __init__(self):
        self.systems = []

    async def stream(self, *, system, messages, tools=None):
        self.systems.append(system)
        yield LLMChunk(text="ok")
        yield LLMChunk(done=True, stop_reason="end_turn")


def parse_sse(text):
    out = []
    for block in text.strip().split("\n\n"):
        name, data = block.split("\n", 1)
        out.append((name.removeprefix("event: "), json.loads(data.removeprefix("data: "))))
    return out


def test_sources_event_lists_consulted_headings(kb):
    with TestClient(create_app(Settings(provider="echo"), Capture(), kb)) as client:
        events = parse_sse(client.post("/chat", json={"message": "Quais tecnologias ele usou no projeto DSS?"}).text)
    names = [n for n, _ in events]
    assert names[:2] == ["meta", "sources"] and names[-1] == "done"
    assert any("Projeto DSS" in s for s in events[1][1]["sources"])


def test_follow_up_question_retrieves_with_previous_context(kb):
    capture = Capture()
    with TestClient(create_app(Settings(provider="echo"), capture, kb)) as client:
        first = parse_sse(client.post("/chat", json={"message": "Fale do projeto DSS"}).text)
        sid = first[0][1]["session_id"]
        client.post("/chat", json={"message": "e a stack?", "session_id": sid})
    assert "Projeto DSS" in capture.systems[1]  # "e a stack?" sozinha não acharia o DSS


def test_no_sources_event_when_nothing_matches(kb):
    with TestClient(create_app(Settings(provider="echo"), Capture(), kb)) as client:
        events = parse_sse(client.post("/chat", json={"message": "xyzzy plugh"}).text)
    assert "sources" not in [n for n, _ in events]


def test_word_variants_find_the_right_section_in_the_real_knowledge(kb):
    """Regressão: "Onde ele trabalha?" não recuperava nada, porque a base só dizia "Experiência atual"."""
    for question, heading in [("Onde ele trabalha?", "Experiência atual"), ("Em qual empresa ele atua?", "Experiência atual"),
                              ("Ele já trabalhou com agentes de IA?", "Projeto DSS"), ("Ele estudou onde?", "Formação")]:
        assert any(heading in c.heading for c in kb.search(question)), question


def test_morphology_group_is_part_of_the_regression_guard(kb):
    rows = evaluate(kb, "bm25")
    assert summarize(rows, "morfologia")["hit@5"] == 1.0 and summarize(rows)["hit@5"] >= 0.97
