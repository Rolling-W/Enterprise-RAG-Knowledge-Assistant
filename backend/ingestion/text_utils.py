
import re


def count_text_units(text: str) -> int:
    """
    Estimate text length for multilingual chunking.

    - Count CJK (Chinese/Japanese/Korean) characters individually.
    - Count other whitespace-separated tokens as one unit.
    - This is not an exact model token count.
    """
    pattern = (
        r"[\u3400-\u9fff\u3040-\u30ff\uac00-\ud7af]"
        r"|[^\s\u3400-\u9fff\u3040-\u30ff\uac00-\ud7af]+"
    )

    return len(re.findall(pattern, text))



def split_text_by_units(text: str, max_units: int) -> list[str]:
    """
    Split text while preserving the original characters.

    The resulting pieces can be concatenated to recover
    the original text exactly.
    """
    if max_units <= 0:
        raise ValueError("max_units must be greater than 0")

    if not text:
        return []

    pattern = (
        r"[\u3400-\u9fff\u3040-\u30ff\uac00-\ud7af]"
        r"|[^\s\u3400-\u9fff\u3040-\u30ff\uac00-\ud7af]+"
    )

    matches = list(re.finditer(pattern, text))
    pieces = []
    start = 0

    for i in range(max_units, len(matches), max_units):
        end = matches[i].start()
        pieces.append(text[start:end])
        start = end

    pieces.append(text[start:])

    return pieces
