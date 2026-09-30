from backend.ingestion.chunker import DocumentChunker
from backend.ingestion.pdf_parser import UnstructuredPDFParser


def build_chunks():
    parser = UnstructuredPDFParser()
    chunker = DocumentChunker()

    elements = parser.parse(
        "sample_data/project_charter.pdf"
    )

    return chunker.chunk(
        elements=elements,
        document_id="project-charter-001",
        department="Global",
        min_clearance=1,
        max_words=400,
    )


def main():
    first_run = build_chunks()
    second_run = build_chunks()

    first_ids = [
        chunk.chunk_id
        for chunk in first_run
    ]

    second_ids = [
        chunk.chunk_id
        for chunk in second_run
    ]

    print(f"First run chunks: {len(first_ids)}")
    print(f"Second run chunks: {len(second_ids)}")
    print(f"IDs identical: {first_ids == second_ids}")
    print()

    for index, (first_id, second_id) in enumerate(
        zip(first_ids, second_ids),
        start=1,
    ):
        print(
            f"Chunk {index}: "
            f"{first_id} == {second_id} "
            f"-> {first_id == second_id}"
        )


if __name__ == "__main__":
    main()