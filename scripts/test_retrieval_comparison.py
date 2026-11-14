from qdrant_client import QdrantClient

from backend.ingestion.chunker import DocumentChunker
from backend.ingestion.pdf_parser import UnstructuredPDFParser
from backend.qdrant_schema import (
    COLLECTION_NAME,
    access_filter,
)
from backend.retrieval.bm25 import BM25Retriever
from backend.retrieval.embedder import DenseEmbedder
from backend.retrieval.hybrid import reciprocal_rank_fusion
from backend.retrieval.qdrant_mapper import payload_to_chunk


def first_line(text: str) -> str:
    return text.strip().splitlines()[0]


def main():
    query = (
        "How does the project implement "
        "hybrid retrieval with BM25 and Qdrant?"
    )

    # --------------------------------------------------
    # Build BM25 corpus
    # --------------------------------------------------

    parser = UnstructuredPDFParser()
    chunker = DocumentChunker()

    elements = parser.parse(
        "sample_data/project_charter.pdf"
    )

    chunks = chunker.chunk(
        elements=elements,
        document_id="project-charter-001",
        department="Global",
        min_clearance=1,
        max_words=400,
    )

    bm25 = BM25Retriever(chunks)

    bm25_results = bm25.search(
        query=query,
        top_k=5,
        department="Finance",
        clearance_level=1,
    )

    # --------------------------------------------------
    # Dense retrieval from Qdrant
    # --------------------------------------------------

    client = QdrantClient(
        host="localhost",
        port=6333,
    )

    embedder = DenseEmbedder()

    query_vector = embedder.embed_text(query)

    dense_response = client.query_points(
        collection_name=COLLECTION_NAME,
        query=query_vector,
        query_filter=access_filter(
            clearance=1,
            department="Finance",
        ),
        limit=5,
        with_payload=True,
    )

    dense_results = [
        (
            payload_to_chunk(point.payload),
            float(point.score),
        )
        for point in dense_response.points
    ]

    # --------------------------------------------------
    # Print comparison
    # --------------------------------------------------

    print(f"Query: {query}")
    print()

    print("===== BM25 =====")

    for rank, (chunk, score) in enumerate(
        bm25_results,
        start=1,
    ):
        print(
            f"{rank}. {first_line(chunk.content)} "
            f"| Score: {score:.4f}"
        )

    print()
    print("===== DENSE =====")

    for rank, point in enumerate(
        dense_response.points,
        start=1,
    ):
        print(
            f"{rank}. "
            f"{first_line(point.payload['content'])} "
            f"| Score: {point.score:.4f}"
        )

    print()
    print("===== HYBRID RRF =====")

    hybrid_results = reciprocal_rank_fusion(
        bm25_results=bm25_results,
        dense_results=dense_results,
    )

    for rank, (chunk, score) in enumerate(
        hybrid_results[:5],
        start=1,
    ):
        print(
            f"{rank}. {first_line(chunk.content)} "
            f"| RRF Score: {score:.6f}"
        )


if __name__ == "__main__":
    main()