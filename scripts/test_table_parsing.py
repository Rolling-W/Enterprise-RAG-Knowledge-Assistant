from backend.ingestion.markdown_parser import MarkdownParser
from backend.ingestion.pdf_parser import UnstructuredPDFParser


def summarize_elements(name, elements):
    titles = [
        element
        for element in elements
        if element.element_type == "Title"
    ]

    body = [
        element
        for element in elements
        if element.element_type
        in {"NarrativeText", "Text", "ListItem"}
    ]

    tables = [
        element
        for element in elements
        if element.element_type == "Table"
    ]

    print(f"===== {name} =====")
    print(f"Total elements: {len(elements)}")
    print(f"Titles: {len(titles)}")
    print(f"Body elements: {len(body)}")
    print(f"Tables: {len(tables)}")

    if tables:
        print()
        print("Example table:")
        print(tables[0].text[:500])

    print("=" * 70)
    print()


def main():
    markdown_parser = MarkdownParser()

    markdown_elements = markdown_parser.parse(
        "sample_data/sample.md"
    )

    summarize_elements(
        "Markdown",
        markdown_elements,
    )

    pdf_parser = UnstructuredPDFParser(
        strategy="hi_res"
    )

    pdf_elements = pdf_parser.parse(
        "sample_data/project_charter.pdf"
    )

    summarize_elements(
        "PDF (hi_res)",
        pdf_elements,
    )


if __name__ == "__main__":
    main()