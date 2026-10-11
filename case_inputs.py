"""Final-case inputs: a folder of bank documents (Markdown, Word, PDF, Excel, text) and the team's mock URL.

`prepare(folder, mock_url, slot)` converts every non-text document to Markdown/text next to the originals
(`<folder>/_text/`), orders the documents (BRIEF.md, then README.md, then the rest by name), fetches the tool API
from `<mock_url>/openapi.json` and pins its server URL to the mock. Nothing here knows anything about the case.
"""
from __future__ import annotations

import json
import pathlib
import re
import urllib.request

TEXT_SUFFIXES = {".md", ".txt", ".markdown", ".csv", ".json", ".yaml", ".yml"}
SKIP_NAMES = {"openapi.json", "openapi.yaml", "openapi.yml"}


def _docx_to_md(path: pathlib.Path) -> str:
    import docx
    d = docx.Document(str(path))
    out = []
    for block in d.element.body.iterchildren():
        tag = block.tag.rsplit("}", 1)[-1]
        if tag == "p":
            p = docx.text.paragraph.Paragraph(block, d)
            t = p.text.strip()
            if not t:
                continue
            style = (p.style.name or "").lower() if p.style is not None else ""
            if style.startswith("heading"):
                level = "".join(ch for ch in style if ch.isdigit()) or "2"
                out.append("#" * min(6, int(level)) + " " + t)
            elif style.startswith("list"):
                out.append("- " + t)
            else:
                out.append(t)
        elif tag == "tbl":
            tbl = docx.table.Table(block, d)
            rows = [[c.text.strip().replace("\n", " ") for c in r.cells] for r in tbl.rows]
            if rows:
                out.append("| " + " | ".join(rows[0]) + " |")
                out.append("|" + "---|" * len(rows[0]))
                for r in rows[1:]:
                    out.append("| " + " | ".join(r) + " |")
        out.append("")
    return "\n".join(out).strip() + "\n"


def _xlsx_to_md(path: pathlib.Path) -> str:
    import openpyxl
    wb = openpyxl.load_workbook(str(path), data_only=True, read_only=True)
    out = []
    for ws in wb.worksheets:
        out.append(f"## Sheet: {ws.title}")
        rows = [[("" if v is None else str(v)).strip() for v in r] for r in ws.iter_rows(values_only=True)]
        rows = [r for r in rows if any(r)]
        if not rows:
            out.append("(empty)\n")
            continue
        width = max(len(r) for r in rows)
        rows = [r + [""] * (width - len(r)) for r in rows]
        out.append("| " + " | ".join(rows[0]) + " |")
        out.append("|" + "---|" * width)
        for r in rows[1:]:
            out.append("| " + " | ".join(r) + " |")
        out.append("")
    return "\n".join(out).strip() + "\n"


def _pdf_to_text(path: pathlib.Path) -> str:
    import pypdf
    r = pypdf.PdfReader(str(path))
    pages = []
    for i, page in enumerate(r.pages):
        t = page.extract_text() or ""
        pages.append(f"<!-- page {i + 1} -->\n{t.strip()}")
    return "\n\n".join(pages).strip() + "\n"


def convert(path: pathlib.Path, dest_dir: pathlib.Path) -> pathlib.Path | None:
    """A readable copy of a document, or None when the file is not a document (images, archives, the API file)."""
    suf = path.suffix.lower()
    if path.name.lower() in SKIP_NAMES:
        return None
    if suf in TEXT_SUFFIXES:
        return path
    dest_dir.mkdir(parents=True, exist_ok=True)
    if suf == ".docx":
        text = _docx_to_md(path); target = dest_dir / (path.stem + ".docx.md")
    elif suf in (".xlsx", ".xlsm"):
        text = _xlsx_to_md(path); target = dest_dir / (path.stem + ".xlsx.md")
    elif suf == ".pdf":
        text = _pdf_to_text(path); target = dest_dir / (path.stem + ".pdf.txt")
    elif suf in (".doc", ".xls", ".ppt", ".pptx", ".rtf", ".odt"):
        return None    # legacy binary formats: left to the operator to convert (the trace lists them as skipped)
    else:
        return None
    target.write_text(text, encoding="utf-8")
    return target


def order_key(p: pathlib.Path):
    n = p.name.lower()
    return (0 if n.startswith("brief") else 1 if n.startswith("readme") else 2, str(p).lower())


def prepare(folder: str, mock_url: str, workspace: pathlib.Path) -> dict:
    """Returns {"briefs": [relative paths], "openapi": relative path, "skipped": [...], "mock_url": ...}."""
    root = pathlib.Path(folder)
    if not root.is_dir():
        raise SystemExit(f"case folder not found: {folder}")
    dest = root / "_text"
    briefs, skipped = [], []
    for p in sorted(root.rglob("*"), key=order_key):
        if not p.is_file() or p.name.startswith(".") or dest in p.parents or p.name.lower() in SKIP_NAMES:
            continue
        try:
            c = convert(p, dest)
        except Exception as e:                      # one unreadable document never stops the build
            skipped.append(f"{p}: {e!r}"[:200]); continue
        if c is None:
            skipped.append(str(p)); continue
        briefs.append(c)
    briefs.sort(key=order_key)
    mock = mock_url.rstrip("/")
    if not re.match(r"^https?://", mock):
        raise SystemExit("mock_url must start with http:// or https://")
    req = urllib.request.Request(mock + "/openapi.json", headers={"User-Agent": "build-the-builder/1.0", "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        spec = json.loads(r.read().decode("utf-8"))
    if not isinstance(spec, dict) or "paths" not in spec:
        raise SystemExit("the mock's /openapi.json is not an OpenAPI document (no 'paths')")
    spec["servers"] = [{"url": mock}]                # the phone agent calls the mock, whatever the document says
    dest.mkdir(parents=True, exist_ok=True)
    api_path = dest / "openapi.json"
    api_path.write_text(json.dumps(spec, indent=1, ensure_ascii=False), encoding="utf-8")
    def rel(p: pathlib.Path) -> str:
        try:
            return str(p.resolve().relative_to(pathlib.Path(workspace).resolve()))
        except ValueError:
            return str(p.resolve())                      # a folder outside the repo: absolute paths work for the extractor too
    return {"briefs": [rel(p) for p in briefs], "openapi": rel(api_path), "skipped": skipped, "mock_url": mock}
