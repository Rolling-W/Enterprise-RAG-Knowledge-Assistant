"""Explicitly provision the Qdrant collection for local development."""

try:
    from .qdrant_schema import create_client, ensure_collection
except ImportError:
    from qdrant_schema import create_client, ensure_collection


if __name__ == "__main__":
    client = create_client()
    ensure_collection(client)
    print("Qdrant collection provisioned: enterprise_documents")
