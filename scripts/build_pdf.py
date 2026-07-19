#!/usr/bin/env python3
"""Render a project index.md (or any .md) to a styled PDF with rendered mermaid diagrams.

  python3 scripts/build_pdf.py projects/<slug>/index.md dist/pdf/<slug>.pdf
  python3 scripts/build_pdf.py --all          # build every project into dist/pdf/

Pipeline: pandoc -> HTML (styled) -> Chrome headless --print-to-pdf. mermaid.js is cached in
dist/.cache (gitignored); downloaded once if absent."""
import sys, subprocess, re, html, tempfile, os, pathlib, urllib.request, base64, yaml, shutil

ROOT = pathlib.Path(__file__).resolve().parent.parent
CACHE = ROOT / "dist" / ".cache"
VENDOR_JS = ROOT / "scripts" / "vendor" / "mermaid.min.js"   # committed, offline-reproducible
VENDOR_LOGO = ROOT / "scripts" / "vendor" / "asrp-logo.svg"  # committed, from asrp.brand
MERMAID_JS = CACHE / "mermaid.min.js"
MERMAID_URL = "https://cdn.jsdelivr.net/npm/mermaid@10.9.1/dist/mermaid.min.js"
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

# ASRP brand primary (asrp.brand tokens/colors.json: brand.primary.default, oklch(0.655 0.215 265))
BRAND_ACCENT = "#7B6AE0"

# Letterhead entities, keyed by meta.yaml's `org` field. Two ASRP legal entities are used
# depending on which org delivered the project (see asrp.investor-package/00-overview for
# the source facts).
LETTERHEADS = {
    "asrp": {
        "name": "Advanced Scientific Research Projects LLP",
        "detail": "ТОО «Перспективные Научно-Исследовательские Разработки» · BIN 240140033296",
        "line3": "Republic of Kazakhstan",
    },
    "osnova": {
        "name": "Advanced Scientific Research Projects LLC",
        "detail": "7901 4th St N, Ste 300, St. Petersburg, FL 33702, USA",
        "line3": "Florida Doc. No. L17000209665",
    },
}

CSS = """
:root { --fg:#1a1a1a; --muted:#555; --accent:__ACCENT__; --line:#e2e2e2; --code-bg:#f6f8fa; }
* { box-sizing:border-box; }
body { font-family:'Inter',-apple-system,'Segoe UI',Helvetica,Arial,sans-serif; color:var(--fg); font-size:10.5pt; line-height:1.5; margin:0; }
.letterhead { display:flex; align-items:center; gap:12pt; margin-bottom:10pt; }
.letterhead img { width:42pt; height:auto; flex:none; }
.letterhead-name { font-weight:700; font-size:12.5pt; }
.letterhead-detail { font-size:8pt; color:var(--muted); }
.letterhead-rule { border:none; border-top:1.5pt solid var(--fg); margin:0 0 16pt; }
h1 { font-size:22pt; margin:0 0 4pt; letter-spacing:-.3pt; }
h1 + p { color:var(--muted); font-size:10pt; }
h2 { font-size:14pt; margin:20pt 0 6pt; padding-bottom:3pt; border-bottom:2px solid var(--accent); page-break-after:avoid; }
h3 { font-size:11.5pt; margin:12pt 0 4pt; page-break-after:avoid; }
p,li { orphans:3; widows:3; }
a { color:var(--accent); text-decoration:none; }
strong { font-weight:650; }
code { font-family:'SF Mono',Menlo,Consolas,monospace; font-size:9pt; background:var(--code-bg); padding:1px 4px; border-radius:3px; }
pre { background:var(--code-bg); padding:10pt; border-radius:6px; overflow:auto; font-size:8.5pt; border:1px solid var(--line); page-break-inside:avoid; }
pre code { background:none; padding:0; }
pre.mermaid { background:none; border:none; text-align:center; padding:6pt 0; }
pre.mermaid svg { max-width:100%; height:auto; }
table { border-collapse:collapse; width:100%; margin:8pt 0; font-size:9pt; page-break-inside:avoid; }
th,td { border:1px solid var(--line); padding:5pt 8pt; text-align:left; vertical-align:top; }
th { background:var(--code-bg); font-weight:650; }
tr:nth-child(even) td { background:#fafbfc; }
blockquote { margin:8pt 0; padding:6pt 12pt; border-left:3px solid var(--accent); background:var(--code-bg); color:var(--muted); font-size:9.5pt; }
hr { border:none; border-top:1px solid var(--line); margin:16pt 0; }
@page { size:A4; margin:16mm 15mm; }
""".replace("__ACCENT__", BRAND_ACCENT)

