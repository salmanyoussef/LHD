import argparse
from pathlib import Path
from difflib import SequenceMatcher
import re

def norm(s: str) -> str:
    """Normalize by trimming, lowering, and collapsing spaces."""
    return re.sub(r"\s+", " ", s.strip().lower())

def sim(a: str, b: str) -> float:
    """Compute similarity using difflib ratio."""
    return SequenceMatcher(None, norm(a), norm(b)).ratio()

def best_line_map(old_lines, new_lines, threshold=0.75, monotone=True):
    mapping = []
    used = set()
    j_start = 0

    for i, old in enumerate(old_lines, 1):
        best_j, best_s = -1, 0.0
        rng = range(j_start, len(new_lines)) if monotone else range(len(new_lines))
        for j in rng:
            if j in used:
                continue
            s = sim(old, new_lines[j])
            if s > best_s:
                best_s, best_j = s, j
        if best_s >= threshold:
            mapping.append((i, best_j + 1))
            used.add(best_j)
            if monotone:
                j_start = best_j + 1
        else:
            mapping.append((i, -1))
    return mapping, used

def main():
    ap = argparse.ArgumentParser(description="Git Diff -> W_BEST_LINE style output")
    ap.add_argument("old_file", type=Path)
    ap.add_argument("new_file", type=Path)
    ap.add_argument("--threshold", type=float, default=0.75)
    args = ap.parse_args()

    old_lines = args.old_file.read_text(encoding="utf-8", errors="replace").splitlines()
    new_lines = args.new_file.read_text(encoding="utf-8", errors="replace").splitlines()

    mapping, used_new = best_line_map(old_lines, new_lines, threshold=args.threshold)

    # Print line-to-line mappings
    for i, j in mapping:
        if j != -1:
            print(f"{i} -> {j}")

    # Print unmatched deletions
    deleted = [i for i, j in mapping if j == -1]
    if deleted:
        print("\n# Unmatched deletions (only in OLD file):")
        for i in deleted:
            print(f"OLD {i}")

    # Print unmatched additions
    new_only = [j+1 for j in range(len(new_lines)) if j not in used_new]
    if new_only:
        print("\n# Unmatched additions (only in NEW file):")
        for j in new_only:
            print(f"NEW {j}")

if __name__ == "__main__":
    main()
