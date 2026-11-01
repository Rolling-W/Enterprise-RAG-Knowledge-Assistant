from abc import ABC, abstractmethod
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from unstructured.partition.pdf import partition_pdf

from backend.ingestion.models import DocumentElement


class PDFParser(ABC):
    @abstractmethod
    def parse(self, file_path: str) -> list[DocumentElement]:
        """Parse a PDF file into normalized document elements."""
        raise NotImplementedError


class UnstructuredPDFParser(PDFParser):
    def __init__(
        self,
        strategy: str = "fast",
    ):
        self.strategy = strategy

    def parse(
        self,
        file_path: str,
    ) -> list[DocumentElement]:
        raw_elements = partition_pdf(
            filename=file_path,
            strategy=self.strategy,
        )

        source_file = Path(file_path).name
        elements: list[DocumentElement] = []

        for sequence, element in enumerate(raw_elements):
            text = getattr(element, "text", None)

            if not text or not text.strip():
                continue

            page_number = getattr(
                element.metadata,
                "page_number",
                None,
            )

            if page_number is None:
                continue

            bbox = None

            coordinates = getattr(
                element.metadata,
                "coordinates",
                None,
            )

            if coordinates is not None and coordinates.points:
                xs = [point[0] for point in coordinates.points]
                ys = [point[1] for point in coordinates.points]

                bbox = (
                    min(xs),
                    min(ys),
                    max(xs),
                    max(ys),
                )

            document_element = DocumentElement(
                element_id=str(
                    uuid5(
                        NAMESPACE_URL,
                        f"{source_file}:{page_number}:{sequence}:{text.strip()}",
                    )
                ),
                text=text.strip(),
                element_type=type(element).__name__,
                source_file=source_file,
                page_number=page_number,
                sequence=sequence,
                bbox=bbox,
            )

            elements.append(document_element)

        return elements