LETTERHEAD_TMPL = """<div class="letterhead">
<img src="data:image/svg+xml;base64,{logo_b64}" alt="ASRP">
<div>
<div class="letterhead-name">{name}</div>
<div class="letterhead-detail">{detail}</div>
<div class="letterhead-detail">{line3} &middot; <a href="https://asrp.tech">asrp.tech</a></div>
</div>
</div>
<hr class="letterhead-rule">
"""

HTML_TMPL = """<!doctype html><html><head><meta charset="utf-8"><style>{css}</style></head><body>
{letterhead}{body}
<script>{mermaid}</script>
<script>
mermaid.initialize({{startOnLoad:false, theme:'neutral', flowchart:{{useMaxWidth:true}}, sequence:{{useMaxWidth:true}}, themeVariables:{{fontSize:'13px'}}}});
mermaid.run({{querySelector:'pre.mermaid'}}).catch(e=>console.error(e));
</script></body></html>"""


def letterhead_html(org):
    entity = LETTERHEADS.get(org)
    if not entity:
        return ""
    logo_b64 = base64.b64encode(VENDOR_LOGO.read_bytes()).decode()
    return LETTERHEAD_TMPL.format(logo_b64=logo_b64, **entity)


def ensure_mermaid():
    if VENDOR_JS.exists():
        return VENDOR_JS.read_text()
    if not MERMAID_JS.exists():
        CACHE.mkdir(parents=True, exist_ok=True)
        print("downloading mermaid.min.js (one-time)...")
        urllib.request.urlretrieve(MERMAID_URL, MERMAID_JS)
    return MERMAID_JS.read_text()


def fix_mermaid(body):
    return re.sub(r'<pre class="mermaid"><code>(.*?)</code></pre>',
                  lambda m: '<pre class="mermaid">' + html.unescape(m.group(1)) + '</pre>',
                  body, flags=re.S)


def convert(md_path, pdf_path, org=None):
    md_path, pdf_path = pathlib.Path(md_path), pathlib.Path(pdf_path)
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    if org is None:
        meta_path = md_path.parent / "meta.yaml"
        if meta_path.exists():
            org = (yaml.safe_load(meta_path.read_text()) or {}).get("org")
    body = subprocess.run(["pandoc", str(md_path), "-f", "markdown", "-t", "html", "--wrap=none"],
                          capture_output=True, text=True, check=True).stdout
    doc = HTML_TMPL.format(css=CSS, letterhead=letterhead_html(org), body=fix_mermaid(body),
                            mermaid=ensure_mermaid())
    with tempfile.NamedTemporaryFile("w", suffix=".html", dir=CACHE, delete=False) as f:
        f.write(doc); html_path = f.name
    subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
                    "--run-all-compositor-stages-before-draw", "--virtual-time-budget=20000",
                    f"--print-to-pdf={pdf_path}", f"file://{html_path}"],
                   capture_output=True, check=True)
    os.unlink(html_path)
    normalize_pdf(pdf_path)
    print(f"OK  {pdf_path}  ({os.path.getsize(pdf_path)} bytes)")


def normalize_pdf(pdf_path):
    """Re-write via Ghostscript (pdfwrite). Chrome's headless print-to-pdf (Producer:
    Skia/PDF) emits per-page subsetted CID TrueType fonts that GitHub's pdf.js viewer
    frequently fails to render ("Error rendering embedded code") even though the file
    opens fine in Preview/Acrobat/poppler. Ghostscript re-encodes fonts/objects into a
    form pdf.js handles; visual output and text content are unaffected."""
    gs = shutil.which("gs")
    if not gs:
        print(f"WARN  ghostscript not found — skipping PDF normalization for {pdf_path} "
              f"(file may fail to render in GitHub's PDF viewer)")
        return
    tmp = pdf_path.with_suffix(".gs.pdf")
    subprocess.run([gs, "-dCompatibilityLevel=1.4", "-dPDFSETTINGS=/prepress",
                    "-dNOPAUSE", "-dBATCH", "-dQUIET", "-sDEVICE=pdfwrite",
                    f"-o{tmp}", str(pdf_path)], capture_output=True, check=True)
    tmp.replace(pdf_path)


def main():
    CACHE.mkdir(parents=True, exist_ok=True)
    if "--all" in sys.argv:
        for idx in sorted((ROOT / "projects").glob("*/index.md")):
            convert(idx, ROOT / "dist" / "pdf" / f"{idx.parent.name}.pdf")
    else:
        convert(sys.argv[1], sys.argv[2])


if __name__ == "__main__":
    main()
