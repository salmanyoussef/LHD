#!/usr/bin/env python3

import sys

def read_file(path):

    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return [line.rstrip("\n") for line in f]
    except FileNotFoundError:
        print(f"Error: File not found -> {path}")
        sys.exit(1)


def compare_files(file1_lines, file2_lines):
    max_lines = max(len(file1_lines), len(file2_lines))

    for i in range(max_lines):
        # Handle cases where one file is shorter
        line1 = file1_lines[i] if i < len(file1_lines) else None
        line2 = file2_lines[i] if i < len(file2_lines) else None

        # Same line
        if line1 == line2:
            print(f"  Line {i+1}: same    -> {line1}")

        # Line added in file2
        elif line1 is None:
            print(f"+ Line {i+1}: added   -> {line2}")

        # Line removed from file1
        elif line2 is None:
            print(f"- Line {i+1}: removed -> {line1}")

        # Line changed between files
        else:
            print(f"~ Line {i+1}: changed from '{line1}' to '{line2}'")


def main():
    if len(sys.argv) != 3:
        print("Usage: python compare_lines.py FILE1 FILE2")
        sys.exit(1)

    file1_path = sys.argv[1]
    file2_path = sys.argv[2]

    file1_lines = read_file(file1_path)
    file2_lines = read_file(file2_path)

    compare_files(file1_lines, file2_lines)

if __name__ == "__main__":
    main()
