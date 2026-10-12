#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""単体テスト項目テンプレート xlsx から個人・組織・環境情報を除去する（OOXML 最小修改）。

  python3 clean_template.py 元.xlsx -o 出力.xlsx

除去するもの:
  * docProps/core.xml の作成者/最終更新者などを空に、作成・更新日時を固定値に
  * docProps/app.xml の Company / Manager / HyperlinkBase を空に
  * docProps/custom.xml（編集ソフトのビルド番号・SharePoint の ContentTypeId など）
  * customXml/*（SharePoint のドキュメントライブラリ情報・テナント GUID）
  * docMetadata/LabelInfo.xml（秘密度ラベルとテナント ID）
  * [trash]/*（どこからも参照されていない残骸）
  * workbook.xml の customWorkbookViews（個人名入りの「個人用ビュー」）と revisionPtr
  * 各 sheet の customSheetViews（上記個人用ビューの sheet 側）、pageSetup の r:id
  * xl/printerSettings/*.bin（社内プリンタ名・IP・サーバー名）と参照 rels
  * styles.xml の独自セルスタイル名（他案件の文書名・社名等が残っている）→ UserStyle_NNNN に置換
    （組み込みスタイル 標準/ハイパーリンク/パーセント は残す。セル書式・xf 番号は変わらない）
sheet の内容・順序・隠し状態・数式・書式・入力規則（下拉）は変更しない。
"""
from __future__ import annotations

import argparse
import re
import zipfile
from pathlib import Path

FIXED_DT = "2026-01-01T00:00:00Z"


def clean(files: dict) -> dict:
    out = {}
    drop = re.compile(r"^(docProps/custom\.xml|customXml/.*|docMetadata/.*|\[trash\]/.*|xl/printerSettings/.*)$")
    for n, data in files.items():
        if drop.match(n):
            continue
        out[n] = data

    def sub(name, pat, rep, flags=re.S):
        if name in out:
            out[name] = re.sub(pat, rep, out[name].decode("utf-8"), flags=flags).encode("utf-8")

    # core / app
    for tag in ("dc:creator", "cp:lastModifiedBy", "dc:title", "dc:subject", "cp:keywords", "dc:description",
                "cp:category", "cp:contentStatus", "cp:revision"):
        sub("docProps/core.xml", rf"<{tag}>.*?</{tag}>|<{tag}/>", f"<{tag}></{tag}>")
    sub("docProps/core.xml", r"(<dcterms:(?:created|modified)\b[^>]*>)[^<]*(</dcterms:)", rf"\g<1>{FIXED_DT}\g<2>")
    sub("docProps/core.xml", r"<cp:lastPrinted>.*?</cp:lastPrinted>", "")
    for tag in ("Company", "Manager", "HyperlinkBase"):
        sub("docProps/app.xml", rf"<{tag}>.*?</{tag}>", f"<{tag}></{tag}>")
    # rels / content types
    sub("_rels/.rels", r'<Relationship\b[^>]*Target="(?:docProps/custom\.xml|docMetadata/[^"]*)"[^>]*/>', "")
    sub("xl/_rels/workbook.xml.rels", r'<Relationship\b[^>]*Target="\.\./customXml/[^"]*"[^>]*/>', "")
    sub("[Content_Types].xml", r'<Override\b[^>]*PartName="/(?:customXml/|docMetadata/|docProps/custom\.xml)[^"]*"[^>]*/>', "")
    sub("[Content_Types].xml", r'<Default\b[^>]*Extension="bin"[^>]*/>', "")
    # styles: 他案件の文書名・社名・プリンタ名が入った独自セルスタイル名を連番に置換（書式・番号は不変）
    if "xl/styles.xml" in out:
        st = out["xl/styles.xml"].decode("utf-8")
        cnt = [0]

        def ren(m):
            tag = m.group(0)
            if "builtinId=" in tag:
                return tag
            cnt[0] += 1
            return re.sub(r'\bname="[^"]*"', f'name="UserStyle_{cnt[0]:04d}"', tag, count=1)
        out["xl/styles.xml"] = re.sub(r"<cellStyle\b[^>]*/>", ren, st).encode("utf-8")
    # workbook personal views
    sub("xl/workbook.xml", r"<customWorkbookViews>.*?</customWorkbookViews>", "")
    sub("xl/workbook.xml", r"<xr:revisionPtr\b[^>]*/>", "")
    # sheets
    for n in list(out):
        if re.match(r"xl/worksheets/sheet\d+\.xml$", n):
            sub(n, r"<customSheetViews>.*?</customSheetViews>", "")
            sub(n, r'(<pageSetup\b[^>]*?)\s+r:id="[^"]*"', r"\1")
        if re.match(r"xl/worksheets/_rels/sheet\d+\.xml\.rels$", n):
            sub(n, r'<Relationship\b[^>]*Target="\.\./printerSettings/[^"]*"[^>]*/>', "")
            if b"<Relationship " not in out[n]:
                del out[n]
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("src")
    ap.add_argument("-o", "--out", required=True)
    a = ap.parse_args()
    with zipfile.ZipFile(a.src) as z:
        names = z.namelist()
        files = {n: z.read(n) for n in names}
    cleaned = clean(files)
    with zipfile.ZipFile(a.out, "w", zipfile.ZIP_DEFLATED) as zo:
        for n in names:  # 元の順序を保つ（[Content_Types].xml が先頭）
            if n in cleaned:
                zo.writestr(zipfile.ZipInfo(n, date_time=(2026, 1, 1, 0, 0, 0)), cleaned[n], zipfile.ZIP_DEFLATED)
    removed = sorted(set(names) - set(cleaned))
    print(f"written: {a.out}  removed parts: {len(removed)}")
    for r in removed:
        print("  -", r)


if __name__ == "__main__":
    main()
