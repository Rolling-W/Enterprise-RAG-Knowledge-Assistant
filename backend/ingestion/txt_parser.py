
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from backend.ingestion.models import DocumentElement


class TXTParser:
    def parse(self, file_path: str) -> list[DocumentElement]:
        path = Path(file_path)
        text = path.read_text(encoding="utf-8-sig")

        elements: list[DocumentElement] = []

        for line_number, line in enumerate(text.splitlines(), start=1):
            content = line.strip()

            if not content:
                continue

            element_id = str(
                uuid5(
                    NAMESPACE_URL,
                    f"{path.name}:{line_number}:{content}",
                )
            )

            elements.append(
                DocumentElement(
                    element_id=element_id,
                    text=content,
                    element_type="Text",
                    source_file=path.name,
                    page_number=1,
                    sequence=len(elements),
                    bbox=None,
                    line_start=line_number,
                    line_end=line_number,
                )
            )

        return elements
