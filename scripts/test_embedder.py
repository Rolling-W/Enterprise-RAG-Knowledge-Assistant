from backend.retrieval.embedder import DenseEmbedder


def main():
    embedder = DenseEmbedder()

    text = (
        "Hybrid retrieval combines BM25 "
        "with dense vector search."
    )

    vector = embedder.embed_text(text)

    print(f"Vector length: {len(vector)}")
    print(f"First 5 values: {vector[:5]}")


if __name__ == "__main__":
    main()