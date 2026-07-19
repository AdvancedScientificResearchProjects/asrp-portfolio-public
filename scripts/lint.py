#!/usr/bin/env python3
"""Validate every projects/<slug>/index.md against the closed schema + confidentiality rules.

Exit 1 on any error. Warnings do not fail. Run before committing."""
import re, sys
from _common import (load_projects, DOMAINS, STACK, TYPES, ORGS, ENGAGEMENTS, STATUSES,
                     TIERS, REQUIRED_KEYS, OPTIONAL_KEYS)

errors, warnings = [], []


def E(slug, msg): errors.append(f"[{slug}] {msg}")
def W(slug, msg): warnings.append(f"[{slug}] {msg}")


def check_sections(slug, body, ptype):
    heads = [h.lower() for h in re.findall(r'^#{1,3}\s+(.+)$', body, re.M)]
    joined = " || ".join(heads)
    need = [("executive summary", "executive summary"),
            ("architecture", "architecture"),
            ("stack/technology", r"stack|technolog"),
            ("what ASRP delivered/contributed", r"deliver|contribut")]
    if ptype == "client-engagement":
        need.append(("FAQ", "faq"))
    else:
        need.append(("See it / try it or Links", r"try it|see it|links"))
    for label, pat in need:
        if not re.search(pat, joined):
            E(slug, f"missing required section: {label}")


def main():
    projects = load_projects()
    if not projects:
        print("no projects found under projects/*/index.md")
        return 0
    slugs = set()
    for p in projects:
        m, slug, body = p["meta"], p["slug"], p["body"]
        if slug in slugs:
            E(slug, "duplicate slug")
        slugs.add(slug)

        # slug == folder
        if m.get("slug") != slug:
            E(slug, f"frontmatter slug '{m.get('slug')}' != folder name '{slug}'")

        # keys
        keys = set(m.keys())
        missing = REQUIRED_KEYS - keys
        if missing:
            E(slug, f"missing required keys: {sorted(missing)}")
        unknown = keys - REQUIRED_KEYS - OPTIONAL_KEYS
        if unknown:
            E(slug, f"unknown keys: {sorted(unknown)}")

        # enums
        if m.get("type") not in TYPES: E(slug, f"bad type: {m.get('type')}")
        if m.get("org") not in ORGS: E(slug, f"bad org: {m.get('org')}")
        if m.get("engagement") not in ENGAGEMENTS: E(slug, f"bad engagement: {m.get('engagement')}")
        if m.get("status") not in STATUSES: E(slug, f"bad status: {m.get('status')}")
        conf = m.get("confidentiality")
        if conf not in TIERS: E(slug, f"bad confidentiality: {conf}")

        # vocab
        for d in (m.get("domain") or []):
            if d not in DOMAINS: E(slug, f"unknown domain '{d}'")
        for s in (m.get("stack") or []):
            if s not in STACK: W(slug, f"stack '{s}' not in vocab (add to _schema.md/_common.py)")
        if not (1 <= len(m.get("domain") or []) <= 3): E(slug, "domain must have 1–3 values")
        if not (2 <= len(m.get("highlights") or []) <= 4): E(slug, "highlights must have 2–4 items")
        if len(m.get("summary") or "") > 240: E(slug, "summary exceeds 240 chars")

        # RU fields (optional, but README renders bilingual EN/RU — nudge to keep in sync)
        for k in ("title_ru", "role_ru", "summary_ru"):
            if not (m.get(k) or "").strip():
                W(slug, f"missing {k} — README will show 'перевод в работе'")
        hl, hl_ru = m.get("highlights") or [], m.get("highlights_ru") or []
        if not hl_ru:
            W(slug, "missing highlights_ru — README will show 'перевод в работе'")
        elif len(hl_ru) != len(hl):
            E(slug, f"highlights_ru has {len(hl_ru)} items, highlights has {len(hl)} — must match")

        # metrics kind
        for mt in (m.get("metrics") or []):
            if mt.get("kind") not in {"target", "measured"}:
                E(slug, f"metric '{mt.get('label')}' has bad kind: {mt.get('kind')}")

        # confidentiality rules
        links = m.get("links") or {}
        has_link = any((links.get(k) or "").strip() for k in ("repo", "demo", "site", "docs"))
        if conf == "anonymized":
            if has_link: E(slug, "anonymized project must have empty links")
            if (m.get("client") or "").strip(): E(slug, "anonymized project must not name a client")
            if not re.search(r"under NDA", body, re.I): W(slug, "NDA footer not found")
            assets = p["path"].parent / "assets"
            if assets.is_dir():
                for f in assets.iterdir():
                    if f.suffix.lower() in {".png", ".jpg", ".jpeg", ".gif"} and "-scrubbed" not in f.stem:
                        E(slug, f"anonymized project has non-scrubbed screenshot: {f.name}")
        # public: links optional (source repos may be private) — allowed but not required.

        check_sections(slug, body, m.get("type"))

        # stack appears in a Stack/Technology section (loose check)
        low = body.lower()
        for s in (m.get("stack") or []):
            token = s.split("-")[0]
            if token not in low:
                W(slug, f"stack '{s}' not mentioned in body")

    for w in warnings: print("WARN ", w)
    for e in errors: print("ERROR", e)
    print(f"\n{len(projects)} project(s) · {len(errors)} error(s) · {len(warnings)} warning(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
