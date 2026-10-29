
from dataclasses import replace
from uuid import NAMESPACE_URL, uuid5

from backend.ingestion.models import DocumentElement
from backend.ingestion.text_utils import (
    count_text_units,
    split_text_by_units,
)


def split_oversized_element(
    element: DocumentElement,
    max_units: int,
) -> list[DocumentElement]:
    """Split an oversized element into traceable sub-elements."""
    if max_units <= 0:
        raise ValueError("max_units must be greater than 0")

    if count_text_units(element.text) <= max_units:
        return [element]

    parts = split_text_by_units(element.text, max_units)

    has_single_line = (
        element.line_start is not None
        and element.line_start == element.line_end
    )

    result = []

    for index, part in enumerate(parts):
        part_id = str(
            uuid5(
                NAMESPACE_URL,
                f"{element.element_id}:part:{index}:{part}",
            )
        )

        result.append(
            replace(
                element,
                element_id=part_id,
                text=part,
                sequence=element.sequence + index,
                line_start=element.line_start if has_single_line else None,
                line_end=element.line_end if has_single_line else None,
            )
        )

    return result
