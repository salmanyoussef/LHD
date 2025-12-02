#!/usr/bin/env python3
import sys
import re
import math
import string
import difflib
from collections import Counter
from typing import List, Dict, Set, Tuple

SIMHASH_BITS = 64
K_CANDIDATES = 15
SIM_THRESHOLD = 0.35
SPLIT_THRESHOLD = 0.65
MERGE_THRESHOLD = 0.65


def preprocess_line(line: str) -> str:
    line = line.rstrip("\n").lower()
    punctuation_to_remove = ''.join(ch for ch in string.punctuation if ch not in "{}")
    table = str.maketrans('', '', punctuation_to_remove)
    line = line.translate(table)
    line = re.sub(r"\s+", " ", line)
    return line.strip()


def preprocess_file(lines):
    return [preprocess_line(l) for l in lines]


def is_blank_pre(line: str) -> bool:
    return line == ""

def structural_tokens(line: str) -> List[str]:
    if not line:
        return []
    raw = re.split(r"[^a-z0-9_]+", line)
    t = []
    for tok in raw:
        if not tok:
            continue
        if tok in KEYWORDS:
            t.append(tok)
        elif tok.isdigit():
            t.append("NUM")
        else:
            t.append("ID")
    return t


def structural_string(line: str) -> str:
    return " ".join(structural_tokens(line))


def build_context(pre_lines, idx, window=4):
    n = len(pre_lines)
    parts = []

    cnt = 0
    j = idx - 1
    while j >= 0 and cnt < window:
        if not is_blank_pre(pre_lines[j]):
            parts.append(pre_lines[j])
            cnt += 1
        j -= 1

    cnt = 0
    j = idx + 1
    while j < n and cnt < window:
        if not is_blank_pre(pre_lines[j]):
            parts.append(pre_lines[j])
            cnt += 1
        j += 1

    return " ".join(parts)


def levenshtein(a, b):
    if a == b:
        return 0
    la, lb = len(a), len(b)
    if la == 0:
        return lb
    if lb == 0:
        return la

    prev = list(range(lb + 1))
    cur = [0] * (lb + 1)

    for i in range(1, la + 1):
        cur[0] = i
        ca = a[i - 1]
        for j in range(1, lb + 1):
            cb = b[j - 1]
            cost = 0 if ca == cb else 1
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + cost)
        prev, cur = cur, prev

    return prev[lb]


def norm_lev(a, b):
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    d = levenshtein(a, b)
    m = max(len(a), len(b))
    return 1.0 - d / m


def cosine(a, b):
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    ca = Counter(a.split())
    cb = Counter(b.split())
    dot = sum(ca[t] * cb.get(t, 0) for t in ca)
    na = math.sqrt(sum(v * v for v in ca.values()))
    nb = math.sqrt(sum(v * v for v in cb.values()))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def combined(ca, cb, sa, sb, xa, xb):
    return 0.5 * norm_lev(ca, cb) + 0.3 * norm_lev(sa, sb) + 0.2 * cosine(xa, xb)


def simhash(tokens: List[str], bits=SIMHASH_BITS) -> int:
    if not tokens:
        return 0
    v = [0] * bits
    for tok in tokens:
        h = hash(tok)
        for i in range(bits):
            if (h >> i) & 1:
                v[i] += 1
            else:
                v[i] -= 1
    x = 0
    for i in range(bits):
        if v[i] > 0:
            x |= (1 << i)
    return x


def hamming(a, b):
    x = a ^ b
    c = 0
    while x:
        x &= x - 1
        c += 1
    return c


def find_unchanged(pre_old, pre_new, blank_old, blank_new):
    sm = difflib.SequenceMatcher(None, pre_old, pre_new, autojunk=False)
    m = {}
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            for k in range(i2 - i1):
                oi = i1 + k
                nj = j1 + k
                if oi in blank_old or nj in blank_new:
                    continue
                m[oi] = nj
    return m


