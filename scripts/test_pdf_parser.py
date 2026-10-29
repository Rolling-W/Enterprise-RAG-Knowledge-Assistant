from backend.ingestion.chunker import DocumentChunker
from backend.ingestion.pdf_parser import UnstructuredPDFParser


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

    print(f"Total elements: {len(elements)}")
    print(f"Total chunks: {len(chunks)}")
    print()

    for chunk in chunks:
        print(
            f"Pages: {chunk.page_start}-{chunk.page_end} | "
            f"Words: {len(chunk.content.split())}"
        )
        print(chunk.content[:300])
        print("=" * 80)


if __name__ == "__main__":
    main()