"""Qdrant collection schema and server-side RBAC filter definitions."""

import os

from qdrant_client import QdrantClient, models

COLLECTION_NAME = os.getenv(
    "QDRANT_COLLECTION",
    "enterprise_documents",
)
VECTOR_SIZE = 384
VECTOR_DISTANCE = models.Distance.COSINE
QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333"))

PAYLOAD_SCHEMA = {
    "document_id": models.PayloadSchemaType.KEYWORD,
    "chunk_id": models.PayloadSchemaType.KEYWORD,
    "department_id": models.PayloadSchemaType.KEYWORD,
    "clearance_level": models.PayloadSchemaType.INTEGER,
    "content_type": models.PayloadSchemaType.KEYWORD,
    "title": models.PayloadSchemaType.KEYWORD,
    "content": models.PayloadSchemaType.TEXT,
    "page": models.PayloadSchemaType.INTEGER,
    "line_start": models.PayloadSchemaType.INTEGER,
    "line_end": models.PayloadSchemaType.INTEGER,
}


def access_filter(
    *, clearance_level: int, department_id: str, is_executive: bool = False
) -> models.Filter:
    """Return the payload filter that must run before vector search/ranking."""
    clearance_condition = models.FieldCondition(
        key="clearance_level",
        range=models.Range(lte=clearance_level),
    )
    if is_executive:
        return models.Filter(must=[clearance_condition])

    return models.Filter(
        must=[clearance_condition],
        should=[
            models.FieldCondition(
                key="department_id",
                match=models.MatchValue(value=department_id),
            ),
            models.FieldCondition(
                key="department_id",
                match=models.MatchValue(value="Global"),
            ),
        ],
    )


def create_client() -> QdrantClient:
    """Create a client using the configured local Qdrant endpoint."""
    return QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)


def ensure_collection(client: QdrantClient) -> None:
    """Create the collection and payload indexes when they do not exist."""
    collections = client.get_collections().collections
    if not any(collection.name == COLLECTION_NAME for collection in collections):
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=models.VectorParams(
                size=VECTOR_SIZE,
                distance=VECTOR_DISTANCE,
            ),
        )

    for field_name, field_schema in PAYLOAD_SCHEMA.items():
        client.create_payload_index(
            collection_name=COLLECTION_NAME,
            field_name=field_name,
            field_schema=field_schema,
        )
