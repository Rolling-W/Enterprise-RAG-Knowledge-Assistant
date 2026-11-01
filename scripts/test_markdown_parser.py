from backend.ingestion.chunker import DocumentChunker
from backend.ingestion.markdown_parser import MarkdownParser


def main():
    parser = MarkdownParser()
    chunker = DocumentChunker()

    elements = parser.parse(
        "sample_data/sample.md"
    )

    chunks = chunker.chunk(
        elements=elements,
        document_id="sample-markdown-001",
        department="Global",
        min_clearance=1,
        max_words=400,
    )

    print(f"Total elements: {len(elements)}")
    print(f"Total chunks: {len(chunks)}")
    print()

    for element in elements:
        print(
            f"{element.element_type} | "
            f"{element.text}"
        )

    print()
    print("===== CHUNKS =====")

    for chunk in chunks:
        print(
            f"Pages: {chunk.page_start}-{chunk.page_end} | "
            f"Words: {len(chunk.content.split())}"
        )
        print(chunk.content)
        print("=" * 80)


if __name__ == "__main__":
    main()