#!/usr/bin/env python3
"""Flag the plain-writing rules that a script can check.

Usage: python3 check_text.py index.html README.md

The script checks for dashes, middle dots, curly quotes, sentences that start
with a demonstrative, negative parallelism, and words that the plain-writing
skill lists as overused. It skips <style> blocks in HTML files. It does not
replace reading the text against the skill, because most rules need a person
or a model to judge them.
"""
import re
import sys

CHARS = {
    "—": "em dash",
    "–": "en dash",
    "·": "middle dot",
    "“": "curly quote",
    "”": "curly quote",
    "‘": "curly quote",
    "’": "curly quote",
}
DEMONSTRATIVE = re.compile(r'(?:^|[.!?]["\']?\s+|>\s*|"\s*)(This|That|These|Those)\b')
NEG_PARALLEL = re.compile(r"\bnot (?:just|only|merely)\b", re.I)
WORDS = re.compile(
    r"\b(delve|tapestry|landscape|robust|leverag\w*|pivotal|renowned|testament|"
    r"seamless\w*|boasts?|game[- ]chang\w*|unlock\w*)\b",
    re.I,
)


def check(path):
    problems = []
    in_style = False
    with open(path, encoding="utf-8") as f:
        for n, line in enumerate(f, 1):
            if path.endswith(".html"):
                if "<style" in line:
                    in_style = True
                if in_style:
                    if "</style>" in line:
                        in_style = False
                    continue
            for ch, name in CHARS.items():
                if ch in line:
                    problems.append((n, name, line))
            for rx, name in (
                (DEMONSTRATIVE, "sentence starts with a demonstrative"),
                (NEG_PARALLEL, "negative parallelism"),
                (WORDS, "overused word"),
            ):
                m = rx.search(line)
                if m:
                    problems.append((n, f"{name} ({m.group(0).strip()})", line))
    return problems


def main():
    if len(sys.argv) < 2:
        print(__doc__.strip())
        return 2
    total = 0
    for path in sys.argv[1:]:
        for n, name, line in check(path):
            total += 1
            snippet = line.strip()
            if len(snippet) > 140:
                snippet = snippet[:140] + "..."
            print(f"{path}:{n}: {name}\n    {snippet}")
    print(f"{total} problem(s) found")
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main())
