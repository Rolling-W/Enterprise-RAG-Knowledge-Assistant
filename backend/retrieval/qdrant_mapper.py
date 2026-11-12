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
            "department_id": chunk.department,
            "permission_level": chunk.permission_level,
        },
    )


def payload_to_chunk(
    payload: dict,
) -> DocumentChunk:
    """Convert Qdrant payload into a DocumentChunk."""

    permission_level = payload.get("permission_level")
    department_id = payload.get("department_id")

    if (
        type(permission_level) is not int
        or permission_level not in (1, 2, 3)
        or not isinstance(department_id, str)
        or not department_id.strip()
    ):
        raise ValueError("Invalid or missing document access metadata")

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
        department=department_id,
        permission_level=permission_level,
        line_start=payload.get("line_start"),
        line_end=payload.get("line_end"),
    )
