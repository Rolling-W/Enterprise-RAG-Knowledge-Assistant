from marker.config.parser import ConfigParser
from marker.converters.pdf import PdfConverter
from marker.models import create_model_dict


def main():
    config = {
        "output_format": "json",
    }

    config_parser = ConfigParser(config)

    converter = PdfConverter(
        config=config_parser.generate_config_dict(),
        artifact_dict=create_model_dict(),
        processor_list=config_parser.get_processors(),
        renderer=config_parser.get_renderer(),
        llm_service=config_parser.get_llm_service(),
    )

    rendered = converter(
        "sample_data/project_charter.pdf"
    )

    print(f"Root block type: {rendered.block_type}")
    print(f"Top-level children: {len(rendered.children)}")
    print()

    first_page = rendered.children[0]

    print(f"First page type: {first_page.block_type}")
    print(f"First page polygon: {first_page.polygon}")
    print(f"First page children: {len(first_page.children)}")
    print()

    for block in first_page.children[:5]:
        print(f"Type: {block.block_type}")
        print(f"Polygon: {block.polygon}")
        print(f"HTML: {block.html[:300]}")
        print("-" * 80)


if __name__ == "__main__":
    main()