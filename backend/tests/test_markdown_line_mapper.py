"""Regression tests for Markdown source line mapping."""

import unittest

from backend.ingestion.markdown_parser import MarkdownParser


class MarkdownLineMapperTests(unittest.TestCase):

    def test_blank_lines_between_sections_preserve_line_numbers(self):
        elements = MarkdownParser().parse("sample_data/test_sections.md")

        expected = [
            ("Project Overview", 1, 1),
            (
                "This project implements an enterprise RAG knowledge assistant.",
                3, 3,
            ),
            ("System Architecture", 5, 5),
            (
                "The backend uses FastAPI and Qdrant for document retrieval.",
                7, 7,
            ),
            ("Access Control", 9, 9),
            (
                "Documents are restricted by department and clearance level.",
                11, 11,
            ),
        ]

        actual = [
            (element.text, element.line_start, element.line_end)
            for element in elements
        ]

        self.assertEqual(actual, expected)


if __name__ == "__main__":
    unittest.main()
