from qdrant_client import models

from backend.ingestion.models import DocumentChunk


def chunk_to_point(
    chunk: DocumentChunk,
    vector: list[float],
) -> models.PointStruct:
    return models.PointStruct(
        id=chunk.chunk_id,
        vector=vector,
        payload={
            "chunk_id": chunk.chunk_id,
            "document_id": chunk.document_id,
            "title": chunk.title,
            "content": chunk.content,
            "content_type": chunk.content_type,
            "source_file": chunk.source_file,
            "page_start": chunk.page_start,
            "page_end": chunk.page_end,
            "element_ids": chunk.element_ids,
            "department": chunk.department,
            "min_clearance": chunk.min_clearance,
        },
    )


def payload_to_chunk(
    payload: dict,
) -> DocumentChunk:
    """Convert Qdrant payload into a DocumentChunk."""

    page = payload.get("page")

    return DocumentChunk(
        chunk_id=payload["chunk_id"],
        document_id=payload["document_id"],
        title=payload.get("title", ""),
        content=payload["content"],
        content_type=payload.get("content_type", "text"),
        source_file=payload.get(
            "source_file",
            payload.get("title", ""),
        ),
        page_start=payload.get(
            "page_start",
            page if page is not None else 1,
        ),
        page_end=payload.get(
            "page_end",
            page if page is not None else 1,
        ),
        element_ids=payload.get("element_ids", []),
        department=payload.get(
            "department",
            payload.get("department_id", "Global"),
        ),
        min_clearance=payload.get(
            "min_clearance",
            payload.get("clearance_level", 0),
        ),
        line_start=payload.get("line_start"),
        line_end=payload.get("line_end"),
    )
