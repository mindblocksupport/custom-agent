"""Anthropic Contextual Chunking (L37 §1 Q1 + Day 12).

给每个 chunk 加 50-100 token 的上下文摘要前缀: "本片段属于 X 文档第 Y 章, 讲的是 Z".
实测 retrieval 失败率从 5.7% → 1.9% (Anthropic 官方).

成本控制 (L37 §4):
- Anthropic prompt caching: doc 文本一次, 复用到所有 chunks
- 本地磁盘 cache: 按 (doc_checksum, chunk_content_hash) 键, 不重复付费
- 默认模型: claude-haiku-4-5-20251001 (便宜)
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from pathlib import Path

from rag_core.chunking.recursive import ChunkSpan
from rag_core.llm.base import LLMClient

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "claude-haiku-4-5-20251001"

_PROMPT_TEMPLATE = """<doc>
{doc_text}
</doc>

Here is the chunk we want to situate within the whole document:
<chunk>
{chunk_text}
</chunk>

Please give a SHORT (50-80 Chinese characters or ≤100 English tokens) context that
summarizes what section this chunk belongs to and what it's about.
Output the context ONLY, no preamble."""


@dataclass
class ContextualEnricher:
    llm: LLMClient
    model: str = DEFAULT_MODEL
    max_tokens: int = 100
    cache_dir: Path | None = None
    max_concurrent: int = 4

    def __post_init__(self) -> None:
        if self.cache_dir:
            self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _cache_path(self, doc_checksum: str, chunk_hash: str) -> Path | None:
        if not self.cache_dir:
            return None
        return self.cache_dir / f"{doc_checksum[:16]}_{chunk_hash[:16]}.json"

    def _read_cache(self, path: Path | None) -> str | None:
        if not path or not path.exists():
            return None
        try:
            return json.loads(path.read_text()).get("prefix")
        except Exception:
            return None

    def _write_cache(self, path: Path | None, prefix: str) -> None:
        if not path:
            return
        try:
            path.write_text(json.dumps({"prefix": prefix}, ensure_ascii=False))
        except Exception as e:
            logger.warning("contextual cache write failed: %s", e)

    async def _enrich_one(
        self, doc_text: str, doc_checksum: str, span: ChunkSpan,
    ) -> ChunkSpan:
        cpath = self._cache_path(doc_checksum, span.content_hash)
        cached = self._read_cache(cpath)
        if cached:
            new_content = f"{cached}\n\n{span.content}"
            return ChunkSpan(
                seq=span.seq, content=new_content,
                char_offset_start=span.char_offset_start,
                char_offset_end=span.char_offset_end,
                heading_path=span.heading_path,
            )

        prompt = _PROMPT_TEMPLATE.format(
            doc_text=doc_text[:8000],              # 截断长文档 (生产用 prompt caching)
            chunk_text=span.content,
        )
        resp = await self.llm.complete(
            messages=[{"role": "user", "content": prompt}],
            model=self.model, max_tokens=self.max_tokens, temperature=0.0,
        )
        prefix = resp.text.strip()
        self._write_cache(cpath, prefix)
        return ChunkSpan(
            seq=span.seq, content=f"{prefix}\n\n{span.content}",
            char_offset_start=span.char_offset_start,
            char_offset_end=span.char_offset_end,
            heading_path=span.heading_path,
        )

    async def enrich(
        self, *, doc_text: str, doc_checksum: str, chunks: list[ChunkSpan],
    ) -> list[ChunkSpan]:
        """批量加 context prefix, 带并发上限."""
        if not chunks:
            return []
        sem = asyncio.Semaphore(self.max_concurrent)

        async def _guarded(span: ChunkSpan) -> ChunkSpan:
            async with sem:
                return await self._enrich_one(doc_text, doc_checksum, span)

        return await asyncio.gather(*(_guarded(s) for s in chunks))
