from collections import defaultdict

from backend.ingestion.models import DocumentChunk

from qdrant_client import QdrantClient

from backend.qdrant_schema import (
    COLLECTION_NAME,
    access_filter,
)
from backend.retrieval.bm25 import BM25Retriever
from backend.retrieval.embedder import DenseEmbedder
from backend.retrieval.qdrant_mapper import payload_to_chunk


def reciprocal_rank_fusion(
    bm25_results: list[tuple[DocumentChunk, float]],
    dense_results: list[tuple[DocumentChunk, float]],
    k: int = 60,
) -> list[tuple[DocumentChunk, float]]:
    scores: dict[str, float] = defaultdict(float)
    chunks: dict[str, DocumentChunk] = {}

    for rank, (chunk, _) in enumerate(
        bm25_results,
        start=1,
    ):
        scores[chunk.chunk_id] += 1 / (k + rank)
        chunks[chunk.chunk_id] = chunk

    for rank, (chunk, _) in enumerate(
        dense_results,
        start=1,
    ):
        scores[chunk.chunk_id] += 1 / (k + rank)
        chunks[chunk.chunk_id] = chunk

    ranked = sorted(
        scores.items(),
        key=lambda item: item[1],
        reverse=True,
    )

    return [
        (chunks[chunk_id], score)
        for chunk_id, score in ranked
    ]

class HybridRetriever:
    def __init__(
        self,
        bm25_retriever: BM25Retriever,
        qdrant_client: QdrantClient,
        embedder: DenseEmbedder,
        collection_name: str = COLLECTION_NAME,
    ):
        self.bm25_retriever = bm25_retriever
        self.qdrant_client = qdrant_client
        self.embedder = embedder
        self.collection_name = collection_name

    def search(
        self,
        query: str,
        department: str,
        clearance_level: int,
        top_k: int = 5,
        candidate_k: int = 10,
    ) -> list[tuple[DocumentChunk, float]]:
        bm25_results = self.bm25_retriever.search(
            query=query,
            top_k=candidate_k,
            department=department,
            clearance_level=clearance_level,
        )

        query_vector = self.embedder.embed_text(query)

        dense_response = self.qdrant_client.query_points(
            collection_name=self.collection_name,
            query=query_vector,
            query_filter=access_filter(
                clearance=clearance_level,
                department=department,
            ),
            limit=candidate_k,
            with_payload=True,
        )

        dense_results = [
            (
                payload_to_chunk(point.payload),
                float(point.score),
            )
            for point in dense_response.points
        ]

        fused_results = reciprocal_rank_fusion(
            bm25_results=bm25_results,
            dense_results=dense_results,
        )

        return fused_results[:top_k]