#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Dump a requirements PPTX into a Markdown digest the design-doc author can cite.

Usage:
  python3 read_pptx.py <file.pptx> [-o OUT_DIR] [--render]

Output (OUT_DIR, default ./ppt_dump/<pptx stem>/):
  slides.md        per slide: title, every text box (groups recursed, sorted top->bottom,
                   left->right), tables as Markdown, speaker notes, picture list,
                   embedded OLE objects (e.g. Excel), annotation markers ①②③.
  media/sN_k.ext   pictures extracted from each slide (LOOK at them: UI mockups live here)
  embedded/        embedded files (xlsx/docx/bin) found in ppt/embeddings
  render/slide-N.png  (with --render) full-slide PNGs via LibreOffice -> PDF -> pdftoppm
Cite as "slide N 注釈②" in the design doc.
"""
import argparse, os, re, shutil, subprocess, zipfile
from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE

MARKS = re.compile(r"\s*[①-⑳]\s*")


def iter_shapes(shapes, depth=0):
    for sh in shapes:
        yield sh, depth
        if sh.shape_type == MSO_SHAPE_TYPE.GROUP:
            yield from iter_shapes(sh.shapes, depth + 1)


def pos(sh):
    try:
        return (int(sh.top or 0), int(sh.left or 0))
    except Exception:
        return (0, 0)


def table_md(tbl):
    rows = [[c.text.replace("\n", "<br>").replace("|", "\\|").strip() for c in r.cells] for r in tbl.rows]
    if not rows:
        return ""
    n = max(len(r) for r in rows)
    rows = [r + [""] * (n - len(r)) for r in rows]
    out = ["| " + " | ".join(rows[0]) + " |", "|" + "---|" * n]
    out += ["| " + " | ".join(r) + " |" for r in rows[1:]]
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pptx")
    ap.add_argument("-o", "--out")
    ap.add_argument("--render", action="store_true", help="also render slides to PNG via LibreOffice")
    a = ap.parse_args()
    stem = os.path.splitext(os.path.basename(a.pptx))[0]
    out = a.out or os.path.join("ppt_dump", stem)
    os.makedirs(os.path.join(out, "media"), exist_ok=True)
    prs = Presentation(a.pptx)
    md = [f"# {os.path.basename(a.pptx)}", f"slides: {len(prs.slides)}", ""]
    for i, s in enumerate(prs.slides, 1):
        md.append(f"## slide {i}")
        title = ""
        try:
            if s.shapes.title is not None and s.shapes.title.has_text_frame:
                title = s.shapes.title.text.strip()
        except Exception:
            pass
        if title:
            md.append(f"**title**: {title}")
        items, pic_n = [], 0
        for sh, d in iter_shapes(s.shapes):
            st = sh.shape_type
            if st == MSO_SHAPE_TYPE.PICTURE:
                try:
                    img = sh.image
                    pic_n += 1
                    fn = f"s{i}_{pic_n}.{img.ext}"
                    with open(os.path.join(out, "media", fn), "wb") as f:
                        f.write(img.blob)
                    items.append((pos(sh), f"- [picture] media/{fn} ({sh.name})"))
                except Exception:
                    items.append((pos(sh), f"- [picture] ({sh.name}, not extractable)"))
            elif st == MSO_SHAPE_TYPE.EMBEDDED_OLE_OBJECT:
                prog = ""
                try:
                    prog = sh.ole_format.prog_id
                except Exception:
                    pass
                items.append((pos(sh), f"- [OLE] {prog} ({sh.name}) -> see embedded/"))
            if getattr(sh, "has_table", False) and sh.has_table:
                items.append((pos(sh), "\n[table]\n" + table_md(sh.table) + "\n"))
            elif getattr(sh, "has_text_frame", False) and sh.has_text_frame:
                t = sh.text_frame.text.strip()
                if t and t != title:
                    t2 = t.replace("\v", "\n").replace("\n", " / ")
                    tag = " [注釈マーカー]" if MARKS.fullmatch(t) else ""
                    items.append((pos(sh), f"- {'  ' * d}{t2}{tag}"))
        for _, line in sorted(items, key=lambda x: x[0]):
            md.append(line)
        if s.has_notes_slide:
            n = s.notes_slide.notes_text_frame.text.strip()
            if n:
                md.append("**notes**: " + n.replace("\n", " / "))
        md.append("")
    with zipfile.ZipFile(a.pptx) as z:
        emb = [n for n in z.namelist() if n.startswith("ppt/embeddings/")]
        if emb:
            os.makedirs(os.path.join(out, "embedded"), exist_ok=True)
            md.append("## embedded files")
            for n in emb:
                dst = os.path.join(out, "embedded", os.path.basename(n))
                with open(dst, "wb") as f:
                    f.write(z.read(n))
                md.append(f"- embedded/{os.path.basename(n)}")
    with open(os.path.join(out, "slides.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(md))
    if a.render:
        rd = os.path.join(out, "render")
        os.makedirs(rd, exist_ok=True)
        subprocess.run(["soffice", "--headless", "--convert-to", "pdf", "--outdir", rd, a.pptx],
                       check=False, capture_output=True)
        pdfs = [p for p in os.listdir(rd) if p.endswith(".pdf")]
        if pdfs and shutil.which("pdftoppm"):
            subprocess.run(["pdftoppm", "-png", "-r", "80", os.path.join(rd, pdfs[0]),
                            os.path.join(rd, "slide")], check=False)
    print(os.path.join(out, "slides.md"))


if __name__ == "__main__":
    main()
