import sys
import math
import difflib
import argparse
import re
from collections import Counter
from typing import List, Tuple, Dict

SIMHASH_BITS = 64         
CANDIDATES_PER_LINE = 15 
MAIN_SIM_THRESHOLD = 0.4   
SPLIT_SIM_THRESHOLD = 0.35  
CONTEXT_WINDOW = 4       

def normalize_line(s: str) -> str:
    """
    Normalize a line so that logically identical lines (even if they differ in spacing) are treated as equal.
    """
    s = s.strip().lower()
    # collapse multiple whitespace to a single space
    s = re.sub(r"\s+", " ", s)
    # remove spaces around punctuation/operators
    s = re.sub(r"\s*([=+\-*/\[\]\(\),])\s*", r"\1", s)
    return s


def is_blank(norm_line: str) -> bool:
    """Return True if a normalized line is empty/whitespace only."""
    return norm_line.strip() == ""

def tokenize(s: str) -> List[str]:
    """
    Split a string into word tokens. Non-alphanumeric characters are like separators.
    """
    tokens: List[str] = []
    token = ""
    for ch in s:
        if ch.isalnum() or ch == "_":
            token += ch
        else:
            if token:
                tokens.append(token)
                token = ""
    if token:
        tokens.append(token)
    return tokens

def get_context_window(lines: List[str], idx: int, window: int = CONTEXT_WINDOW) -> List[str]:
    start = max(0, idx - window)
    end = min(len(lines), idx + window + 1)
    return [lines[i] for i in range(start, end) if i != idx]


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


def context_vector(norm_lines: List[str], idx: int) -> Dict[str, float]:
 
    ctx_text = " ".join(get_context_window(norm_lines, idx))
    tokens = tokenize(ctx_text)
    if not tokens:
        return {}
    tf = Counter(tokens)
    return {t: float(c) for t, c in tf.items()}

def normalized_levenshtein(s1: str, s2: str) -> float:
    """
    Compute normalized Levenshtein distance between two strings.

    - Returns 0.0 if strings are identical.
    - Returns 1.0 if one is empty and the other is not.
    - Otherwise, distance / max(len(s1), len(s2)).

    This measures content difference between single lines.
    """
    if s1 == s2:
        return 0.0
    if not s1 or not s2:
        return 1.0

    len1, len2 = len(s1), len(s2)
    # Standard dynamic programming edit distance, but we only keep two rows.
    prev = list(range(len2 + 1))
    curr = [0] * (len2 + 1)

    for i in range(1, len1 + 1):
        curr[0] = i
        c1 = s1[i - 1]
        for j in range(1, len2 + 1):
            cost = 0 if c1 == s2[j - 1] else 1
            curr[j] = min(
                prev[j] + 1,      # deletion
                curr[j - 1] + 1,  # insertion
                prev[j - 1] + cost  # substitution
            )
        prev, curr = curr, prev

    ld = prev[len2]
    return ld / float(max(len1, len2))

def simhash(tokens: List[str], bits: int = SIMHASH_BITS) -> int:
    if not tokens:
        return 0
    v = [0] * bits
    for token in tokens:
        h = hash(token)
        for i in range(bits):
            bit = (h >> i) & 1
            v[i] += 1 if bit else -1
    result = 0
    for i in range(bits):
        if v[i] > 0:
            result |= (1 << i)
    return result


def hamming_distance(a: int, b: int) -> int:
    x = a ^ b
    count = 0
    while x:
        x &= x - 1   # drop the lowest set bit
        count += 1
    return count


def build_line_signatures(norm_lines: List[str], bits: int = SIMHASH_BITS) -> Tuple[List[int], List[int]]:

    content_hashes: List[int] = []
    context_hashes: List[int] = []

    for i in range(len(norm_lines)):
        content_tokens = tokenize(norm_lines[i])
        context_tokens = tokenize(" ".join(get_context_window(norm_lines, i)))
        content_hashes.append(simhash(content_tokens, bits))
        context_hashes.append(simhash(context_tokens, bits))

    return content_hashes, context_hashes

