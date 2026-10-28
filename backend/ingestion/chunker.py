import re
from uuid import NAMESPACE_URL, uuid5

from backend.ingestion.models import DocumentChunk, DocumentElement
from backend.ingestion.text_utils import count_text_units
from backend.ingestion.element_splitter import split_oversized_element

class DocumentChunker:
    def chunk(
        self,
        elements: list[DocumentElement],
        document_id: str,
        department: str,
        min_clearance: int,
        max_words: int = 400,
        overlap_words: int = 50,
    ) -> list[DocumentChunk]:

        if max_words <= 0:
            raise ValueError("max_words must be greater than 0")

        if overlap_words < 0:
            raise ValueError("overlap_words cannot be negative")

        if overlap_words >= max_words:
            raise ValueError(
                "overlap_words must be smaller than max_words"
            )

        chunks: list[DocumentChunk] = []

        current_elements: list[DocumentElement] = []
        current_word_count = 0

        prepared_elements = []

        for element in elements:
            prepared_elements.extend(
                split_oversized_element(element, max_words)
            )

        for element in prepared_elements:
            word_count = count_text_units(element.text)

            size_exceeded = (
                current_elements
                and current_word_count + word_count > max_words
            )

            section_changed = (
                current_elements
                and self._is_section_heading(element)
            )

            if section_changed:
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

            elif size_exceeded:
                chunks.append(
                    self._build_chunk(
                        current_elements,
                        document_id,
                        department,
                        min_clearance,
                    )
                )

                current_elements = self._get_overlap_elements(
                    current_elements,
                    min(overlap_words, max_words - word_count),
                )

                current_word_count = sum(
                    count_text_units(overlap_element.text)
                    for overlap_element in current_elements
                )

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

        chunks = self._merge_short_heading_chunks(
            chunks,
            max_words=max_words,
        )

        return chunks

    def _get_overlap_elements(
        self,
        elements: list[DocumentElement],
        overlap_words: int,
    ) -> list[DocumentElement]:

        if overlap_words <= 0:
            return []

        overlap_elements: list[DocumentElement] = []
        overlap_count = 0

        for element in reversed(elements):
            word_count = count_text_units(element.text)

            if overlap_count + word_count > overlap_words:
                break

            overlap_elements.insert(0, element)
            overlap_count += word_count

        return overlap_elements

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

        title_elements = [
            element
            for element in elements
            if element.element_type == "Title"
        ]

        title = title_elements[0].text if title_elements else ""

        element_types = {
            element.element_type
            for element in elements
        }

        if element_types == {"Table"}:
            content_type = "table"
        else:
            content_type = "text"

        line_starts = [
            element.line_start
            for element in elements
            if element.line_start is not None
        ]

        line_ends = [
            element.line_end
            for element in elements
            if element.line_end is not None
        ]

        has_complete_line_metadata = all(
            element.line_start is not None
            and element.line_end is not None
            and element.line_start <= element.line_end
            for element in elements
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
            title=title,
            content=content,
            content_type=content_type,
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
            line_start=min(line_starts) if has_complete_line_metadata else None,
            line_end=max(line_ends) if has_complete_line_metadata else None,
        )

    def _is_section_heading(
        self,
        element: DocumentElement,
    ) -> bool:
        if element.element_type != "Title":
            return False

        if element.source_file.lower().endswith((".md", ".markdown")):
            return True

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
        max_words: int = 400,
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

            can_merge = (
                is_short_heading
                and i + 1 < len(chunks)
                and (
                    count_text_units(current.content)
                    + count_text_units(chunks[i + 1].content)
                    <= max_words
                )
            )

            if can_merge:
                next_chunk = chunks[i + 1]

                combined_content = (
                    current.content.strip()
                    + "\n\n"
                    + next_chunk.content
                )

                has_complete_line_metadata = all(
                    value is not None
                    for value in (
                        current.line_start,
                        current.line_end,
                        next_chunk.line_start,
                        next_chunk.line_end,
                    )
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
                    line_start=(
                        min(current.line_start, next_chunk.line_start)
                        if has_complete_line_metadata
                        else None
                    ),
                    line_end=(
                        max(current.line_end, next_chunk.line_end)
                        if has_complete_line_metadata
                        else None
                    ),
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
