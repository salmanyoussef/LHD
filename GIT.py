import argparse
from pathlib import Path
from difflib import ndiff

def git_diff_lines(old_lines, new_lines):
    """
    Simulate Git Diff by comparing two lists of lines.
    Lines starting with:
      - '  ' are unchanged
      - '- ' are deletions
      - '+ ' are additions
    """
    diff = ndiff(old_lines, new_lines)
    return list(diff)

def main():
    ap = argparse.ArgumentParser(description="Simulated Git Diff (compare any two text files)")
    ap.add_argument("old_file", type=Path, help="Path to the original file")
    ap.add_argument("new_file", type=Path, help="Path to the modified file")
    ap.add_argument("--out", type=Path, default=Path("git_diff_output.txt"), help="Output diff file")
    args = ap.parse_args()

    # Read files safely
    old_lines = args.old_file.read_text(encoding="utf-8", errors="replace").splitlines()
    new_lines = args.new_file.read_text(encoding="utf-8", errors="replace").splitlines()

    diff_result = git_diff_lines(old_lines, new_lines)

    # Write the diff result to a file
    with args.out.open("w", encoding="utf-8") as f:
        f.write("=== Simulated Git Diff Output ===\n\n")
        for line in diff_result:
            f.write(line + "\n")

    print(f"Diff complete! Output written to: {args.out}")
if __name__ == "__main__":
    main()