def get_candidates_for_line(
    del_idx: int,
    add_indices: List[int],
    old_content_hash: List[int],
    old_context_hash: List[int],
    new_content_hash: List[int],
    new_context_hash: List[int],
    k: int = CANDIDATES_PER_LINE,
    bits: int = SIMHASH_BITS
) -> List[int]:
   
    c_hash = old_content_hash[del_idx]
    ctx_hash = old_context_hash[del_idx]
    scores = []

    for j in add_indices:
        c2 = new_content_hash[j]
        ctx2 = new_context_hash[j]

        hd_c = hamming_distance(c_hash, c2)
        hd_ctx = hamming_distance(ctx_hash, ctx2)
        sim_c = 1.0 - hd_c / float(bits)
        sim_ctx = 1.0 - hd_ctx / float(bits)
        combined = 0.6 * sim_c + 0.4 * sim_ctx
        scores.append((combined, j))

    # Sort by similarity descending
    scores.sort(reverse=True, key=lambda x: x[0])
    # Keep only the candidate indices
    return [j for (score, j) in scores[:k]]

def detect_line_split(
    old_idx: int,
    first_new_idx: int,
    old_norm: List[str],
    new_norm: List[str],
    max_span: int = 4
) -> List[int]:

    base = old_norm[old_idx]
    best_indices = [first_new_idx]
    best_dist = normalized_levenshtein(base, new_norm[first_new_idx])

    cur_indices = list(best_indices)
    for step in range(1, max_span):
        next_idx = first_new_idx + step
        if next_idx >= len(new_norm):
            break
        cur_indices.append(next_idx)
        combined_text = " ".join(new_norm[k] for k in cur_indices)
        d = normalized_levenshtein(base, combined_text)
        if d < best_dist:
            best_dist = d
            best_indices = list(cur_indices)
        else:
            # once extending makes it worse, stop
            break

    return best_indices

