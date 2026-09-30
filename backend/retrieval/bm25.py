import re
from rank_bm25 import BM25Okapi

from backend.ingestion.models import DocumentChunk


class BM25Retriever:
    def __init__(
        self,
        chunks: list[DocumentChunk],
    ):
        self.chunks = chunks

        self.tokenized_corpus = [
            self._tokenize(chunk.content)
            for chunk in chunks
        ]

        self.bm25 = BM25Okapi(
            self.tokenized_corpus
        )

    def search(
        self,
        query: str,
        top_k: int = 5,
        department: str | None = None,
        clearance_level: int | None = None,
    ) -> list[tuple[DocumentChunk, float]]:
        authorized_chunks = [
            chunk
            for chunk in self.chunks
            if (
                (
                    department is None
                    or chunk.department == "Global"
                    or chunk.department == department
                )
                and (
                    clearance_level is None
                    or chunk.min_clearance <= clearance_level
                )
            )
        ]

        if not authorized_chunks:
            return []

        tokenized_corpus = [
            self._tokenize(chunk.content)
            for chunk in authorized_chunks
        ]

        bm25 = BM25Okapi(tokenized_corpus)

        tokenized_query = self._tokenize(query)
        scores = bm25.get_scores(tokenized_query)

        ranked_indices = sorted(
            range(len(scores)),
            key=lambda i: scores[i],
            reverse=True,
        )

        results = []

        for index in ranked_indices[:top_k]:
            results.append(
                (
                    authorized_chunks[index],
                    float(scores[index]),
                )
            )

        return results

    def _tokenize(
        self,
        text: str,
    ) -> list[str]:
        return re.findall(
            r"[a-z0-9]+(?:[-_.][a-z0-9]+)*",
            text.lower(),
        )