#!/usr/bin/env python3
"""Extract one language (en|ru) from an interleaved bilingual case-study index.md.

The portfolio's case studies are single files that carry EN and RU side by side:

  * headings are joined as ``## 7. Title EN / Заголовок RU`` (bilingual on one line);
  * prose blocks are marked ``**EN:**`` … ``**RU:**`` (the marker may be inline with text);
  * the two byline lines directly under the H1 are EN then RU, one per line;
  * fenced code / mermaid and tables live inside an EN or RU block and follow its language.

This turns that interleaved file back into a clean single-language markdown so the existing
``build_pdf.py`` can render a per-language PDF (``pdfs/en.pdf`` / ``pdfs/ru.pdf``).

  python3 scripts/split_lang.py projects/<slug>/index.md en  > /tmp/en.md
"""
import sys, re

HEAD_RE = re.compile(r'^(#{1,6}\s+)(\d+\.\s+)?(.*)$')


def has_cyr(s):
    return any('Ѐ' <= c <= 'ӿ' for c in s)


def split_bilingual(text, lang):
    assert lang in ("en", "ru")
    want_en = lang == "en"
    out, mode = [], "both"          # mode: both | en | ru
    in_fence = False                # inside a ``` code/mermaid fence
    seen_h1 = False
    byline_left = 0                 # remaining byline lines to route after H1

    for raw in text.split("\n"):
        line = raw

        # Fenced code / mermaid: copy verbatim while in the active language (or both).
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            if mode in ("both", lang):
                out.append(line)
            continue
        if in_fence:
            if mode in ("both", lang):
                out.append(line)
            continue

        stripped = line.strip()

        # Headings — bilingual "EN / RU", optionally numbered. Preserve the number for both.
        m = HEAD_RE.match(line) if stripped.startswith("#") else None
        if m:
            prefix, num, rest = m.group(1), m.group(2) or "", m.group(3)
            if " / " in rest:
                en_part, ru_part = rest.split(" / ", 1)
                rest = en_part if want_en else ru_part
            out.append(f"{prefix}{num}{rest}")
            mode = "both"
            if not seen_h1:
                seen_h1, byline_left = True, 2      # next 2 non-blank lines are the byline
            continue

        # Language markers (may carry inline content after the marker).
        if stripped.startswith("**EN:**"):
            mode = "en"
            remainder = stripped[len("**EN:**"):].strip()
            if remainder and want_en:
                out.append(remainder)
            continue
        if stripped.startswith("**RU:**"):
            mode = "ru"
            remainder = stripped[len("**RU:**"):].strip()
            if remainder and not want_en:
                out.append(remainder)
            continue

        # Horizontal rule — structural, belongs to both.
        if stripped == "---":
            out.append(line)
            mode = "both"
            continue

        # Byline: the two lines right under the H1 (EN then RU), routed by script.
        if byline_left and stripped:
            is_ru = has_cyr(line)
            if want_en != is_ru:
                out.append(line)
            byline_left -= 1
            continue

        # Everything else follows the active mode; blanks/both-mode lines go to both.
        if mode == "both" or mode == lang:
            out.append(line)

    # Collapse 3+ blank lines the splitting may introduce.
    result = "\n".join(out)
    result = re.sub(r"\n{3,}", "\n\n", result)
    return result.strip() + "\n"


def main():
    if len(sys.argv) != 3 or sys.argv[2] not in ("en", "ru"):
        sys.exit("usage: split_lang.py <index.md> <en|ru>")
    with open(sys.argv[1], encoding="utf-8") as f:
        sys.stdout.write(split_bilingual(f.read(), sys.argv[2]))


if __name__ == "__main__":
    main()
