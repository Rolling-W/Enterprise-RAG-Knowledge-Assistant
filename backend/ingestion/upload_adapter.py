
from pathlib import Path
from tempfile import TemporaryDirectory

from backend.ingestion.chunker import DocumentChunker
from backend.ingestion.markdown_parser import MarkdownParser
from backend.ingestion.models import DocumentChunk
from backend.ingestion.pdf_parser import UnstructuredPDFParser
from backend.ingestion.txt_parser import TXTParser


def parse_uploaded_document(
    *,
    filename: str,
    content: bytes,
    document_id: str,
    department: str,
    min_clearance: int,
) -> list[DocumentChunk]:
    """Convert uploaded document bytes into structured chunks."""

    suffix = Path(filename).suffix.lower()

    parsers = {
        ".pdf": UnstructuredPDFParser,
        ".md": MarkdownParser,
        ".markdown": MarkdownParser,
        ".txt": TXTParser,
    }

    if suffix not in parsers:
        raise ValueError(f"Unsupported document format: {suffix}")

    safe_filename = Path(filename.replace("\\", "/")).name

    with TemporaryDirectory() as temp_dir:
        file_path = Path(temp_dir) / safe_filename
        file_path.write_bytes(content)

        parser = parsers[suffix]()
        elements = parser.parse(str(file_path))

        chunker = DocumentChunker()

        chunks = chunker.chunk(
            elements=elements,
            document_id=document_id,
            department=department,
            min_clearance=min_clearance,
        )

    return chunks
