"""Document ingestion and Qdrant-backed retrieval services."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import PurePath
from uuid import NAMESPACE_URL, uuid5

from qdrant_client import QdrantClient, models

try:
    from .qdrant_schema import COLLECTION_NAME, VECTOR_SIZE, access_filter, ensure_collection
except ImportError:
    from qdrant_schema import COLLECTION_NAME, VECTOR_SIZE, access_filter, ensure_collection


@dataclass(frozen=True)
class IngestedChunk:
    chunk_id: str
    content: str
    page: int | None
    line_start: int | None
    line_end: int | None


def _vector(text: str) -> list[float]:
    """Create a stable local embedding without requiring a model download."""
    values = [0.0] * VECTOR_SIZE
    tokens = re.findall(r"\w+", text.lower())
    for token in tokens:
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        index = int.from_bytes(digest[:4], "big") % VECTOR_SIZE
        values[index] += 1.0
    magnitude = sum(value * value for value in values) ** 0.5
    return [value / magnitude for value in values] if magnitude else values


def _text_chunks(text: str, document_id: str, chunk_size: int = 1200) -> list[IngestedChunk]:
    lines = text.splitlines()
    chunks: list[IngestedChunk] = []
    current: list[str] = []
    start_line = 1
    for line_number, line in enumerate(lines, start=1):
        if current and len("\n".join(current)) + len(line) + 1 > chunk_size:
            content = "\n".join(current).strip()
            if content:
                chunks.append(
                    IngestedChunk(
                        chunk_id=f"{document_id}_chunk_{len(chunks) + 1:04d}",
                        content=content,
                        page=None,
                        line_start=start_line,
                        line_end=line_number - 1,
                    )
                )
            current = []
            start_line = line_number
        current.append(line)
    content = "\n".join(current).strip()
    if content:
        chunks.append(
            IngestedChunk(
                chunk_id=f"{document_id}_chunk_{len(chunks) + 1:04d}",
                content=content,
                page=None,
                line_start=start_line,
                line_end=len(lines),
            )
        )
    return chunks


def parse_document(filename: str, content_type: str, content: bytes) -> list[IngestedChunk]:
    if content_type == "application/pdf" or PurePath(filename).suffix.lower() == ".pdf":
        try:
            from pypdf import PdfReader
        except ImportError as exc:
            raise RuntimeError("PDF support is not installed") from exc
        import io

        chunks: list[IngestedChunk] = []
        reader = PdfReader(io.BytesIO(content))
        for page_number, page in enumerate(reader.pages, start=1):
            page_text = page.extract_text() or ""
            for chunk in _text_chunks(page_text, f"page_{page_number}"):
                chunks.append(
                    IngestedChunk(
                        chunk_id=f"chunk_{len(chunks) + 1:04d}",
                        content=chunk.content,
                        page=page_number,
                        line_start=chunk.line_start,
                        line_end=chunk.line_end,
                    )
                )
        return chunks
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("Document must be UTF-8 encoded text") from exc
    return _text_chunks(text, "document")


def ingest(
    client: QdrantClient,
    *,
    document_id: str,
    filename: str,
    content_type: str,
    content: bytes,
    department_id: str,
    clearance_level: int,
) -> int:
    ensure_collection(client)
    chunks = parse_document(filename, content_type, content)
    points = []
    for chunk in chunks:
        point_id = str(uuid5(NAMESPACE_URL, f"{document_id}:{chunk.chunk_id}"))
        payload = {
            "document_id": document_id,
            "chunk_id": chunk.chunk_id,
            "department_id": department_id,
            "clearance_level": clearance_level,
            "content_type": content_type,
            "title": filename,
            "content": chunk.content,
            "page": chunk.page,
            "line_start": chunk.line_start,
            "line_end": chunk.line_end,
        }
        points.append(models.PointStruct(id=point_id, vector=_vector(chunk.content), payload=payload))
    if points:
        client.upsert(collection_name=COLLECTION_NAME, points=points, wait=True)
    return len(points)


def search(
    client: QdrantClient,
    *,
    query: str,
    top_k: int,
    mode: str,
    clearance_level: int,
    department_id: str,
    is_executive: bool,
    department_filter: str | None = None,
) -> list[models.ScoredPoint]:
    ensure_collection(client)
    query_filter = access_filter(
        clearance_level=clearance_level,
        department_id=department_id,
        is_executive=is_executive,
    )
    if department_filter:
        query_filter.must.append(
            models.FieldCondition(
                key="department_id",
                match=models.MatchValue(value=department_filter),
            )
        )
    if mode == "keyword":
        return _keyword_search(client, query, top_k, query_filter)
    semantic_response = client.query_points(
        collection_name=COLLECTION_NAME,
        query=_vector(query),
        query_filter=query_filter,
        limit=top_k,
        with_payload=True,
    )
    semantic = semantic_response.points
    if mode == "semantic":
        return semantic
    keyword = _keyword_search(client, query, top_k, query_filter)
    by_id = {str(point.id): point for point in semantic}
    for point in keyword:
        existing = by_id.get(str(point.id))
        if existing is None:
            by_id[str(point.id)] = point
        else:
            existing.score = (existing.score + point.score) / 2
    return sorted(by_id.values(), key=lambda point: point.score, reverse=True)[:top_k]


def _keyword_search(
    client: QdrantClient, query: str, top_k: int, query_filter: models.Filter
) -> list[models.ScoredPoint]:
    query_tokens = set(re.findall(r"\w+", query.lower()))
    records, _ = client.scroll(
        collection_name=COLLECTION_NAME,
        scroll_filter=query_filter,
        limit=1000,
        with_payload=True,
        with_vectors=False,
    )
    scored: list[models.ScoredPoint] = []
    for record in records:
        content = str((record.payload or {}).get("content", ""))
        tokens = set(re.findall(r"\w+", content.lower()))
        score = len(query_tokens & tokens) / max(len(query_tokens), 1)
        if score > 0:
            scored.append(
                models.ScoredPoint(
                    id=record.id,
                    version=0,
                    score=score,
                    payload=record.payload,
                )
            )
    return sorted(scored, key=lambda record: record.score, reverse=True)[:top_k]
