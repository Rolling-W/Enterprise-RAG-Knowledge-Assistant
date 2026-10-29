from backend.ingestion.chunker import DocumentChunker
from backend.ingestion.pdf_parser import UnstructuredPDFParser
from backend.retrieval.bm25 import BM25Retriever


def main():
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

    retriever = BM25Retriever(chunks)

    query = "hybrid retrieval BM25 Qdrant"

    results = retriever.search(
        query=query,
        top_k=5,
    )

    print(f"Query: {query}")
    print()

    for rank, (chunk, score) in enumerate(
        results,
        start=1,
    ):
        print(
            f"Rank {rank} | "
            f"Score: {score:.4f} | "
            f"Pages: {chunk.page_start}-{chunk.page_end}"
        )

        print(chunk.content[:500])
        print("=" * 80)


if __name__ == "__main__":
    main()