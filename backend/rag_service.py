"""Document ingestion and Qdrant-backed retrieval services."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import PurePath
from uuid import NAMESPACE_URL, uuid5

from qdrant_client import QdrantClient, models
from functools import lru_cache
from sentence_transformers import SentenceTransformer, CrossEncoder

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


@lru_cache(maxsize=1)
def _reranker_model() -> CrossEncoder:
    """Load the Cross-Encoder reranker once per Python process."""
    return CrossEncoder(
        "cross-encoder/ms-marco-MiniLM-L-6-v2"
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
    permission_level: int,
) -> int:
    ensure_collection(client)

    chunks = parse_uploaded_document(
        filename=filename,
        content=content,
        document_id=document_id,
        department=department_id,
        permission_level=permission_level,
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
            "permission_level": chunk.permission_level,
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


def delete_document_points(
    client: QdrantClient,
    *,
    document_id: str,
) -> None:
    """Delete all Qdrant points belonging to one document."""

    if not document_id:
        raise ValueError("document_id cannot be empty")

    client.delete(
        collection_name=COLLECTION_NAME,
        points_selector=models.FilterSelector(
            filter=models.Filter(
                must=[
                    models.FieldCondition(
                        key="document_id",
                        match=models.MatchValue(value=document_id),
                    )
                ]
            )
        ),
        wait=True,
    )


def update_document_permission(
    client: QdrantClient,
    *,
    document_id: str,
    permission_level: int,
) -> None:
    """Update the permission level of all Qdrant chunks for a document."""

    if not document_id:
        raise ValueError("document_id cannot be empty")

    if permission_level not in (1, 2, 3):
        raise ValueError("permission_level must be between 1 and 3")

    client.set_payload(
        collection_name=COLLECTION_NAME,
        payload={"permission_level": permission_level},
        points=models.FilterSelector(
            filter=models.Filter(
                must=[
                    models.FieldCondition(
                        key="document_id",
                        match=models.MatchValue(value=document_id),
                    )
                ]
            )
        ),
        wait=True,
    )


def verify_document_permission(
    client: QdrantClient,
    *,
    document_id: str,
    permission_level: int,
) -> int:
    """Verify all indexed chunks have the expected permission level."""

    if not document_id:
        raise ValueError("document_id cannot be empty")

    if permission_level not in (1, 2, 3):
        raise ValueError("permission_level must be between 1 and 3")

    document_filter = models.Filter(
        must=[
            models.FieldCondition(
                key="document_id",
                match=models.MatchValue(value=document_id),
            )
        ]
    )

    verified_count = 0
    offset = None

    while True:
        points, next_offset = client.scroll(
            collection_name=COLLECTION_NAME,
            scroll_filter=document_filter,
            limit=100,
            offset=offset,
            with_payload=True,
            with_vectors=False,
        )

        for point in points:
            payload = point.payload or {}

            if payload.get("permission_level") != permission_level:
                raise RuntimeError(
                    f"Permission mismatch for document {document_id}"
                )

            verified_count += 1

        if next_offset is None:
            break

        offset = next_offset

    if verified_count == 0:
        raise RuntimeError(
            f"No indexed chunks found for document {document_id}"
        )

    return verified_count


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
    allowed_document_ids: list[str] | None = None,
) -> list[models.ScoredPoint]:

    # PostgreSQL authorization is mandatory.
    if allowed_document_ids is None:
        raise ValueError(
            "PostgreSQL document authorization is required"
        )

    if not allowed_document_ids:
        return []

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

    query_filter.must.append(
        models.FieldCondition(
            key="document_id",
            match=models.MatchAny(any=allowed_document_ids),
        )
    )

    if mode == "keyword":
        return _keyword_search(client, query, top_k, query_filter)

    # Retrieve a larger candidate pool for hybrid reranking.
    candidate_limit = max(20, top_k)

    semantic_response = client.query_points(
        collection_name=COLLECTION_NAME,
        query=_vector(query),
        query_filter=query_filter,
        limit=candidate_limit if mode == "hybrid" else top_k,
        with_payload=True,
    )
    semantic = semantic_response.points
    if mode == "semantic":
        return semantic

    # Hybrid Search: Reciprocal Rank Fusion (RRF)
    keyword = _keyword_search(
        client, query, candidate_limit, query_filter
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


    # Select candidates using the existing RRF ranking.
    results = []

    for point_id in ranked_ids[:candidate_limit]:
        point = points_by_id[point_id]
        point.score = fused_scores[point_id]
        results.append(point)

    if not results:
        return []

    # Prepare query-document pairs for Cross-Encoder.
    pairs = []

    for point in results:
        payload = point.payload or {}
        content = payload.get("content")

        if not isinstance(content, str) or not content.strip():
            raise ValueError(
                "Retrieved chunk is missing text content"
            )

        pairs.append((query, content))

    # Compute Cross-Encoder relevance scores.
    rerank_scores = _reranker_model().predict(
        pairs,
        show_progress_bar=False,
    )

    # Replace the RRF score with the final reranking score.
    for point, score in zip(results, rerank_scores):
        point.score = float(score)

    # Return the most relevant chunks after reranking.
    results.sort(
        key=lambda point: point.score,
        reverse=True,
    )

    return results[:top_k]



def search_debug(
    client: QdrantClient,
    *,
    query: str,
    top_k: int,
    candidate_limit: int,
    mode: str,
    clearance_level: int,
    department_id: str,
    is_executive: bool,
    department_filter: str | None = None,
    allowed_document_ids: list[str] | None = None,
) -> tuple[list[dict], list[str], dict[str, float]]:
    """Return authorized search candidates with stage scores and timings."""
    from time import perf_counter

    if allowed_document_ids is None:
        raise ValueError("PostgreSQL document authorization is required")

    if not allowed_document_ids:
        return [], [], {
            "authorization_filter": 0.0,
            "bm25": 0.0,
            "dense": 0.0,
            "fusion": 0.0,
            "rerank": 0.0,
        }

    started = perf_counter()

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

    query_filter.must.append(
        models.FieldCondition(
            key="document_id",
            match=models.MatchAny(any=allowed_document_ids),
        )
    )

    timings = {
        "authorization_filter": (perf_counter() - started) * 1000,
        "bm25": 0.0,
        "dense": 0.0,
        "fusion": 0.0,
        "rerank": 0.0,
    }

    keyword = []
    semantic = []
    stages = []

    if mode in ("keyword", "hybrid"):
        started = perf_counter()

        keyword = _keyword_search(
            client,
            query,
            candidate_limit,
            query_filter,
            return_raw_scores=True,
        )

        timings["bm25"] = (perf_counter() - started) * 1000
        stages.append("bm25")

    if mode in ("semantic", "hybrid"):
        started = perf_counter()

        semantic = client.query_points(
            collection_name=COLLECTION_NAME,
            query=_vector(query),
            query_filter=query_filter,
            limit=candidate_limit,
            with_payload=True,
        ).points

        timings["dense"] = (perf_counter() - started) * 1000
        stages.append("dense")


    candidates = {}
    candidate_text_by_key = {}


    def add_results(points, stage):
        for rank, point in enumerate(points, start=1):
            point_id = str(point.id)
            payload = point.payload or {}

            if point_id not in candidates:
                candidate_text_by_key[
                    (str(payload["document_id"]), str(payload["chunk_id"]))
                ] = payload.get("content", "")

                candidates[point_id] = {
                    "document_id": str(payload["document_id"]),
                    "chunk_id": str(payload["chunk_id"]),
                    "permission_level": int(payload["permission_level"]),
                    "scores": {
                        "bm25_raw": None,
                        "bm25_rank": None,
                        "dense_raw": None,
                        "dense_rank": None,
                        "fusion": None,
                        "rerank": None,
                        "final": None,
                    },
                }

            scores = candidates[point_id]["scores"]
            scores[f"{stage}_raw"] = float(point.score)
            scores[f"{stage}_rank"] = rank

    add_results(keyword, "bm25")
    add_results(semantic, "dense")

    started = perf_counter()

    for candidate in candidates.values():
        scores = candidate["scores"]

        if mode == "hybrid":
            fusion = 0.0

            if scores["bm25_rank"] is not None:
                fusion += 1.0 / (60 + scores["bm25_rank"])

            if scores["dense_rank"] is not None:
                fusion += 1.0 / (60 + scores["dense_rank"])

            scores["fusion"] = fusion
            scores["final"] = fusion

        elif mode == "keyword":
            scores["final"] = 1.0 / scores["bm25_rank"]

        else:
            scores["final"] = scores["dense_raw"]

    ranked = sorted(
        candidates.values(),
        key=lambda candidate: (
            -candidate["scores"]["final"],
            candidate["chunk_id"],
        ),
    )

    ranked = ranked[:candidate_limit]

    # Record RRF fusion time before reranking.
    timings["fusion"] = (perf_counter() - started) * 1000

    if mode == "hybrid":
        stages.append("rrf")

        if ranked:
            started = perf_counter()

            # Prepare query-chunk pairs.
            pairs = []

            for candidate in ranked:
                key = (
                    candidate["document_id"],
                    candidate["chunk_id"],
                )

                content = candidate_text_by_key[key]

                if not isinstance(content, str) or not content.strip():
                    raise ValueError(
                        "Retrieved chunk is missing text content"
                    )

                pairs.append((query, content))

            # Compute Cross-Encoder scores.
            rerank_scores = _reranker_model().predict(
                pairs,
                show_progress_bar=False,
            )

            # Preserve RRF scores while updating final scores.
            for candidate, score in zip(ranked, rerank_scores):
                candidate["scores"]["rerank"] = float(score)
                candidate["scores"]["final"] = float(score)

            # Sort by Cross-Encoder relevance.
            ranked.sort(
                key=lambda candidate: (
                    -candidate["scores"]["final"],
                    candidate["chunk_id"],
                ),
            )

            timings["rerank"] = (
                perf_counter() - started
            ) * 1000

            stages.append("rerank")

    # Assign final ranks after reranking.
    for rank, candidate in enumerate(ranked, start=1):
        candidate["final_rank"] = rank

    return ranked, stages, timings


def get_chunk_content(
    client: QdrantClient,
    *,
    document_id: str,
    chunk_id: str,
) -> str | None:
    """Retrieve the content of one specific document chunk."""

    if not document_id or not chunk_id:
        raise ValueError("Document ID and Chunk ID are required")

    chunk_filter = models.Filter(
        must=[
            models.FieldCondition(
                key="document_id",
                match=models.MatchValue(value=document_id),
            ),
            models.FieldCondition(
                key="chunk_id",
                match=models.MatchValue(value=chunk_id),
            ),
        ]
    )

    points, _ = client.scroll(
        collection_name=COLLECTION_NAME,
        scroll_filter=chunk_filter,
        limit=2,
        with_payload=True,
        with_vectors=False,
    )

    if not points:
        return None

    if len(points) > 1:
        raise RuntimeError("Duplicate document chunk found")

    content = (points[0].payload or {}).get("content")

    if not isinstance(content, str) or not content.strip():
        return None

    return content


def _keyword_search(
    client: QdrantClient,
    query: str,
    top_k: int,
    query_filter: models.Filter,
    *,
    return_raw_scores: bool = False,
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
                score=(
                    float(raw_score)
                    if return_raw_scores
                    else 1.0 / (len(results) + 1)
                ),
                payload=record.payload,
            )
        )

    return results
