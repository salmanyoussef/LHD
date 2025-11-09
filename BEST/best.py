import argparse, re
from pathlib import Path
from difflib import SequenceMatcher

def norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip().lower())

def sim(a: str, b: str) -> float:
    return SequenceMatcher(None, norm(a), norm(b)).ratio()

def best_line_map(old_lines, new_lines, threshold=0.75, monotone=True):
    mapping = []            # (old_idx, new_idx or -1, score or None)
    j_start = 0             # enforce monotone left→right matches in new
    used = set()

    for i, old in enumerate(old_lines, 1):
        best_j, best_s = -1, 0.0
        rng = range(j_start, len(new_lines)) if monotone else range(0, len(new_lines))
        for j in rng:
            if j in used: 
                continue
            s = sim(old, new_lines[j])
            if s > best_s:
                best_s, best_j = s, j
        if best_s >= threshold:
            mapping.append((i, best_j+1, round(best_s, 3)))
            used.add(best_j)
            if monotone:
                j_start = best_j + 1
        else:
            mapping.append((i, -1, None))  # treat as DELETED (no good match)
    return mapping

def main():
    ap = argparse.ArgumentParser(description="W_BEST_LINE-style line mapper (TXT out)")
    ap.add_argument("old_file", type=Path)
    ap.add_argument("new_file", type=Path)
    ap.add_argument("--out", type=Path, default=Path("mapping.txt"))
    ap.add_argument("--threshold", type=float, default=0.75)
    ap.add_argument("--no-monotone", action="store_true", help="disable order constraint")
    args = ap.parse_args()

    old_lines = args.old_file.read_text(encoding="utf-8", errors="replace").splitlines()
    new_lines = args.new_file.read_text(encoding="utf-8", errors="replace").splitlines()

    mapping = best_line_map(old_lines, new_lines, threshold=args.threshold, monotone=not args.no_monotone)

    with args.out.open("w", encoding="utf-8") as f:
        f.write("# old_line -> new_line  score   (new_line=- means DELETED)\n")
        for i, j, s in mapping:
            f.write(f"{i:>5} -> {('-' if j==-1 else j):<5}  {'' if s is None else s}\n")

if __name__ == "__main__":
    main()
