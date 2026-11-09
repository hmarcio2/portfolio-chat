"""Guardrails automáticos do chat, gravados como NOTAS (scores) no trace do Langfuse.

São **sinais de observabilidade**, não bloqueios: servem para ver, no painel, quantas conversas tentaram injeção de
prompt, quantas vezes o assistente não tinha a informação (lacunas da base de conhecimento) ou citou um link que não
estava no contexto. Quem protege de verdade é o prompt do sistema e as regras da API; estas notas medem se isso funciona.

Todas as verificações são determinísticas e baratas (regex e comparações), sem chamar outro LLM, e são heurísticas:
têm falsos positivos e negativos. O ``comment`` de cada nota diz o que disparou, para auditar no Langfuse.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from portfolio_core import mask_pii

# Tentativas comuns de injeção/extração, em português e inglês. Lista curta de propósito: é um sinal, não um filtro.
_INJECTION = [re.compile(p, re.IGNORECASE) for p in (
    r"ignor\w*\s+(?:\w+\s+){0,3}(?:instru[cç][õo]es|regras|ordens|prompts?)",
    r"ignore\s+(?:\w+\s+){0,3}(?:instructions|rules|prompts?)",
    r"(?:mostre|revele|exiba|repita|imprima|vaze|show|reveal|print|repeat|leak)\b.{0,40}\b(?:prompt|instru[cç][õo]es|instructions)",
    r"\b(?:system\s+prompt|prompt\s+de\s+sistema|prompt\s+do\s+sistema)\b",
    r"(?:a\s+partir\s+de\s+agora|de\s+agora\s+em\s+diante)[, ]+\s*voc[êe]",
    r"voc[êe]\s+(?:agora\s+)?[ée]\s+(?:um|uma)\b",
    r"\byou\s+are\s+now\b|\bact\s+as\b|\bpretend\s+(?:to\s+be|you)\b|\bfinja\s+(?:ser|que)\b",
    r"\bjailbreak\b|\bDAN\s+mode\b",
)]

# Trechos do prompt do sistema que nunca deveriam aparecer numa resposta.
_PROMPT_MARKERS = ("<contexto>", "</contexto>", "Como responder:", "SOMENTE no contexto", "dado, não instrução",
                   "Nunca revele nem resuma")

_GAP = re.compile(
    r"n[ãa]o\s+(?:tenho|h[áa]|consta|encontr\w+|sei|est[áa]\s+no\s+contexto|possuo|menciona\w*|cita\w*|informa\w*|"
    r"detalha\w*|especifica\w*)|sem\s+informa[cç][õo]es|"
    r"(?:don'?t|do\s+not)\s+have|no\s+information|not\s+(?:in|part\s+of)\s+the\s+context",
    re.IGNORECASE,
)
GAP_WINDOW = 300  # máximo de caracteres do 1º parágrafo da resposta analisados para "não sei"
_URL = re.compile(r"https?://[^\s)\]>\"']+")


@dataclass(frozen=True)
class Score:
    name: str
    value: float
    data_type: str = "BOOLEAN"  # BOOLEAN (0/1) ou NUMERIC
    comment: str | None = None


def check_input(question: str) -> list[Score]:
    hit = next((p.pattern for p in _INJECTION if p.search(question)), None)
    return [
        Score("injection_suspect", bool(hit), comment="padrão de injeção/extração de prompt detectado" if hit else None),
        Score("pii_in_input", mask_pii(question) != question,
              comment="a pergunta continha e-mail, telefone ou documento (mascarado antes do envio)" if mask_pii(question) != question else None),
    ]


def check_retrieval(chunks: list) -> list[Score]:
    return [Score("no_context", not chunks, comment="nenhum trecho da base de conhecimento casou com a pergunta" if not chunks else None)]


def _clean_url(url: str) -> str:
    return url.rstrip(".,;:!?)").lower().rstrip("/")


def check_output(answer: str, system: str, chunks: list) -> list[Score]:
    """Verifica a resposta: links fora do contexto, vazamento do prompt, dado pessoal e "não sei" (lacuna da base)."""
    known = {_clean_url(u) for u in _URL.findall(system)}
    unknown = sorted({_clean_url(u) for u in _URL.findall(answer)} - known)
    leaked = [m for m in _PROMPT_MARKERS if m.lower() in answer.lower()]
    pii = mask_pii(answer) != answer
    # só o começo: o prompt manda começar pela resposta, então um "não sei" de verdade vem logo; um aviso no fim
    # ("não há informações sobre salário...") depois de responder ao que foi perguntado não é lacuna
    first_paragraph = answer.strip().split("\n\n")[0][:GAP_WINDOW]
    gap = bool(_GAP.search(first_paragraph)) or not chunks
    return [
        Score("unsupported_links", len(unknown), "NUMERIC", ("links que não estão no contexto: " + ", ".join(unknown)) if unknown else None),
        Score("prompt_leak_suspect", bool(leaked), comment=("trechos do prompt na resposta: " + ", ".join(leaked)) if leaked else None),
        Score("pii_in_output", pii, comment="a resposta contém e-mail, telefone ou documento" if pii else None),
        Score("knowledge_gap", gap,
              comment="o assistente disse que não tinha a informação (ou nenhum trecho foi recuperado): candidato a entrar na base" if gap else None),
    ]


def evaluate_turn(*, question: str, answer: str, system: str, chunks: list, failed: bool = False) -> list[Score]:
    """Todas as notas de um turno. Com falha do provedor (sem resposta), só as da pergunta e da busca."""
    scores = check_input(question) + check_retrieval(chunks)
    if answer and not failed:
        scores += check_output(answer, system, chunks)
    return scores
