from dataclasses import dataclass
from typing import Optional


@dataclass
class DocumentElement:
    element_id: str
    text: str
    element_type: str
    source_file: str
    page_number: int
    sequence: int
    bbox: Optional[tuple[float, float, float, float]] = None
    line_start: Optional[int] = None
    line_end: Optional[int] = None


@dataclass
class DocumentChunk:
    chunk_id: str
    document_id: str
    title: str
    content: str
    content_type: str
    source_file: str
    page_start: int
    page_end: int
    element_ids: list[str]
    department: str
    min_clearance: int
    line_start: Optional[int] = None
    line_end: Optional[int] = None