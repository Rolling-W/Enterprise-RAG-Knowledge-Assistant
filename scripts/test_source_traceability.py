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

    element_map = {
        element.element_id: element
        for element in elements
    }

    target_chunk = chunks[1]

    print(
        f"Chunk ID: {target_chunk.chunk_id}"
    )
    print(
        f"Chunk pages: "
        f"{target_chunk.page_start}-"
        f"{target_chunk.page_end}"
    )
    print(
        f"Element count: "
        f"{len(target_chunk.element_ids)}"
    )
    print()

    for element_id in target_chunk.element_ids:
        element = element_map[element_id]

        print(
            f"Element: {element.element_type}"
        )
        print(
            f"Page: {element.page_number}"
        )
        print(
            f"BBox: {element.bbox}"
        )
        print(
            f"Text: {element.text[:100]}"
        )
        print("-" * 60)


if __name__ == "__main__":
    main()