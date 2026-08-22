import hashlib
import json
import math
import re
from collections import Counter, defaultdict
from functools import lru_cache
from pathlib import Path
from typing import Protocol

from app.core.config import Settings, get_settings
from app.domain.models import KnowledgeDocument, RetrievedContext


def tokenize(text: str) -> list[str]:
    text = text.lower()
    ascii_words = re.findall(r"[a-z0-9]+", text)
    chinese = re.findall(r"[\u4e00-\u9fff]", text)
    bigrams = ["".join(chinese[index : index + 2]) for index in range(len(chinese) - 1)]
    return ascii_words + chinese + bigrams


class EmbeddingProvider(Protocol):
    dimension: int

    def embed(self, texts: list[str]) -> list[list[float]]: ...


class HashEmbeddingProvider:
    """Dependency-free deterministic embedding for tests and local demos."""

    def __init__(self, dimension: int = 128) -> None:
        self.dimension = dimension

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._embed_one(text) for text in texts]

    def _embed_one(self, text: str) -> list[float]:
        vector = [0.0] * self.dimension
        for token in tokenize(text):
            digest = hashlib.blake2b(token.encode(), digest_size=8).digest()
            value = int.from_bytes(digest, "big")
            index = value % self.dimension
            vector[index] += 1.0 if (value >> 8) % 2 else -1.0
        norm = math.sqrt(sum(item * item for item in vector)) or 1.0
        return [item / norm for item in vector]


class SentenceTransformerEmbeddingProvider:
    def __init__(self, model_name: str) -> None:
        from sentence_transformers import SentenceTransformer

        self.model = SentenceTransformer(model_name)
        self.dimension = int(self.model.get_sentence_embedding_dimension())

    def embed(self, texts: list[str]) -> list[list[float]]:
        vectors = self.model.encode(texts, normalize_embeddings=True)
        return [vector.tolist() for vector in vectors]


def cosine(left: list[float], right: list[float]) -> float:
    return sum(a * b for a, b in zip(left, right, strict=True))


class InMemoryHybridRetriever:
    def __init__(
        self,
        documents: list[KnowledgeDocument] | None = None,
        embedding_provider: EmbeddingProvider | None = None,
        rrf_k: int = 60,
    ) -> None:
        self.embedding_provider = embedding_provider or HashEmbeddingProvider()
        self.rrf_k = rrf_k
        self.documents: dict[str, KnowledgeDocument] = {}
        self.vectors: dict[str, list[float]] = {}
        if documents:
            self.upsert(documents)

    def upsert(self, documents: list[KnowledgeDocument]) -> None:
        vectors = self.embedding_provider.embed(
            [f"{doc.title}\n{doc.content}" for doc in documents]
        )
        for document, vector in zip(documents, vectors, strict=True):
            self.documents[document.doc_id] = document
            self.vectors[document.doc_id] = vector

    def search(
        self,
        query: str,
        brand_id: str,
        category: str | None = None,
        limit: int = 4,
    ) -> list[RetrievedContext]:
        candidates = [
            document
            for document in self.documents.values()
            if document.brand_id == brand_id
            and (not category or document.category in {"global", category})
        ]
        if not candidates:
            return []
        sparse_scores = self._bm25(query, candidates)
        query_vector = self.embedding_provider.embed([query])[0]
        dense_scores = {
            document.doc_id: cosine(query_vector, self.vectors[document.doc_id])
            for document in candidates
        }
        sparse_rank = [
            doc_id
            for doc_id, score in sorted(
                sparse_scores.items(), key=lambda item: item[1], reverse=True
            )
            if score > 0
        ]
        dense_rank = [
            doc_id
            for doc_id, _ in sorted(
                dense_scores.items(), key=lambda item: item[1], reverse=True
            )
        ]
        fused: defaultdict[str, float] = defaultdict(float)
        for ranking in (sparse_rank, dense_rank):
            for rank, doc_id in enumerate(ranking, start=1):
                fused[doc_id] += 1 / (self.rrf_k + rank)
        ordered = sorted(fused, key=fused.get, reverse=True)[:limit]
        return [
            RetrievedContext(
                doc_id=doc_id,
                title=self.documents[doc_id].title,
                content=self.documents[doc_id].content,
                source=self.documents[doc_id].source,
                score=fused[doc_id],
            )
            for doc_id in ordered
        ]

    @staticmethod
    def _bm25(
        query: str, documents: list[KnowledgeDocument], k1: float = 1.5, b: float = 0.75
    ) -> dict[str, float]:
        tokenized = {doc.doc_id: tokenize(f"{doc.title} {doc.content}") for doc in documents}
        average_length = sum(map(len, tokenized.values())) / len(documents)
        frequencies = {doc_id: Counter(tokens) for doc_id, tokens in tokenized.items()}
        document_frequency = Counter()
        for tokens in tokenized.values():
            document_frequency.update(set(tokens))
        scores: dict[str, float] = {}
        query_tokens = tokenize(query)
        for document in documents:
            doc_tokens = tokenized[document.doc_id]
            score = 0.0
            for token in query_tokens:
                frequency = frequencies[document.doc_id][token]
                if not frequency:
                    continue
                df = document_frequency[token]
                idf = math.log(1 + (len(documents) - df + 0.5) / (df + 0.5))
                denominator = frequency + k1 * (
                    1 - b + b * len(doc_tokens) / max(average_length, 1)
                )
                score += idf * frequency * (k1 + 1) / denominator
            scores[document.doc_id] = score
        return scores


