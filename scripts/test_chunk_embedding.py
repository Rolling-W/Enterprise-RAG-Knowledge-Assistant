from backend.ingestion.models import DocumentChunk
from backend.retrieval.embedder import DenseEmbedder
from backend.retrieval.qdrant_mapper import chunk_to_point


def main():
    chunk = DocumentChunk(
        chunk_id="test-chunk-001",
        document_id="test-doc-001",
        title="Hybrid Retrieval",
        content=(
            "Hybrid retrieval combines BM25 sparse search "
            "with dense vector search in Qdrant."
        ),
        content_type="text",
        source_file="test.pdf",
        page_start=1,
        page_end=1,
        element_ids=["el-1"],
        department="Global",
        min_clearance=1,
    )

    embedder = DenseEmbedder()

    vector = embedder.embed_text(
        chunk.content
    )

    point = chunk_to_point(
        chunk=chunk,
        vector=vector,
    )

    print(f"Point ID: {point.id}")
    print(f"Vector length: {len(point.vector)}")
    print(f"Title: {point.payload['title']}")
    print(f"Department: {point.payload['department']}")
    print(f"Content: {point.payload['content']}")


if __name__ == "__main__":
    main()