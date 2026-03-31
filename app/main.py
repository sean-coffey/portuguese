import sys
from pathlib import Path
from app.pipeline import process_document

def main():
    if len(sys.argv) < 2:
        print("Usage: python -m app.main input/my_phrases.docx")
        return

    input_path = sys.argv[1]
    input_name = Path(input_path).stem
    output_filename = f"{input_name}_with_images.docx"

    output_path = process_document(
        input_path=input_path,
        output_filename=output_filename
    )

    print(f"\nDone! Output saved at: {output_path}\n")


if __name__ == "__main__":
    main()