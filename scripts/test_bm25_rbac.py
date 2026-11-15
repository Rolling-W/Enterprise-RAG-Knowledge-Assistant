from backend.ingestion.models import DocumentChunk
from backend.retrieval.bm25 import BM25Retriever


def make_chunk(
    content: str,
    department: str,
    min_clearance: int,
) -> DocumentChunk:
    return DocumentChunk(
        chunk_id=content,
        document_id="test-doc",
        title="",
        content=content,
        content_type="text",
        source_file="test.pdf",
        page_start=1,
        page_end=1,
        element_ids=[],
        department=department,
        min_clearance=min_clearance,
    )


def main():
    chunks = [
        make_chunk(
            "Company revenue forecast and financial budget",
            "Finance",
            1,
        ),
        make_chunk(
            "Confidential finance acquisition strategy",
            "Finance",
            3,
        ),
        make_chunk(
            "Legal contract review and compliance policy",
            "Legal",
            1,
        ),
        make_chunk(
            "Company-wide financial reporting guidelines",
            "Global",
            1,
        ),
    ]

    retriever = BM25Retriever(chunks)

    results = retriever.search(
        query="finance financial strategy",
        top_k=10,
        department="Finance",
        clearance_level=3,
    )

    for chunk, score in results:
        print(
            f"{chunk.department} | "
            f"Level {chunk.min_clearance} | "
            f"{score:.4f} | "
            f"{chunk.content}"
        )


if __name__ == "__main__":
    main()