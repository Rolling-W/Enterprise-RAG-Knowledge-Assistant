from qdrant_client import QdrantClient

from backend.ingestion.chunker import DocumentChunker
from backend.ingestion.pdf_parser import UnstructuredPDFParser
from backend.retrieval.bm25 import BM25Retriever
from backend.retrieval.embedder import DenseEmbedder
from backend.retrieval.hybrid import HybridRetriever


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

    bm25_retriever = BM25Retriever(chunks)

    qdrant_client = QdrantClient(
        host="localhost",
        port=6333,
    )

    embedder = DenseEmbedder()

    retriever = HybridRetriever(
        bm25_retriever=bm25_retriever,
        qdrant_client=qdrant_client,
        embedder=embedder,
    )

    query = (
        "How does the project implement "
        "hybrid retrieval with BM25 and Qdrant?"
    )

    results = retriever.search(
        query=query,
        department="Finance",
        clearance_level=1,
        top_k=5,
        candidate_k=10,
    )

    print(f"Query: {query}")
    print()

    for rank, (chunk, score) in enumerate(
        results,
        start=1,
    ):
        first_line = chunk.content.strip().splitlines()[0]

        print(
            f"{rank}. {first_line} "
            f"| RRF Score: {score:.6f} "
            f"| Pages: {chunk.page_start}-{chunk.page_end}"
        )


if __name__ == "__main__":
    main()