class MilvusHybridRetriever:
    """Milvus dense + native BM25 sparse retrieval with RRF reranking."""

    def __init__(self, settings: Settings, embedding_provider: EmbeddingProvider) -> None:
        from pymilvus import MilvusClient

        self.settings = settings
        self.embedding_provider = embedding_provider
        self.client = MilvusClient(uri=settings.milvus_uri, token=settings.milvus_token)
        self._ensure_collection()

    def _ensure_collection(self) -> None:
        from pymilvus import DataType, Function, FunctionType, MilvusClient

        name = self.settings.milvus_collection
        if self.client.has_collection(name):
            return
        schema = MilvusClient.create_schema(auto_id=False, enable_dynamic_field=False)
        schema.add_field("doc_id", DataType.VARCHAR, max_length=128, is_primary=True)
        schema.add_field("brand_id", DataType.VARCHAR, max_length=64)
        schema.add_field("category", DataType.VARCHAR, max_length=80)
        schema.add_field("title", DataType.VARCHAR, max_length=200)
        schema.add_field("source", DataType.VARCHAR, max_length=300)
        schema.add_field("content", DataType.VARCHAR, max_length=8000, enable_analyzer=True)
        schema.add_field("dense", DataType.FLOAT_VECTOR, dim=self.embedding_provider.dimension)
        schema.add_field("sparse", DataType.SPARSE_FLOAT_VECTOR)
        schema.add_function(
            Function(
                name="content_bm25",
                input_field_names=["content"],
                output_field_names=["sparse"],
                function_type=FunctionType.BM25,
            )
        )
        indexes = MilvusClient.prepare_index_params()
        indexes.add_index("dense", index_type="AUTOINDEX", metric_type="COSINE")
        indexes.add_index("sparse", index_type="SPARSE_INVERTED_INDEX", metric_type="BM25")
        self.client.create_collection(collection_name=name, schema=schema, index_params=indexes)

    def upsert(self, documents: list[KnowledgeDocument]) -> None:
        vectors = self.embedding_provider.embed(
            [f"{doc.title}\n{doc.content}" for doc in documents]
        )
        rows = [
            {**document.model_dump(), "dense": vector}
            for document, vector in zip(documents, vectors, strict=True)
        ]
        self.client.upsert(collection_name=self.settings.milvus_collection, data=rows)

    def search(
        self,
        query: str,
        brand_id: str,
        category: str | None = None,
        limit: int = 4,
    ) -> list[RetrievedContext]:
        from pymilvus import AnnSearchRequest, Function, FunctionType

        escaped_brand = brand_id.replace('"', '\\"')
        expression = f'brand_id == "{escaped_brand}"'
        if category:
            escaped_category = category.replace('"', '\\"')
            expression += f' and category in ["global", "{escaped_category}"]'
        query_vector = self.embedding_provider.embed([query])[0]
        requests = [
            AnnSearchRequest(
                data=[query_vector],
                anns_field="dense",
                param={"metric_type": "COSINE"},
                limit=max(limit * 2, 10),
                expr=expression,
            ),
            AnnSearchRequest(
                data=[query],
                anns_field="sparse",
                param={"metric_type": "BM25"},
                limit=max(limit * 2, 10),
                expr=expression,
            ),
        ]
        ranker = Function(
            name="rrf",
            input_field_names=[],
            function_type=FunctionType.RERANK,
            params={"reranker": "rrf", "k": 60},
        )
        response = self.client.hybrid_search(
            collection_name=self.settings.milvus_collection,
            reqs=requests,
            ranker=ranker,
            limit=limit,
            output_fields=["doc_id", "title", "content", "source"],
        )
        return [
            RetrievedContext(
                doc_id=hit["entity"]["doc_id"],
                title=hit["entity"]["title"],
                content=hit["entity"]["content"],
                source=hit["entity"]["source"],
                score=float(hit["distance"]),
            )
            for hit in response[0]
        ]


class BrandRepository:
    def __init__(self, retriever=None, data_dir: Path | None = None) -> None:
        self.retriever = retriever or InMemoryHybridRetriever()
        self.data_dir = data_dir or Path("data/brands")
        self._load_seed_documents()

    def _load_seed_documents(self) -> None:
        documents: list[KnowledgeDocument] = []
        for path in self.data_dir.glob("*.json"):
            payload = json.loads(path.read_text(encoding="utf-8"))
            documents.extend(KnowledgeDocument(**item) for item in payload["documents"])
        if documents:
            self.retriever.upsert(documents)

    def upsert(self, documents: list[KnowledgeDocument]) -> None:
        self.retriever.upsert(documents)

    def search(
        self, query: str, brand_id: str, category: str | None = None, limit: int = 4
    ) -> list[RetrievedContext]:
        return self.retriever.search(query, brand_id, category, limit)

    def retrieve(
        self, brand_id: str, category: str, query: str, limit: int = 4
    ) -> list[RetrievedContext]:
        return self.search(query, brand_id, category, limit)


@lru_cache
def get_brand_repository() -> BrandRepository:
    settings = get_settings()
    if settings.retrieval_mode == "milvus":
        embedder = SentenceTransformerEmbeddingProvider(settings.embedding_model)
        return BrandRepository(retriever=MilvusHybridRetriever(settings, embedder))
    return BrandRepository()
