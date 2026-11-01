from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from unstructured.partition.md import partition_md

from backend.ingestion.models import DocumentElement

from backend.ingestion.markdown_line_mapper import map_markdown_lines


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
                element_id=str(
                    uuid5(
                        NAMESPACE_URL,
                        f"{source_file}:{sequence}:{text.strip()}",
                    )
                ),
                text=text.strip(),
                element_type=type(element).__name__,
                source_file=source_file,
                page_number=1,
                sequence=sequence,
                bbox=None,
            )

            elements.append(document_element)

        source_text = Path(file_path).read_text(encoding="utf-8-sig")
        map_markdown_lines(elements, source_text)

        return elements
