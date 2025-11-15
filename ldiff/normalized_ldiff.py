#!/usr/bin/env python3
"""
ldiff.py  —  Rough re-implementation of ldiff (Canfora–Cerulo–Di Penta)

Given two versions of a file, outputs a sequence of line mappings:
    old_line_number -> new_line_number

It ALWAYS also prints:
  - unmatched deletions (lines only in OLD file)
  - unmatched additions (lines only in NEW file)
"""

import sys
import math
import difflib
from collections import Counter
from typing import List, Tuple, Dict

# ---------------------- Tokenization & TF-IDF ---------------------- #

def tokenize_line_range(lines: List[str]) -> List[str]:
    tokens = []
    for line in lines:
        token = ""
        for ch in line:
            if ch.isalnum() or ch == "_":
                token += ch
            else:
                if token:
                    tokens.append(token)
                    token = ""
        if token:
            tokens.append(token)
    return tokens


def build_tfidf_vectors(
    ranges: List[Tuple[int, int]],
    all_lines: List[str]
) -> Dict[Tuple[int, int], Dict[str, float]]:
    docs_tokens: Dict[Tuple[int, int], List[str]] = {}
    df: Counter = Counter()

    for (start, end) in ranges:
        tokens = tokenize_line_range(all_lines[start:end])
        docs_tokens[(start, end)] = tokens
        unique_tokens = set(tokens)
        for t in unique_tokens:
            df[t] += 1

    N = len(ranges)
    vectors: Dict[Tuple[int, int], Dict[str, float]] = {}

    for key, tokens in docs_tokens.items():
        tf = Counter(tokens)
        vec: Dict[str, float] = {}
        for t, f in tf.items():
            idf = math.log((N + 1.0) / (df[t] + 1.0)) + 1.0
            vec[t] = f * idf
        vectors[key] = vec

    return vectors


def cosine_similarity(vec1: Dict[str, float], vec2: Dict[str, float]) -> float:
    if not vec1 or not vec2:
        return 0.0
    if len(vec1) < len(vec2):
        smaller, larger = vec1, vec2
    else:
        smaller, larger = vec2, vec1
    dot = 0.0
    for t, w in smaller.items():
        w2 = larger.get(t)
        if w2 is not None:
            dot += w * w2
    norm1 = math.sqrt(sum(w * w for w in vec1.values()))
    norm2 = math.sqrt(sum(w * w for w in vec2.values()))
    if norm1 == 0.0 or norm2 == 0.0:
        return 0.0
    return dot / (norm1 * norm2)


# ---------------- Normalized Levenshtein Distance ------------------ #

def normalized_levenshtein(s1: str, s2: str) -> float:
    if s1 == s2:
        return 0.0
    if not s1 or not s2:
        return 1.0

    len1, len2 = len(s1), len(s2)
    prev = list(range(len2 + 1))
    curr = [0] * (len2 + 1)

    for i in range(1, len1 + 1):
        curr[0] = i
        c1 = s1[i - 1]
        for j in range(1, len2 + 1):
            cost = 0 if c1 == s2[j - 1] else 1
            curr[j] = min(
                prev[j] + 1,
                curr[j - 1] + 1,
                prev[j - 1] + cost
            )
        prev, curr = curr, prev

    ld = prev[len2]
    return ld / float(max(len1, len2))


# -------------------- Range Thinning (Algorithm 1) ----------------- #

def thin_change_relation(
    lstart: int, lend: int,
    rstart: int, rend: int,
    old_lines: List[str],
    new_lines: List[str],
    lev_threshold: float,
    mapping: Dict[int, int]
) -> None:
    sl = lstart
    sr = rstart

    while sl < lend and sr < rend:
        best_l = best_r = None
        best_d = None

        for l in range(sl, lend):
            s1 = old_lines[l]
            for r in range(sr, rend):
                s2 = new_lines[r]
                d = normalized_levenshtein(s1, s2)
                if best_d is None or d < best_d - 1e-9:
                    best_d = d
                    best_l, best_r = l, r
                elif best_d is not None and abs(d - best_d) < 1e-9:
                    if (l + r) < (best_l + best_r):
                        best_l, best_r = l, r

        if best_d is None or best_d >= lev_threshold:
            break

        mapping[best_l] = best_r
        sl = best_l + 1
        sr = best_r + 1


# ---------------------- Main ldiff Procedure ----------------------- #

def ldiff(
    old_lines: List[str],
    new_lines: List[str],
    cosine_threshold: float = 0.0,
    lev_threshold: float = 0.4
) -> Dict[int, int]:
    sm = difflib.SequenceMatcher(None, old_lines, new_lines)
    opcodes = sm.get_opcodes()

    mapping: Dict[int, int] = {}

    deletion_ranges: List[Tuple[int, int]] = []
    addition_ranges: List[Tuple[int, int]] = []

    for tag, i1, i2, j1, j2 in opcodes:
        if tag == "equal":
            for offset in range(i2 - i1):
                mapping[i1 + offset] = j1 + offset
        else:
            if tag in ("delete", "replace") and i1 != i2:
                deletion_ranges.append((i1, i2))
            if tag in ("insert", "replace") and j1 != j2:
                addition_ranges.append((j1, j2))

    if not deletion_ranges or not addition_ranges:
        return mapping

    del_vecs = build_tfidf_vectors(deletion_ranges, old_lines)
    add_vecs = build_tfidf_vectors(addition_ranges, new_lines)

    for d_range in deletion_ranges:
        d_vec = del_vecs[d_range]
        for a_range in addition_ranges:
            a_vec = add_vecs[a_range]
            sim = cosine_similarity(d_vec, a_vec)
            if sim > cosine_threshold:
                lstart, lend = d_range
                rstart, rend = a_range
                thin_change_relation(
                    lstart, lend, rstart, rend,
                    old_lines, new_lines,
                    lev_threshold,
                    mapping
                )

    return mapping


# -------------------------- CLI wrapper ---------------------------- #

def main(argv: List[str]) -> None:
    if len(argv) != 3:
        print(f"Usage: {argv[0]} OLD_FILE NEW_FILE", file=sys.stderr)
        sys.exit(1)

    old_path = argv[1]
    new_path = argv[2]

    with open(old_path, "r", encoding="utf-8", errors="replace") as f:
        old_lines = [line.rstrip("\n") for line in f]

    with open(new_path, "r", encoding="utf-8", errors="replace") as f:
        new_lines = [line.rstrip("\n") for line in f]

    mapping = ldiff(old_lines, new_lines)

    # ----- Print mappings (old_idx -> new_idx) -----
    for old_idx in sorted(mapping.keys()):
        new_idx = mapping[old_idx]
        print(f"{old_idx + 1} -> {new_idx + 1}")

    # ----- Always show unmatched lines -----
    old_line_count = len(old_lines)
    new_line_count = len(new_lines)
    mapped_old = set(mapping.keys())
    mapped_new = set(mapping.values())

    deletions = [i for i in range(old_line_count) if i not in mapped_old]
    additions = [j for j in range(new_line_count) if j not in mapped_new]

    if deletions:
        print("\n# Unmatched deletions (only in OLD file):")
        for i in deletions:
            print(f"OLD {i + 1}")
    if additions:
        print("\n# Unmatched additions (only in NEW file):")
        for j in additions:
            print(f"NEW {j + 1}")


if __name__ == "__main__":
    main(sys.argv)
