"""Page-tagged retrieval over an annual report.

BM25 keyword search is always on: finance terms ('pledged', 'qualified
opinion') need exact matches. If sentence-transformers is installed (offline
pipeline), dense scores are blended in and an optional cross-encoder reranks.
The API at runtime uses BM25 only, so it stays light enough for serverless.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from rank_bm25 import BM25Okapi

_TOKEN = re.compile(r"[a-z0-9]+(?:\.[0-9]+)?")


def tokenize(text: str) -> list[str]:
    return _TOKEN.findall(text.lower())


@dataclass
class Chunk:
    page: int
    text: str


def chunk_pages(pages: dict[int, str], size: int = 1200, overlap: int = 200) -> list[Chunk]:
    chunks: list[Chunk] = []
    for page, text in sorted(pages.items()):
        text = re.sub(r"[ \t]+", " ", text).strip()
        if not text:
            continue
        start = 0
        while start < len(text):
            end = min(len(text), start + size)
            if end < len(text):  # break on a line or sentence end near the limit
                cut = max(text.rfind("\n", start + size // 2, end), text.rfind(". ", start + size // 2, end))
                if cut > start:
                    end = cut + 1
            chunks.append(Chunk(page, text[start:end].strip()))
            if end >= len(text):
                break
            start = max(end - overlap, start + 1)
    return chunks


class ReportIndex:
    def __init__(self, pages: dict[int, str], *, dense_model=None, reranker=None):
        self.pages = pages
        self.chunks = chunk_pages(pages)
        self._bm25 = BM25Okapi([tokenize(c.text) for c in self.chunks]) if self.chunks else None
        self._dense = dense_model
        self._reranker = reranker
        self._emb = None
        if dense_model is not None and self.chunks:
            self._emb = dense_model.encode([c.text for c in self.chunks], normalize_embeddings=True, show_progress_bar=False)

    def search(self, query: str, k: int = 6) -> list[Chunk]:
        if not self._bm25:
            return []
        import numpy as np

        scores = np.asarray(self._bm25.get_scores(tokenize(query)), dtype=float)
        if scores.max() > 0:
            scores = scores / scores.max()
        if self._emb is not None:
            q = self._dense.encode([query], normalize_embeddings=True, show_progress_bar=False)[0]
            dense = self._emb @ q
            scores = 0.5 * scores + 0.5 * dense
        idx = list(np.argsort(-scores)[: max(k * 4, k)])
        if self._reranker is not None:
            pairs = [(query, self.chunks[i].text) for i in idx]
            rr = self._reranker.predict(pairs)
            idx = [i for _, i in sorted(zip(rr, idx), key=lambda t: -t[0])]
        out, seen = [], set()
        for i in idx:
            if scores[i] <= 0 and self._reranker is None:
                continue
            key = (self.chunks[i].page, self.chunks[i].text[:80])
            if key not in seen:
                seen.add(key)
                out.append(self.chunks[i])
            if len(out) >= k:
                break
        return out

    def search_many(self, queries: list[str], k: int = 8) -> list[Chunk]:
        merged: list[Chunk] = []
        seen = set()
        per = max(2, k // max(1, len(queries)) + 1)
        for q in queries:
            for c in self.search(q, per):
                key = (c.page, c.text[:80])
                if key not in seen:
                    seen.add(key)
                    merged.append(c)
        return merged[:k]
