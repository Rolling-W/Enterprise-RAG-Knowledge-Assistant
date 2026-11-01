# Enterprise RAG Notes

## Hybrid Retrieval

The system combines BM25 sparse retrieval with dense vector search in Qdrant.

## Access Control

Role-based access control filters documents by department and clearance level.

## Parser Comparison

| Parser | Strength | Limitation |
|---|---|---|
| Unstructured | Fast integration | Weaker table reconstruction in fast mode |
| Marker | Strong Markdown reconstruction | Heavier dependencies |

## Citations

Answers should preserve source metadata for page-level and line-level citation.
