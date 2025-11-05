import sys
import re
from pathlib import Path

def preprocess_text(text: str) -> str:
    """
    Cleans text by:
    1. Removing tabs and reducing multiple spaces to a single space per line.
    2. Collapsing consecutive blank lines (more than one) into a single blank line.
    """
    # Replace tabs with a single space
    text = text.replace('\t', ' ')
    
    # For each line, replace multiple spaces with a single one
    lines = []
    for line in text.splitlines():
        clean_line = re.sub(r' +', ' ', line.strip())
        lines.append(clean_line)
    
    cleaned_text = '\n'.join(lines)
    
    # Remove multiple blank lines (keep only one)
    cleaned_text = re.sub(r'\n{2,}', '\n\n', cleaned_text)
    
    return cleaned_text


def main():
    if len(sys.argv) < 2:
        print("Usage: python preprocess.py <input_file>")
        sys.exit(1)

    input_path = Path(sys.argv[1])

    if not input_path.exists():
        print(f"Error: File '{input_path}' not found.")
        sys.exit(1)

    # Read file content
    with input_path.open('r', encoding='utf-8') as f:
        original_text = f.read()

    # Process
    processed_text = preprocess_text(original_text)

    # Save result to new file
    output_path = input_path.with_name(f"{input_path.stem}_cleaned{input_path.suffix}")
    with output_path.open('w', encoding='utf-8') as f:
        f.write(processed_text)

    print(f"✅ Preprocessed file saved as: {output_path}")

if __name__ == "__main__":
    main()
