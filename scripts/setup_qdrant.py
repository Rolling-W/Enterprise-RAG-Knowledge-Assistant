from qdrant_client import QdrantClient

from backend.qdrant_schema import (
    COLLECTION_NAME,
    ensure_collection,
)


def main():
    client = QdrantClient(
        host="localhost",
        port=6333,
    )

    ensure_collection(client)

    collection = client.get_collection(
        collection_name=COLLECTION_NAME,
    )

    print(f"Collection: {COLLECTION_NAME}")
    print(f"Vector size: {collection.config.params.vectors.size}")
    print(f"Distance: {collection.config.params.vectors.distance}")


if __name__ == "__main__":
    main()