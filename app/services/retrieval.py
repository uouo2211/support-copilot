import logging
import re

import jieba
from fastapi import HTTPException
from rank_bm25 import BM25Okapi
from sqlalchemy import select

from app.config import settings
from app.models import Chunk
from app.providers.ai import embed

jieba.setLogLevel(logging.ERROR)
STOP = {"的", "了", "吗", "请", "如何", "怎么", "是", "在", "和", "与", "我", "我们", "你", "是否", "什么", "有", "支持"}


def tokens(text):
    return [t for t in jieba.lcut(text.lower()) if t.strip() and re.search(r"[\w\u4e00-\u9fff]", t)
            and t not in STOP and not re.fullmatch(r"\d+(?:\.\d+)*", t)]


def retrieve(access, conversation, question):
    rows = access.evidence(conversation, include_unknown=True)
    if not rows:
        return [], "BM25"
    query = tokens(question)
    corpus = [tokens(r.Knowledge.title + " " + r.Chunk.text + " " + r.Revision.topic) for r in rows]
    scores = BM25Okapi(corpus).get_scores(query)
    ranked = sorted(range(len(rows)), key=lambda i: (-scores[i], rows[i].Chunk.id))
    useful = [i for i in ranked if scores[i] > 0 and len(set(query) & set(corpus[i])) >= 1]
    mode = "BM25"
    if settings().embedding_enabled:
        cfg = settings()
        if any(r.Chunk.embedding_space != cfg.embedding_space or r.Chunk.embedding is None for r in rows):
            raise HTTPException(409, "embedding 索引缺失或模型已变更，请先重建索引；不能混用向量空间")
        vector = embed([question])[0]
        # IDs come exclusively from the authorization- and version-filtered candidate set.
        ordered = list(access.db.scalars(select(Chunk.id).where(
            Chunk.id.in_([r.Chunk.id for r in rows]), Chunk.embedding_space == cfg.embedding_space
        ).order_by(Chunk.embedding.cosine_distance(vector))))
        positions = {cid: n for n, cid in enumerate(ordered)}
        rrf = {i: 1 / (60 + n + 1) + 1 / (60 + positions[rows[i].Chunk.id] + 1)
               for n, i in enumerate(ranked)}
        useful.sort(key=lambda i: -rrf[i])
        mode = "BM25 + pgvector / RRF"
    if not useful:
        return [], mode
    top = scores[useful[0]]
    selected = [rows[i] for i in useful if scores[i] >= max(0.2, top * 0.45)][:5]
    # Conflict checks must include all authorized claims, not just top-k snippets.
    keys = {r.Revision.claim_key for r in selected if r.Revision.claim_key}
    for row in rows:
        if row.Revision.claim_key in keys and row not in selected:
            selected.append(row)
    return selected, mode
