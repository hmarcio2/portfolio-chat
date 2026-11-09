"""Recuperação de trechos para o RAG do chat.

BM25 (``portfolio_core.bm25``) sobre arquivos Markdown, sem banco vetorial: o corpus tem algumas dezenas
de trechos, e a medição em ``evaluation/`` mostra se isso basta. A interface (``KnowledgeBase.search``) é a que
uma busca vetorial teria, então trocar o motor não muda o app.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from portfolio_core.bm25 import BM25Index, tokenize

MAX_CHUNK_CHARS = 1000   # trechos maiores são divididos: prompts curtos e busca mais precisa
MAX_CONTEXT_CHARS = 5000  # teto do que vai para o prompt
STEM_PREFIX = 6          # radical por truncamento no BM25 ("trabalha"/"trabalhou" -> "trabal"); medido em evaluation/ de sistema
_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)


@dataclass(frozen=True)
class Chunk:
    source: str
    heading: str
    text: str

    @property
    def label(self) -> str:
        return self.heading


def _split_sentences(piece: str, limit: int) -> list[str]:
    """Uma linha maior que ``limit`` (parágrafo corrido) é quebrada por frase e, em último caso, por palavra."""
    if len(piece) <= limit:
        return [piece]
    out, current = [], ""
    for sentence in re.split(r"(?<=[.!?;])\s+", piece):
        for word_group in ([sentence] if len(sentence) <= limit else _split_words(sentence, limit)):
            candidate = f"{current} {word_group}" if current else word_group
            if current and len(candidate) > limit:
                out.append(current)
                current = word_group
            else:
                current = candidate
    if current:
        out.append(current)
    return out


def _split_words(text: str, limit: int) -> list[str]:
    out, current = [], ""
    for word in text.split():
        candidate = f"{current} {word}" if current else word
        if current and len(candidate) > limit:
            out.append(current)
            current = word
        else:
            current = candidate
    return out + ([current] if current else [])


def _split_long(text: str, limit: int) -> list[str]:
    """Divide por parágrafos e, se preciso, por linhas, sem passar de ``limit`` caracteres por parte."""
    if len(text) <= limit:
        return [text]
    parts, current = [], ""
    pieces = [line for para in text.split("\n\n") for line in ([para] if len(para) <= limit else para.split("\n"))]
    pieces = [small for piece in pieces for small in _split_sentences(piece, limit)]
    for piece in pieces:
        candidate = f"{current}\n\n{piece}" if current else piece
        if current and len(candidate) > limit:
            parts.append(current)
            current = piece
        else:
            current = candidate
    if current:
        parts.append(current)
    return parts


def _split_markdown(source: str, content: str) -> list[Chunk]:
    chunks: list[Chunk] = []
    heading, lines = source, []

    def flush():
        body = "\n".join(lines).strip()
        for part in _split_long(body, MAX_CHUNK_CHARS) if body else []:
            chunks.append(Chunk(source, heading, part))

    for line in _COMMENT.sub("", content).splitlines():
        if re.match(r"^#{1,3} ", line):
            flush()
            heading, lines = line.lstrip("# ").strip(), []
        else:
            lines.append(line)
    flush()
    return chunks


def retrieval_query(user_messages: Sequence[str]) -> str:
    """Pergunta de busca: a última mensagem; se for curta demais ("e a stack dele?"), junta a anterior."""
    if not user_messages:
        return ""
    last = user_messages[-1]
    if len(tokenize(last)) < 4 and len(user_messages) > 1:
        return f"{user_messages[-2]} {last}"
    return last


class KnowledgeBase:
    def __init__(self, chunks: list[Chunk], prefix: int | None = STEM_PREFIX):
        self._chunks = chunks
        # o título conta em dobro: perguntas costumam citar o assunto da seção
        self._index = BM25Index([f"{c.heading} {c.heading} {c.text}" for c in chunks], prefix=prefix)

    @classmethod
    def from_paths(cls, paths: list[Path], prefix: int | None = STEM_PREFIX) -> "KnowledgeBase":
        files: list[Path] = []
        for p in paths:
            if p.is_dir():
                files.extend(sorted(p.glob("*.md")))
            elif p.is_file():
                files.append(p)
        chunks: list[Chunk] = []
        for f in files:
            chunks.extend(_split_markdown(f.name, f.read_text(encoding="utf-8")))
        return cls(chunks, prefix)

    def __len__(self) -> int:
        return len(self._chunks)

    @property
    def chunks(self) -> list[Chunk]:
        return list(self._chunks)

    def search(self, query: str, k: int = 5) -> list[Chunk]:
        """Os ``k`` trechos mais relevantes, limitados a ``MAX_CONTEXT_CHARS`` no total."""
        picked, total = [], 0
        for i, _ in self._index.search(query, k):
            chunk = self._chunks[i]
            if picked and total + len(chunk.text) > MAX_CONTEXT_CHARS:
                break
            picked.append(chunk)
            total += len(chunk.text)
        return picked
