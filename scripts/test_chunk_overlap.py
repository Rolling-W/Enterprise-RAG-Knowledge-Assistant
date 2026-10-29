from backend.ingestion.chunker import DocumentChunker
from backend.ingestion.models import DocumentElement


def make_element(
    element_id: str,
    text: str,
    sequence: int,
) -> DocumentElement:
    return DocumentElement(
        element_id=element_id,
        text=text,
        element_type="NarrativeText",
        source_file="synthetic_test.txt",
        page_number=1,
        sequence=sequence,
    )


elements = [
    DocumentElement(
        element_id="heading-1",
        text="1 Long Section",
        element_type="Title",
        source_file="synthetic_test.txt",
        page_number=1,
        sequence=0,
    ),
    make_element(
        "p1",
        " ".join(["alpha"] * 90),
        1,
    ),
    make_element(
        "p2",
        " ".join(["beta"] * 110),
        2,
    ),
    make_element(
        "p3",
        " ".join(["gamma"] * 40),
        3,
    ),
    make_element(
        "p4",
        " ".join(["delta"] * 100),
        4,
    ),
    make_element(
        "p5",
        " ".join(["epsilon"] * 80),
        5,
    ),
]

chunker = DocumentChunker()

chunks = chunker.chunk(
    elements=elements,
    document_id="overlap-test",
    department="Engineering",
    min_clearance=1,
    max_words=300,
    overlap_words=50,
)

print(f"Total chunks: {len(chunks)}")
print()

for i, chunk in enumerate(chunks, start=1):
    print(f"Chunk {i}")
    print(f"Words: {len(chunk.content.split())}")
    print(f"Element IDs: {chunk.element_ids}")
    print("-" * 60)

if len(chunks) >= 2:
    overlap = set(chunks[0].element_ids) & set(
        chunks[1].element_ids
    )

    print()
    print(
        "Overlap between chunk 1 and chunk 2:",
        sorted(overlap),
    )
