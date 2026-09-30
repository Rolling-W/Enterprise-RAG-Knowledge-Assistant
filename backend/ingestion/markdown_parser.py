from pathlib import Path
from uuid import uuid4

from unstructured.partition.md import partition_md

from backend.ingestion.models import DocumentElement


class MarkdownParser:
    def parse(
        self,
        file_path: str,
    ) -> list[DocumentElement]:
        raw_elements = partition_md(
            filename=file_path,
        )

        source_file = Path(file_path).name
        elements: list[DocumentElement] = []

        for sequence, element in enumerate(raw_elements):
            text = getattr(element, "text", None)

            if not text or not text.strip():
                continue

            document_element = DocumentElement(
                element_id=str(uuid4()),
                text=text.strip(),
                element_type=type(element).__name__,
                source_file=source_file,
                page_number=1,
                sequence=sequence,
                bbox=None,
            )

            elements.append(document_element)

        return elements