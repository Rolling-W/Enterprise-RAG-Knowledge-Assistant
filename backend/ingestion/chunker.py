import re
from uuid import NAMESPACE_URL, uuid5

from backend.ingestion.models import DocumentChunk, DocumentElement


class DocumentChunker:
    def chunk(
        self,
        elements: list[DocumentElement],
        document_id: str,
        department: str,
        min_clearance: int,
        max_words: int = 400,
    ) -> list[DocumentChunk]:

        chunks: list[DocumentChunk] = []

        current_elements: list[DocumentElement] = []
        current_word_count = 0

        for element in elements:
            word_count = len(element.text.split())

            size_exceeded = (
                current_elements
                and current_word_count + word_count > max_words
            )

            section_changed = (
                current_elements
                and self._is_section_heading(element)
            )

            if size_exceeded or section_changed:
                chunks.append(
                    self._build_chunk(
                        current_elements,
                        document_id,
                        department,
                        min_clearance,
                    )
                )

                current_elements = []
                current_word_count = 0

            current_elements.append(element)
            current_word_count += word_count

        if current_elements:
            chunks.append(
                self._build_chunk(
                    current_elements,
                    document_id,
                    department,
                    min_clearance,
                )
            )

        chunks = self._merge_short_heading_chunks(chunks)

        return chunks

    def _build_chunk(
        self,
        elements: list[DocumentElement],
        document_id: str,
        department: str,
        min_clearance: int,
    ) -> DocumentChunk:

        content = "\n\n".join(
            element.text for element in elements
        )

        return DocumentChunk(
            chunk_id=self._make_chunk_id(
                document_id=document_id,
                source_file=elements[0].source_file,
                page_start=min(
                    element.page_number for element in elements
                ),
                page_end=max(
                    element.page_number for element in elements
                ),
                content=content,
            ),
            document_id=document_id,
            title="",
            content=content,
            content_type="text",
            source_file=elements[0].source_file,
            page_start=min(
                element.page_number for element in elements
            ),
            page_end=max(
                element.page_number for element in elements
            ),
            element_ids=[
                element.element_id for element in elements
            ],
            department=department,
            min_clearance=min_clearance,
        )

    def _is_section_heading(
        self,
        element: DocumentElement,
    ) -> bool:
        if element.element_type != "Title":
            return False

        text = element.text.strip()

        # Accept numbered headings such as:
        # "1 Project Background"
        # "2.1 Objectives"
        # "2.10 Options Analysis"
        if not re.match(
            r"^\d+(?:\.\d+)?\s+\S+",
            text,
        ):
            return False

        # Exclude values that look like durations rather than headings.
        if re.fullmatch(
            r"\d+(?:\.\d+)?\s+"
            r"(weeks?|days?|months?|years?|hours?|minutes?)",
            text,
            re.IGNORECASE,
        ):
            return False

        return True

    def _merge_short_heading_chunks(
        self,
        chunks: list[DocumentChunk],
        max_heading_words: int = 10,
    ) -> list[DocumentChunk]:

        if not chunks:
            return chunks

        merged: list[DocumentChunk] = []
        i = 0

        while i < len(chunks):
            current = chunks[i]

            words = current.content.split()

            is_short_heading = (
                len(words) <= max_heading_words
                and re.match(
                    r"^\d+\s+\S+",
                    current.content.strip(),
                )
            )

            if (
                is_short_heading
                and i + 1 < len(chunks)
            ):
                next_chunk = chunks[i + 1]

                combined_content = (
                    current.content.strip()
                    + "\n\n"
                    + next_chunk.content
                )

                combined = DocumentChunk(
                    chunk_id=self._make_chunk_id(
                        document_id=current.document_id,
                        source_file=current.source_file,
                        page_start=current.page_start,
                        page_end=next_chunk.page_end,
                        content=combined_content,
                    ),
                    document_id=current.document_id,
                    title=current.content.strip(),
                    content=combined_content,
                    content_type=next_chunk.content_type,
                    source_file=current.source_file,
                    page_start=current.page_start,
                    page_end=next_chunk.page_end,
                    element_ids=(
                        current.element_ids
                        + next_chunk.element_ids
                    ),
                    department=current.department,
                    min_clearance=current.min_clearance,
                    line_start=current.line_start,
                    line_end=next_chunk.line_end,
                )

                merged.append(combined)
                i += 2
                continue

            merged.append(current)
            i += 1

        return merged

    def _make_chunk_id(
        self,
        document_id: str,
        source_file: str,
        page_start: int,
        page_end: int,
        content: str,
    ) -> str:
        stable_key = (
            f"{document_id}|"
            f"{source_file}|"
            f"{page_start}|"
            f"{page_end}|"
            f"{content}"
        )

        return str(
            uuid5(
                NAMESPACE_URL,
                stable_key,
            )
        )