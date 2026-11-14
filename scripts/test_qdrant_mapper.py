from backend.ingestion.models import DocumentChunk
from backend.retrieval.qdrant_mapper import chunk_to_point


def main():
    chunk = DocumentChunk(
        chunk_id="test-chunk-001",
        document_id="test-doc-001",
        title="Test Section",
        content="This is a test chunk for Qdrant mapping.",
        content_type="text",
        source_file="test.pdf",
        page_start=1,
        page_end=2,
        element_ids=["el-1", "el-2"],
        department="Finance",
        min_clearance=2,
    )

    vector = [0.0] * 384

    point = chunk_to_point(
        chunk=chunk,
        vector=vector,
    )

    print(f"Point ID: {point.id}")
    print(f"Vector length: {len(point.vector)}")
    print("Payload:")

    for key, value in point.payload.items():
        print(f"  {key}: {value}")


if __name__ == "__main__":
    main()