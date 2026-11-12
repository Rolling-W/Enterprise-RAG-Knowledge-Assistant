from qdrant_client import QdrantClient

from backend.qdrant_schema import (
    COLLECTION_NAME,
    access_filter,
)
from backend.retrieval.embedder import DenseEmbedder


def main():
    client = QdrantClient(
        host="localhost",
        port=6333,
    )

    embedder = DenseEmbedder()

    query = (
        "How does the project implement "
        "hybrid retrieval with BM25 and Qdrant?"
    )

    query_vector = embedder.embed_text(query)

    response = client.query_points(
        collection_name=COLLECTION_NAME,
        query=query_vector,
        query_filter=access_filter(
            clearance=1,
            department="Finance",
        ),
        limit=5,
        with_payload=True,
    )

    print(f"Query: {query}")
    print()

    for rank, point in enumerate(
        response.points,
        start=1,
    ):
        print(
            f"Rank {rank} | "
            f"Score: {point.score:.4f} | "
            f"Point ID: {point.id}"
        )

        print(
            f"Department: "
            f"{point.payload['department']}"
        )

        print(
            f"Clearance: "
            f"{point.payload['min_clearance']}"
        )

        print(
            f"Content: "
            f"{point.payload['content']}"
        )

        print("=" * 80)


if __name__ == "__main__":
    main()