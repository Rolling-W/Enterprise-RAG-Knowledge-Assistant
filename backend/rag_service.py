"""Document ingestion and Qdrant-backed retrieval services."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import PurePath
from uuid import NAMESPACE_URL, uuid5

from qdrant_client import QdrantClient, models
from functools import lru_cache
from sentence_transformers import SentenceTransformer

from backend.ingestion.upload_adapter import parse_uploaded_document
from backend.retrieval.bm25 import BM25Retriever
from backend.retrieval.qdrant_mapper import payload_to_chunk

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



@lru_cache(maxsize=1)
def _embedding_model() -> SentenceTransformer:
    """Load the embedding model once per Python process."""
    return SentenceTransformer(
        "sentence-transformers/all-MiniLM-L6-v2"
    )


def _vector(text: str) -> list[float]:
    """Generate a 384-dimensional semantic embedding."""
    embedding = _embedding_model().encode(
        text,
        normalize_embeddings=True,
    )

    return embedding.tolist()



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

    chunks = parse_uploaded_document(
        filename=filename,
        content=content,
        document_id=document_id,
        department=department_id,
        min_clearance=clearance_level,
    )

    is_pdf = PurePath(filename).suffix.lower() == ".pdf"

    points = []

    for chunk in chunks:
        point_id = str(
            uuid5(
                NAMESPACE_URL,
                f"{document_id}:{chunk.chunk_id}",
            )
        )

        payload = {
            "document_id": document_id,
            "chunk_id": chunk.chunk_id,
            "department_id": chunk.department,
            "clearance_level": chunk.min_clearance,
            "content_type": content_type,
            "title": filename,
            "content": chunk.content,
            "page": chunk.page_start if is_pdf else None,
            "line_start": chunk.line_start,
            "line_end": chunk.line_end,
        }

        points.append(
            models.PointStruct(
                id=point_id,
                vector=_vector(chunk.content),
                payload=payload,
            )
        )

    if points:
        client.upsert(
            collection_name=COLLECTION_NAME,
            points=points,
            wait=True,
        )

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

    # Hybrid Search: Reciprocal Rank Fusion (RRF)
    keyword = _keyword_search(
        client, query, top_k, query_filter
    )

    rrf_k = 60
    fused_scores = {}
    points_by_id = {}

    for ranked_results in (semantic, keyword):
        for rank, point in enumerate(ranked_results, start=1):
            point_id = str(point.id)

            points_by_id[point_id] = point

            fused_scores[point_id] = (
                fused_scores.get(point_id, 0.0)
                + 1.0 / (rrf_k + rank)
            )

    ranked_ids = sorted(
        fused_scores,
        key=lambda point_id: fused_scores[point_id],
        reverse=True,
    )

    results = []

    for point_id in ranked_ids[:top_k]:
        point = points_by_id[point_id]
        point.score = fused_scores[point_id]
        results.append(point)

    return results




def _keyword_search(
    client: QdrantClient,
    query: str,
    top_k: int,
    query_filter: models.Filter,
) -> list[models.ScoredPoint]:
    """Run BM25 on documents authorized by Qdrant RBAC."""

    records = []
    offset = None

    # Retrieve all authorized chunks using Qdrant pagination.
    while True:
        batch, offset = client.scroll(
            collection_name=COLLECTION_NAME,
            scroll_filter=query_filter,
            limit=256,
            offset=offset,
            with_payload=True,
            with_vectors=False,
        )

        records.extend(batch)

        if offset is None:
            break

    if not records:
        return []

    # Convert Qdrant payloads into DocumentChunk objects.
    chunks = [
        payload_to_chunk(record.payload)
        for record in records
    ]

    retriever = BM25Retriever(chunks)

    # Authorization has already been enforced by Qdrant.
    ranked = retriever.search(
        query=query,
        top_k=len(chunks),
    )

    query_tokens = set(retriever._tokenize(query))

    # Preserve original Qdrant records and payloads.
    records_by_chunk_id = {
        record.payload["chunk_id"]: record
        for record in records
    }

    results = []

    for chunk, raw_score in ranked:
        chunk_tokens = set(retriever._tokenize(chunk.content))

        if not query_tokens.intersection(chunk_tokens):
            continue

        if len(results) >= top_k:
            break

        record = records_by_chunk_id[chunk.chunk_id]

        results.append(
            models.ScoredPoint(
                id=record.id,
                version=0,
                score=1.0 / (len(results) + 1),
                payload=record.payload,
            )
        )

    return results