def compute_mapping(old_lines: List[str], new_lines: List[str]):
    n_old = len(old_lines)
    n_new = len(new_lines)

    pre_old = preprocess_file(old_lines)
    pre_new = preprocess_file(new_lines)

    blank_old = {i for i, s in enumerate(pre_old) if is_blank_pre(s)}
    blank_new = {j for j, s in enumerate(pre_new) if is_blank_pre(s)}

    struct_old = [structural_string(s) for s in pre_old]
    struct_new = [structural_string(s) for s in pre_new]
    ctx_old = [build_context(pre_old, i) for i in range(n_old)]
    ctx_new = [build_context(pre_new, j) for j in range(n_new)]

    hash_old = [simhash(structural_tokens(s)) for s in pre_old]
    hash_new = [simhash(structural_tokens(s)) for s in pre_new]

    unchanged = find_unchanged(pre_old, pre_new, blank_old, blank_new)
    used_old = set(unchanged.keys())
    used_new = set(unchanged.values())

    pairs = []
    for i in range(n_old):
        if i in used_old or i in blank_old:
            continue

        sims = []
        hi = hash_old[i]
        for j in range(n_new):
            if j in used_new or j in blank_new:
                continue
            hd = hamming(hi, hash_new[j])
            sims.append((1.0 - hd / SIMHASH_BITS, j))

        if not sims:
            continue

        sims.sort(reverse=True)
        for _, j in sims[:K_CANDIDATES]:
            score = combined(pre_old[i], pre_new[j],
                             struct_old[i], struct_new[j],
                             ctx_old[i], ctx_new[j])
            pairs.append((score, i, j))

    pairs.sort(reverse=True)
    primary = dict(unchanged)

    for score, i, j in pairs:
        if score < SIM_THRESHOLD:
            break
        if i in used_old or j in used_new:
            continue
        primary[i] = j
        used_old.add(i)
        used_new.add(j)

    mapping = {i: set() for i in range(n_old)}
    for i, j in primary.items():
        mapping[i].add(j)

    for i in range(n_old):
        if not mapping[i] or i in blank_old:
            continue
        j0 = sorted(mapping[i])[0]

        for k in (j0 - 1, j0 + 1):
            if 0 <= k < n_new and k not in mapping[i] and k not in blank_new:
                score = combined(pre_old[i], pre_new[k],
                                 struct_old[i], struct_new[k],
                                 ctx_old[i], ctx_new[k])
                if score >= SPLIT_THRESHOLD:
                    mapping[i].add(k)

    for i in range(n_old):
        if not mapping[i] or i in blank_old:
            continue
        j0 = sorted(mapping[i])[0]

        for nb in (i - 1, i + 1):
            if nb < 0 or nb >= n_old:
                continue
            if mapping[nb] or nb in blank_old:
                continue
            score = combined(pre_old[nb], pre_new[j0],
                             struct_old[nb], struct_new[j0],
                             ctx_old[nb], ctx_new[j0])
            if score >= MERGE_THRESHOLD:
                mapping[nb].add(j0)

    final = {}
    for i in range(n_old):
        final[i + 1] = sorted(j + 1 for j in mapping[i])
    return final


def print_mapping(mapping, pre_old, pre_new):
    for i in sorted(mapping.keys()):
        if is_blank_pre(pre_old[i - 1]):
            continue
        t = mapping[i]
        if not t:
            continue
        if len(t) == 1:
            print(f"{i} -> {t[0]}")
        else:
            print(f"{i} -> {', '.join(str(x) for x in t)}")

    print("\n# Unmatched deletions (only in OLD file):")
    dels = [i for i, t in mapping.items() if not t and not is_blank_pre(pre_old[i - 1])]
    for d in dels:
        print(f"OLD {d}")
    if not dels:
        print("(none)")

    print("\n# Unmatched additions (only in NEW file):")
    used_new = set()
    for t in mapping.values():
        used_new.update(t)
    adds = [j for j in range(1, len(pre_new)+1)
            if j not in used_new and not is_blank_pre(pre_new[j - 1])]
    for a in adds:
        print(f"NEW {a}")
    if not adds:
        print("(none)")


def main():
    if len(sys.argv) != 3:
        print("Usage: python3 lhdiff.py <old> <new>")
        sys.exit(1)

    old = open(sys.argv[1], encoding="utf-8").read().splitlines(True)
    new = open(sys.argv[2], encoding="utf-8").read().splitlines(True)

    pre_old = preprocess_file(old)
    pre_new = preprocess_file(new)

    mapping = compute_mapping(old, new)
    print_mapping(mapping, pre_old, pre_new)


if __name__ == "__main__":
    main()

