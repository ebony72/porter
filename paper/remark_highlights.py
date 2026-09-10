"""Retire the previous round's \\chg{} highlights and mark the current round instead.

Strips every existing \\chg{...} wrapper (balanced-brace aware, so nested
braces survive), then diffs each file against its state at the baseline commit
and wraps the runs of lines that changed.

Structural lines are never wrapped -- comments, \\item, sectioning, and any
line opening or closing an environment -- because a macro argument cannot
straddle \\begin/\\end.  Runs are extended forward until their braces balance,
and any run that cannot be balanced is reported and left unmarked rather than
guessed at.
"""
import re, subprocess, sys, difflib
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
BASE = "a9466d1"   # the end of round 5; bump this when a new round starts
FILES = sorted(p.relative_to(REPO).as_posix() for p in (REPO / "paper/sections").glob("*.tex"))
FILES.append("paper/sfc_appendix.tex")

STRUCT = re.compile(r"^\s*(%|\\item|\\(sub)*section|\\begin\{|\\end\{|\\label|\\caption|\\bibliography|\\input|\\appendix)")


def strip_chg(text: str) -> str:
    out, i = [], 0
    while True:
        j = text.find("\\chg{", i)
        if j < 0:
            out.append(text[i:]); break
        out.append(text[i:j])
        k = j + len("\\chg{"); depth = 1
        while k < len(text) and depth:
            c = text[k]
            if c == "{" and text[k-1] != "\\":
                depth += 1
            elif c == "}" and text[k-1] != "\\":
                depth -= 1
            k += 1
        out.append(text[j+len("\\chg{"):k-1])
        i = k
    return "".join(out)


def math_balanced(text: str) -> bool:
    """An even number of unescaped $, i.e. the text neither opens nor closes a
    math group it does not also close or open.  A \\chg{} that straddles a $
    puts a brace group across the math delimiter, which LaTeX rejects with
    "Missing } inserted" -- the failure this guard exists to prevent."""
    return sum(1 for i, c in enumerate(text)
               if c == "$" and (i == 0 or text[i-1] != "\\")) % 2 == 0


def balanced(lines) -> bool:
    s = "".join(lines)
    if not math_balanced(s):
        return False
    d = 0
    for n, c in enumerate(s):
        if c == "{" and (n == 0 or s[n-1] != "\\"):
            d += 1
        elif c == "}" and (n == 0 or s[n-1] != "\\"):
            d -= 1
            if d < 0:
                return False
    return d == 0


# A table data row: cells separated by & and terminated by \\.  Every existing
# mark in this manuscript sits in prose, never inside a row, and the table
# verifier parses those rows with regexes that a \chg{} wrapper would break.
# Any line carrying an unescaped alignment tab belongs to a tabular -- including
# a row continued across several source lines, which has no trailing \\ to
# recognise it by.  Marks stay in prose: that is the manuscript's own
# convention, and the table verifier parses those rows with regexes a \chg{}
# wrapper would break.
def has_alignment_tab(line: str) -> bool:
    return any(c == "&" and (i == 0 or line[i-1] != "\\")
               for i, c in enumerate(line))


def wrappable(line: str) -> bool:
    return (bool(line.strip()) and not STRUCT.match(line)
            and not has_alignment_tab(line))


def mark(old: str, new: str, path: str):
    o, n = strip_chg(old).splitlines(True), strip_chg(new).splitlines(True)
    sm = difflib.SequenceMatcher(None, [x.rstrip("\n") for x in o], [x.rstrip("\n") for x in n],
                                 autojunk=False)
    runs = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag in ("replace", "insert") and j2 > j1:
            runs.append((j1, j2))
    # Never mark the preamble of a standalone document: a \chg{} there emits
    # text before \begin{document}, and wrapping a \newcommand destroys the
    # definition -- which took out every xr macro in the appendix when this
    # guard was missing.
    body_start = 0
    for idx, line in enumerate(n):
        if line.lstrip().startswith("\\begin{document}"):
            body_start = idx + 1
            break
    # split each run around structural lines, then balance it
    final, skipped = [], []
    for a, b in runs:
        cur = []
        for idx in range(a, b):
            if idx >= body_start and wrappable(n[idx]):
                cur.append(idx)
            else:
                if cur:
                    final.append((cur[0], cur[-1] + 1)); cur = []
        if cur:
            final.append((cur[0], cur[-1] + 1))
    adjusted = []
    for a, b in final:
        end = b
        while end <= len(n) and not balanced(n[a:end]):
            end += 1
            if end - a > 40 or (end <= len(n) and end > b and not wrappable(n[end-1] if end <= len(n) else "")):
                break
        if end <= len(n) and balanced(n[a:end]):
            adjusted.append((a, end))
        else:
            skipped.append((a, b))
    # Trim a run to the words that actually changed: the line diff marks whole
    # lines, so a run starting mid-line would otherwise colour the tail of the
    # preceding sentence.  The prefix is taken as an exact slice of the new
    # line (backed off to a space) so the text round-trips byte for byte.
    def word_prefix_len(x, y):
        k = 0
        while k < min(len(x), len(y)) and x[k] == y[k]:
            k += 1
        while k > 0 and x[k-1] != " ":
            k -= 1
        return k

    old_first = {}
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "replace":
            for j in range(j1, j2):
                if i1 < len(o):
                    old_first[j] = o[i1].rstrip("\n")

    out = list(n)
    for a, b in sorted(adjusted, reverse=True):
        seg = list(out[a:b])
        k = 0
        if a in old_first:
            k = word_prefix_len(seg[0].rstrip("\n"), old_first[a])
            if (not seg[0][k:].strip() or not balanced([seg[0][:k]])
                    or not math_balanced(seg[0][:k])):
                k = 0
        body = "".join([seg[0][k:]] + seg[1:])
        if not body.strip():                       # nothing but whitespace: skip
            continue
        # Pure deletion: every word that survives on this line was already
        # there, so nothing was added and there is nothing to highlight.
        if len(seg) == 1 and a in old_first and body.strip() in old_first[a]:
            continue
        seg[0] = seg[0][:k] + "\\chg{" + seg[0][k:]
        tail = seg[-1]
        seg[-1] = (tail.rstrip("\n") + "}" + ("\n" if tail.endswith("\n") else ""))
        out[a:b] = seg
    return "".join(out), len(adjusted), skipped


def main():
    apply = "--write" in sys.argv
    total = 0
    for f in FILES:
        cur = (REPO / f).read_text()
        old = subprocess.run(["git", "-C", str(REPO), "show", f"{BASE}:{f}"],
                             capture_output=True, text=True).stdout
        if not old:
            print(f"  {f}: no baseline version, skipped"); continue
        before = cur.count("\\chg{")
        new_text, k, skipped = mark(old, cur, f)
        total += k
        print(f"  {f:<40} old marks {before:>3} -> new marks {k:>3}"
              + (f"   SKIPPED {len(skipped)} unbalanced run(s)" if skipped else ""))
        for a, b in skipped:
            print(f"      unmarked lines {a+1}-{b}")
        if apply:
            (REPO / f).write_text(new_text)
    print(f"\n  total new marks: {total}")


if __name__ == "__main__":
    main()
