\# \*\*LDiF: A Complete Technical Overview + Detailed Explanation of the Implementation\*\*



\## \*\*Table of Contents\*\*

1\. \[What Is LDiF?](#what-is-ldif)  

2\. \[Why LDiF Exists](#why-ldif-exists)  

3\. \[Core Concepts](#core-concepts)  

4\. \[LDiF Algorithm (Original MSR/ICSE Papers)](#ldif-algorithm)  

5\. \[Limitations](#limitations)  

6\. \[Our Python Implementation Overview](#our-python-implementation)  

7\. \[Detailed Walk-Through of the Code](#code-walkthrough)  

8\. \[How Output Is Generated](#output-format)  

9\. \[Example Output](#example-output)  

10\. \[Possible Extensions](#extensions)



---



\# \*\*1. What Is LDiF?\*\*

LDiF (“\*\*Language-independent Differencing\*\*”) is a \*\*line-matching technique\*\* used in software evolution research to track which lines in a source file correspond across two versions of the file.



It was introduced in:



\- Canfora, Cerulo, and Di Penta (MSR 2007)

\- Expanded in the ICSE 2009 paper



LDiF is widely used in:

\- Software evolution studies  

\- Defect injection studies  

\- Code churn analysis  

\- Fine-grained change tracking  



Its goal is to find \*\*line-level correspondences\*\* between two source code files \*\*regardless of programming language\*\*, without relying on syntax, ASTs, or compilers.



---



\# \*\*2. Why LDiF Exists\*\*

Traditional diff algorithms (e.g., GNU diff, Myers diff) are good at detecting:

\- Insertions  

\- Deletions  

\- Replacements  



But they \*\*fail\*\* when:

\- Large blocks are moved  

\- Code is refactored  

\- Lines are reordered  

\- Comments are edited separately  

\- File content changes structurally  



LDiF bridges this gap by combining:

1\. \*\*Text diff\*\*  

2\. \*\*IR techniques (tf-idf cosine similarity)\*\*  

3\. \*\*String similarity (Normalized Levenshtein Distance)\*\*  



This hybrid approach handles more complex changes.



---



\# \*\*3. Core Concepts\*\*

\### \*\*3.1 Range Matching\*\*

Instead of comparing lines directly, LDiF:

\- Identifies \*deleted ranges\* in OLD file  

\- Identifies \*inserted ranges\* in NEW file  

\- Uses \*\*tf-idf cosine similarity\*\* to determine which OLD-ranges correspond to which NEW-ranges



\### \*\*3.2 Tokenization\*\*

Each range is turned into a “bag of tokens.”  

Tokens include:

\- Identifiers  

\- Numbers  

\- Words  

\- etc.



\### \*\*3.3 Cosine Similarity\*\*

Given range A and B:

\- Count tokens  

\- Weight tokens with tf-idf  

\- Compute the cosine similarity  

\- If similarity > threshold (typically 0), treat ranges as “related”



\### \*\*3.4 Normalized Levenshtein Distance (NLD)\*\*

Within each matched range pair:

\- Compare each OLD line to each NEW line  

\- Compute edit distance  

\- Normalize by max(line length)  

\- Greedily pick the minimal pair  

\- Continue until distance ≥ 0.4 or no lines remain



\### \*\*3.5 Final Output\*\*

For each OLD line:

\- A NEW line index if matched  

\- Otherwise, "DELETED"



For each NEW line:

\- If unmatched: "ADDED"



---



\# \*\*4. LDiF Algorithm\*\*

\### \*\*Step 1 – Initial diff\*\*

Use Myers algorithm to classify:

\- equal  

\- delete  

\- insert  

\- replace  



\### \*\*Step 2 – Build range pairs\*\*

For each delete-range and each insert-range:

\- Tokenize lines  

\- Compute tf-idf vector per range  

\- Compute cosine similarity  

\- If similarity > threshold:

&nbsp; → consider ranges corresponding



\### \*\*Step 3 – Range Thinning (Algorithm 1)\*\*

Within each matching range pair:

\- Compute the pairwise normalized Levenshtein distance

\- Greedily map the smallest-distance pair

\- Continue until threshold exceeded

\- Ensures no line-splitting is detected  

&nbsp; (LDiF \*\*does not\*\* handle line splits!)



\### \*\*Step 4 – Final matching\*\*

\- Equal lines are mapped directly  

\- “Thinned” matches are inserted  

\- Unmapped OLD lines → deleted  

\- Unmapped NEW lines → added  



---



\# \*\*5. Limitations\*\*

\### ❌ Does not detect line splitting  

If one line becomes multiple, LDiF picks only \*\*one\*\* as the match.



\### ❌ Independent of syntax  

It does not use ASTs, so meaning-preserving refactors may confuse it.



\### ❌ Range granularity  

Cosine similarity may match semantically unrelated ranges if tokens overlap.



\### ❌ NLD is quadratic  

Large ranges become expensive.



---



\# \*\*6. Our Python Implementation\*\*

Your implementation faithfully reproduces the published LDiF algorithm:



✔ Myers diff via `difflib.SequenceMatcher`  

✔ Range cosine similarity using custom tf-idf  

✔ Normalized Levenshtein-based thinning  

✔ Greedy matching strategy 

✔ Always prints unmatched lines  



The program takes:



```

python ldiff.py old\_file new\_file

```



It outputs:



\- Line mappings  

\- Unmatched deletions  

\- Unmatched additions  



---



\# \*\*7. Detailed Walk-Through of the Code\*\*



\## \*\*7.1 Tokenization\*\*

Splits each range into alphanumeric tokens. Required because LDiF is language-independent.



\## \*\*7.2 TF-IDF Construction\*\*

Builds a tf-idf vector for each deleted/inserted range.



\## \*\*7.3 Cosine Similarity\*\*

Computes dot product / (norm1 \* norm2).



\## \*\*7.4 Normalized Levenshtein Distance (NLD)\*\*

Normalized LD = LD / max(len(s1), len(s2)).



\## \*\*7.5 Range Thinning Algorithm\*\*

Implements Algorithm 1 from the ICSE paper.



\## \*\*7.6 LDiF Main Procedure\*\*

Collects delete/insert ranges, matches them, and constructs line mappings.



\## \*\*7.7 Printing Results\*\*

Unmatched deletions/additions are always shown.



---



\# \*\*8. How Output Format Works\*\*

Printed format:



```

OLD -> NEW

```



followed by:



```

\# Unmatched deletions (only in OLD file):

OLD <n>



\# Unmatched additions (only in NEW file):

NEW <n>

```



---



\# \*\*9. Example Output\*\*



```

1 -> 1

3 -> 2

4 -> 4



\# Unmatched deletions (only in OLD file):

OLD 2



\# Unmatched additions (only in NEW file):

NEW 3

```



---



\# \*\*10. Possible Extensions\*\*

\- Add JSON output  

\- Add syntax-aware diff  

\- Add movement detection  

\- Add colorized terminal output  



---





