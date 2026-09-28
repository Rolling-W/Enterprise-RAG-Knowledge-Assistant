"""Qdrant collection and server-side RBAC filter definitions."""

from qdrant_client import QdrantClient, models

COLLECTION_NAME = "enterprise_documents"
VECTOR_SIZE = 384
VECTOR_DISTANCE = models.Distance.COSINE


def access_filter(*, clearance: int, department: str, is_executive: bool = False) -> models.Filter:
    """Return the payload filter that must run before vector search/ranking."""
    clearance_condition = models.FieldCondition(
        key="min_clearance",
        range=models.Range(lte=clearance),
    )
    if is_executive:
        return models.Filter(must=[clearance_condition])

    return models.Filter(
        must=[clearance_condition],
        should=[
            models.FieldCondition(
                key="department",
                match=models.MatchValue(value=department),
            ),
            models.FieldCondition(
                key="department",
                match=models.MatchValue(value="Global"),
            ),
        ],
    )


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

    for field_name, field_schema in (
        ("document_id", models.PayloadSchemaType.KEYWORD),
        ("department", models.PayloadSchemaType.KEYWORD),
        ("min_clearance", models.PayloadSchemaType.INTEGER),
        ("content_type", models.PayloadSchemaType.KEYWORD),
    ):
        client.create_payload_index(
            collection_name=COLLECTION_NAME,
            field_name=field_name,
            field_schema=field_schema,
        )