def lhdiff(
    old_lines: List[str],
    new_lines: List[str]
) -> Dict[int, List[int]]:
   
    # Step 1: normalization
    old_norm = [normalize_line(s) for s in old_lines]
    new_norm = [normalize_line(s) for s in new_lines]

    # Step 2: detect unchanged lines via diff on normalized content
    # SequenceMatcher gives us blocks tagged as "equal", "replace", "delete", or "insert"
    sm = difflib.SequenceMatcher(None, old_norm, new_norm)
    opcodes = sm.get_opcodes()

    mapping: Dict[int, List[int]] = {}

    # indices of lines that are part of changes
    deletion_indices: List[int] = []
    addition_indices: List[int] = []

    for tag, i1, i2, j1, j2 in opcodes:
        if tag == "equal":
            # directly map unchanged lines (one-to-one)
            for offset in range(i2 - i1):
                old_idx = i1 + offset
                new_idx = j1 + offset
                mapping[old_idx] = [new_idx]
        else:
            # collect all deletion and insertion line indices within changed blocks
            if tag in ("delete", "replace") and i1 != i2:
                deletion_indices.extend(range(i1, i2))
            if tag in ("insert", "replace") and j1 != j2:
                addition_indices.extend(range(j1, j2))

    # If there are no deletions or no additions, nothing left to match
    if not deletion_indices or not addition_indices:
        return mapping

    # Step 3: build SimHash signatures and context vectors for all lines
    old_content_hash, old_context_hash = build_line_signatures(old_norm)
    new_content_hash, new_context_hash = build_line_signatures(new_norm)

    old_ctx_vecs = [context_vector(old_norm, i) for i in range(len(old_norm))]
    new_ctx_vecs = [context_vector(new_norm, j) for j in range(len(new_norm))]

    # Track "ownership" of each new-line index: which old line currently maps to it
    # and with what similarity score.
    new_line_owner: Dict[int, Tuple[int, float]] = {}

    # Seed ownership with the unchanged ("equal") mappings from diff
    for old_idx, new_list in mapping.items():
        for new_idx in new_list:
            new_line_owner[new_idx] = (old_idx, 1.0)

    # Step 4 & 5: handle changed (deleted) lines using candidates + split detection
    for i in deletion_indices:
        # skip lines already matched as equal (we don't want to remap them)
        if i in mapping:
            continue

        # do not try to match blank old lines
        if is_blank(old_norm[i]):
            continue

        # 3a: use SimHash-based nearest neighbor search to find candidate new lines
        candidates = get_candidates_for_line(
            i,
            addition_indices,
            old_content_hash,
            old_context_hash,
            new_content_hash,
            new_context_hash,
            k=CANDIDATES_PER_LINE,
            bits=SIMHASH_BITS
        )
        if not candidates:
            continue

        # 4: Among candidates, pick the best one using a more accurate similarity:
        #    combined = 0.6 * (content similarity using Levenshtein)
        #             + 0.4 * (context similarity using cosine)
        best_j = None
        best_score = 0.0

        for j in candidates:
            # do not match anything to blank new lines
            if is_blank(new_norm[j]):
                continue

            content_sim = 1.0 - normalized_levenshtein(old_norm[i], new_norm[j])
            ctx_sim = cosine_similarity(old_ctx_vecs[i], new_ctx_vecs[j])
            combined = 0.6 * content_sim + 0.4 * ctx_sim
            if combined > best_score:
                best_score = combined
                best_j = j

        # Apply main similarity threshold: if nothing is good enough, skip this line
        if best_j is None or best_score < MAIN_SIM_THRESHOLD:
            continue

        owner = new_line_owner.get(best_j)
        if owner is not None:
            owner_old, owner_score = owner
            if best_score <= owner_score:
                # existing mapping is better; skip this line
                continue
            else:
                # steal mapping: remove best_j from the previous owner
                if owner_old in mapping:
                    mapping[owner_old] = [k for k in mapping[owner_old] if k != best_j]
                    if not mapping[owner_old]:
                        del mapping[owner_old]

        # Step 5: line split detection (extend mapping from best_j to multiple new lines)
        split_indices = detect_line_split(i, best_j, old_norm, new_norm)

        final_new_indices: List[int] = []
        for j in split_indices:
            # Recompute similarity per new line (used to compare with existing owners)
            content_sim = 1.0 - normalized_levenshtein(old_norm[i], new_norm[j])
            ctx_sim = cosine_similarity(old_ctx_vecs[i], new_ctx_vecs[j])
            combined = 0.6 * content_sim + 0.4 * ctx_sim

            # Slightly lower threshold for additional split lines
            if combined < SPLIT_SIM_THRESHOLD:
                continue

            existing = new_line_owner.get(j)
            if existing is not None:
                owner_old, owner_score = existing
                if combined <= owner_score:
                    # someone else has a better claim
                    continue
                else:
                    # reassign from previous owner
                    if owner_old in mapping:
                        mapping[owner_old] = [k for k in mapping[owner_old] if k != j]
                        if not mapping[owner_old]:
                            del mapping[owner_old]

            final_new_indices.append(j)
            new_line_owner[j] = (i, combined)

        if final_new_indices:
            # Store sorted new indices for nicer output
            mapping[i] = sorted(final_new_indices)

    return mapping

def parse_args(argv: List[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="LHDiff-style line matcher: OLD_FILE NEW_FILE"
    )
    parser.add_argument("old_file", help="Path to old version")
    parser.add_argument("new_file", help="Path to new version")
    parser.add_argument(
        "--show-unmatched",
        action="store_true",
        help="Also print pure additions and deletions"
    )
    return parser.parse_args(argv[1:])


def main(argv: List[str]) -> None:
    args = parse_args(argv)

    with open(args.old_file, "r", encoding="utf-8", errors="replace") as f:
        old_lines = [line.rstrip("\r\n") for line in f]

    with open(args.new_file, "r", encoding="utf-8", errors="replace") as f:
        new_lines = [line.rstrip("\r\n") for line in f]

    mapping = lhdiff(old_lines, new_lines)

    # Print mappings with 1-based line numbers
    for old_idx in sorted(mapping.keys()):
        new_idxs = mapping[old_idx]
        new_str = ",".join(str(j + 1) for j in new_idxs)
        print(f"{old_idx + 1} -> {new_str}")

    # Print unmatched deletions/additions
    if args.show_unmatched:
        old_line_count = len(old_lines)
        new_line_count = len(new_lines)

        mapped_old = set(mapping.keys())
        mapped_new: set[int] = set()
        for new_list in mapping.values():
            mapped_new.update(new_list)

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
