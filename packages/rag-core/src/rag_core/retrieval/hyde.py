"""HyDE (Hypothetical Document Embeddings, Gao et al. 2022).

流程: query → LLM 先想象一段假答案 → 对假答案 embedding → 用假答案向量做 dense 检索.
直觉: 假答案跟真文档更语义接近 (同为"答案语域"), 比 query 跟文档直接配对命中率高.

L37 §8.4: 仅在单 dense 召回 < 阈值时启 (贵, 多一次 LLM 调用).
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from rag_core.embedding.base import EmbeddingProvider
from rag_core.llm.base import LLMClient
from rag_core.storage.pgvector_store import PgVectorStore
from rag_core.types import SearchHit

DEFAULT_MODEL = "deepseek/deepseek-chat"

_HYDE_PROMPT = """Please write a short hypothetical passage that would directly answer the following question.
Do not hedge or add caveats — write as if the answer is in a knowledge base article.
Keep it to 3-5 sentences.

Question: {query}

Hypothetical passage:"""


@dataclass
class HyDERetriever:
    """HyDE wrapper.

    在 base dense 检索之前, 先让 LLM 生成 hypothetical passage, 再以其 embedding 做检索.
    """

    store: PgVectorStore
    embedder: EmbeddingProvider
    llm: LLMClient
    model: str = DEFAULT_MODEL
    max_tokens: int = 200

    async def search(
        self,
        *,
        query: str,
        tenant_id: UUID,
        principals: list[str],
        k: int = 5,
        filters: dict | None = None,
    ) -> list[SearchHit]:
        resp = await self.llm.complete(
            messages=[{"role": "user", "content": _HYDE_PROMPT.format(query=query)}],
            model=self.model, max_tokens=self.max_tokens, temperature=0.0,
        )
        hypo = resp.text.strip() or query
        [vec] = self.embedder.encode([hypo])
        return self.store.dense_search(
            tenant_id=tenant_id,
            query_embedding=vec,
            principals=principals,
            k=k,
            filters=filters,
        )
