
import re

from backend.ingestion.models import DocumentElement


def map_markdown_lines(
    elements: list[DocumentElement],
    source_text: str,
) -> None:
    """Assign source line ranges to unambiguously matched elements."""

    source_lines = source_text.splitlines()
    last_matched_line = 0

    for element in elements:
        target = " ".join(element.text.split())
        candidates = []

        for start_index in range(last_matched_line, len(source_lines)):
            if not source_lines[start_index].strip():
                continue

            combined_lines = []

            for end_index in range(start_index, len(source_lines)):
                normalized = source_lines[end_index].strip()

                # Remove Markdown heading markers.
                if element.element_type == "Title":
                    normalized = re.sub(
                        r"^#{1,6}\s+",
                        "",
                        normalized,
                    )

                if normalized:
                    combined_lines.append(normalized)

                combined = " ".join(" ".join(combined_lines).split())

                if combined == target:
                    candidates.append(
                        (start_index + 1, end_index + 1)
                    )
                    break

                # Stop when the candidate is no longer a prefix.
                if not target.startswith(combined):
                    break

        # Only assign line numbers for an unambiguous match.
        if len(candidates) == 1:
            line_start, line_end = candidates[0]

            element.line_start = line_start
            element.line_end = line_end

            last_matched_line = line_end
