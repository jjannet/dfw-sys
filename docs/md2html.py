#!/usr/bin/env python3
"""Convert docs/*.md to standalone styled HTML. Usage: md2html.py FILE.md [FILE2.md ...]"""
import sys
import pathlib
import re
import markdown

CSS = """
:root { --ink:#1a1f2b; --muted:#5b6477; --line:#e3e7ef; --accent:#2563eb; --bg:#f7f8fb; --card:#ffffff; }
* { box-sizing:border-box; }
body { margin:0; background:var(--bg); color:var(--ink);
  font-family:'Segoe UI','SF Pro Text','Noto Sans Thai',Sarabun,Tahoma,sans-serif;
  line-height:1.7; font-size:16px; }
main { max-width:920px; margin:0 auto; padding:48px 32px 96px; }
h1 { font-size:1.9em; border-bottom:3px solid var(--accent); padding-bottom:.4em; margin-top:0; }
h2 { font-size:1.45em; margin-top:2.2em; border-bottom:1px solid var(--line); padding-bottom:.3em; }
h3 { font-size:1.15em; margin-top:1.8em; color:#1e3a8a; }
a { color:var(--accent); text-decoration:none; } a:hover { text-decoration:underline; }
blockquote { margin:1em 0; padding:.6em 1em; border-left:4px solid var(--accent);
  background:#eef3fe; color:var(--muted); border-radius:0 8px 8px 0; }
blockquote p { margin:.2em 0; }
code { font-family:'Cascadia Code',Menlo,Consolas,monospace; font-size:.88em;
  background:#edf0f6; padding:.12em .4em; border-radius:4px; }
pre { background:#0f172a; color:#dbe4f3; padding:18px 20px; border-radius:10px;
  overflow-x:auto; line-height:1.45; }
pre code { background:none; color:inherit; padding:0; font-size:.85em; }
table { border-collapse:collapse; width:100%; margin:1.2em 0; background:var(--card);
  border-radius:8px; overflow:hidden; box-shadow:0 1px 3px rgba(15,23,42,.08); }
th { background:#1e3a8a; color:#fff; text-align:left; padding:10px 14px; font-weight:600; }
td { padding:9px 14px; border-top:1px solid var(--line); vertical-align:top; }
tr:nth-child(even) td { background:#fafbfe; }
ul,ol { padding-left:1.5em; }
li { margin:.25em 0; }
hr { border:none; border-top:1px solid var(--line); margin:2.5em 0; }
.meta { color:var(--muted); font-size:.85em; margin-bottom:2em; }
@media print { body { background:#fff; } main { padding:0; max-width:none; } }
"""

TEMPLATE = """<!DOCTYPE html>
<html lang="th">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>{css}</style>
</head>
<body>
<main>
{body}
</main>
</body>
</html>
"""


def convert(path: pathlib.Path) -> pathlib.Path:
    text = path.read_text(encoding="utf-8")
    title_match = re.search(r"^#\s+(.+)$", text, re.MULTILINE)
    title = title_match.group(1).strip() if title_match else path.stem
    body = markdown.markdown(text, extensions=["tables", "fenced_code", "toc", "sane_lists"])
    # .md links -> .html so cross-references keep working in the HTML versions
    body = body.replace('.md"', '.html"')
    out = path.with_suffix(".html")
    out.write_text(TEMPLATE.format(title=title, css=CSS, body=body), encoding="utf-8")
    return out


if __name__ == "__main__":
    for arg in sys.argv[1:]:
        print(convert(pathlib.Path(arg)))
