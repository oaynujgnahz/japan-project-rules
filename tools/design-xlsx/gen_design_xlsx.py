#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""詳細設計書 (Japanese-style Excel) generator（项目共用；系统名等取自 design.json 的 meta / 项目配置）.

  python3 gen_design_xlsx.py design.json -o out.xlsx          # build
  python3 gen_design_xlsx.py --blank -o 設計書_テンプレート.xlsx  # empty template (all sheets, headers only)
  python3 gen_design_xlsx.py --schema                           # print the JSON skeleton

Input: JSON (or YAML if PyYAML is installed). Every table section accepts rows as
lists (column order = headers) or dicts keyed by the header text (missing keys -> blank).
Strings may contain "\n" (rendered as line breaks). A list value inside a cell is joined
with "\n" (numbered "1. ..." for 処理 columns).

Style follows the company-style 詳細設計書 layout:
Yu Gothic, header fill 4472C4 + white bold, section band D9E1F2, thin borders, wrap/top.
Adds the usual 日式 sheet header band (システム名/機能名/文書番号/版数/作成日/作成者/シート名).
"""
from __future__ import annotations

import argparse, json, math, os, re, sys, unicodedata
from datetime import date

import openpyxl
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.page import PageMargins
from openpyxl.worksheet.hyperlink import Hyperlink

FONT = "Yu Gothic"
HEADER_FILL = PatternFill("solid", start_color="4472C4", end_color="4472C4")
HEADER_FONT = Font(name=FONT, size=10, bold=True, color="FFFFFF")
SECTION_FILL = PatternFill("solid", start_color="D9E1F2", end_color="D9E1F2")
SECTION_FONT = Font(name=FONT, size=11, bold=True)
BAND_LABEL_FILL = PatternFill("solid", start_color="DDEBF7", end_color="DDEBF7")
KEY_FILL = PatternFill("solid", start_color="F2F2F2", end_color="F2F2F2")
BODY_FONT = Font(name=FONT, size=10)
BOLD_FONT = Font(name=FONT, size=10, bold=True)
TITLE_FONT = Font(name=FONT, size=18, bold=True)
LINK_FONT = Font(name=FONT, size=10, color="0563C1", underline="single")
THIN = Side(style="thin", color="808080")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
WRAP = Alignment(horizontal="left", vertical="top", wrap_text=True)
CENTER = Alignment(horizontal="center", vertical="center", wrap_text=True)
STATUS_FILLS = {
    "✅": "E2EFDA", "done": "E2EFDA", "済": "E2EFDA", "回答済": "E2EFDA",
    "⏳": "FFF2CC", "wip": "FFF2CC", "todo": "FFF2CC", "未回答": "FFF2CC", "TBD": "FFF2CC",
    "△": "FCE4D6", "❌": "F8CBAD", "NG": "F8CBAD",
}
NCOLS_BAND = 8

# --------------------------------------------------------------------------------------
# Sheet catalog: (key, sheet name, required, sections)
# section = (json key, title, [(header, width), ...])
# --------------------------------------------------------------------------------------
C = lambda *pairs: list(pairs)  # noqa: E731

OVERVIEW = [
    ("summary", "1. 要件概要", C(("No", 6), ("変更内容／機能", 34), ("目的・効果", 40), ("要件来源（PPT）", 18))),
    ("out_of_scope", "2. 対象外", C(("項目", 34), ("理由", 60))),
    ("principles", "3. 実現方針", C(("方針", 22), ("説明", 72))),
    ("permissions", "4. 権限", C(("操作", 22), ("権限定数／チェック", 50), ("備考", 30))),
    ("structure", "5. システム構成（層・コンポーネント）", C(("層", 18), ("コンポーネント（業務名）", 40), ("役割", 40))),
]
CURRENT = [
    ("tables", "1. 主キーとテーブル", C(("テーブル", 34), ("主キー", 18), ("業務キー／一意制約", 40))),
    ("backend", "2. バックエンド入口", C(("層", 16), ("クラス／パス", 60), ("備考", 30))),
    ("frontend", "3. フロントエンド入口", C(("区分", 16), ("パス", 60), ("備考", 30))),
    ("logic_points", "4. 既存ロジック要点", C(("項目", 22), ("説明", 72))),
    ("similar", "5. 類似機能参照", C(("参照", 22), ("パス", 50), ("流用ポイント", 40))),
    ("risks", "6. リスク", C(("No", 6), ("リスク内容", 70), ("対応", 30))),
    ("scope", "7. 今回変更範囲", C(("区分", 22), ("有無", 8), ("内容", 60))),
]
FLOW_COLS = C(("No", 7), ("シナリオ", 18), ("目的", 24), ("トリガー", 22), ("入力", 22),
              ("処理", 50), ("出力", 26), ("境界・例外", 30), ("関連（BR/AC/API/Slide）", 20))
SCREEN_SECTIONS = [
    ("overview", "1. 画面概要", C(("項目", 18), ("内容", 80))),
    ("layout", "2. 画面レイアウト", None),  # text / images
    ("items", "3. 画面項目", C(("項番", 6), ("項目名", 20), ("物理名", 18), ("コンポーネント", 16), ("R/W", 6),
                              ("必須", 6), ("チェック・備考", 40), ("要件来源", 14))),
    ("transitions", "4. 画面遷移", C(("操作", 20), ("遷移先", 26), ("条件", 50))),
    ("events", "5. イベント・操作", C(("操作", 14), ("トリガー", 10), ("API", 44), ("リクエスト要点", 28),
                                    ("成功時", 22), ("失敗時", 20))),
    ("validations", "6. バリデーション", C(("項番", 6), ("ルール", 50), ("タイミング", 14), ("メッセージ（コード／キー）", 40))),
    ("i18n", "7. 文言（i18n）", C(("キー", 40), ("ja", 36), ("en", 36))),
    ("ppt_diff", "8. PPT vs 現状（改修画面は必須）", C(("PPT要素", 18), ("PPT要求", 34), ("現状実装", 30), ("衝突", 6), ("対応方針", 30))),
    ("impl_status", "9. 実装状態サマリ", C(("要件項目", 30), ("PPT", 6), ("設計", 6), ("コード", 6), ("備考", 40))),
    ("details", "10. 実装詳細（目的/トリガー/入力/処理/出力/境界）", FLOW_COLS),
]
API_SECTIONS = [
    ("summary", "1. 処理概要", None),
    ("request", "2. リクエスト", C(("項目（物理名）", 26), ("必須", 6), ("型", 12), ("説明", 60))),
    ("response", "3. レスポンス", C(("項目（物理名）", 26), ("型", 12), ("説明", 66))),
    ("auth", "4. ヘッダ・権限", C(("項目", 18), ("内容", 80))),
    ("logic", "5. ビジネスロジック（BL）", C(("BL-ID", 8), ("ステップ", 18), ("条件", 34), ("処理（業務語）", 50),
                                          ("失敗時", 24))),
    ("db", "6. DB項目", C(("テーブル", 30), ("操作", 12), ("条件／対象項目", 60))),
    ("errors", "7. エラー処理", C(("エラーコード", 14), ("条件", 50), ("画面表現・リカバリ", 40))),
    ("relations", "8. 他API・バッチとの関係", C(("関係", 22), ("説明", 72))),
    ("tests", "9. テスト観点", C(("No", 6), ("シナリオ", 50), ("期待結果", 44))),
    ("details", "10. 実装詳細（目的/トリガー/入力/処理/出力/境界）", FLOW_COLS),
]
TABLE_SECTIONS_COLS = C(("No", 5), ("列名", 26), ("型", 14), ("NULL", 6), ("デフォルト", 12), ("説明", 50), ("変更区分", 10))
INDEX_COLS = C(("名称", 24), ("列", 30), ("説明", 40))

CATALOG = [
    # key,            sheet name,        required, kind
    ("cover",          "表紙",            True,  "cover"),
    ("revisions",      "改訂履歴",        True,  [("revisions", None, C(("版数", 8), ("改訂日", 12), ("改訂箇所", 22), ("改訂内容", 56), ("作成者", 12), ("承認者", 12)))]),
    ("index",          "目次",            True,  "index"),
    ("overview",       "機能概要",        True,  OVERVIEW),
    ("traceability",   "要件対応表",      True,  [("traceability", None, C(("No", 5), ("Slide／注釈", 12), ("要件内容（PPT原文要約）", 40), ("設計対応（シート／ID）", 28), ("既存コード／実装", 30), ("状態", 7), ("備考", 26)))]),
    ("current_state",  "現状分析",        False, CURRENT),
    ("flows",          "処理フロー",      True,  [("flows", None, FLOW_COLS)]),
    ("business_rules", "業務ルール",      True,  [("business_rules", None, C(("規則ID", 8), ("条件", 44), ("結果", 40), ("エラーコード", 14), ("関連フロー／Slide", 18)))]),
    ("screen_list",    "画面一覧",        False, [("screen_list", None, C(("画面ID", 18), ("画面名", 30), ("変更種別", 10), ("要件来源（PPT）", 22), ("実装状態", 10), ("シート", 18)))]),
    ("screens",        None,              False, "screens"),
    ("api_list",       "API一覧",         False, [("api_list", None, C(("API ID", 18), ("名称", 22), ("HTTP", 8), ("Path", 52), ("画面", 18), ("実装状態", 10), ("シート", 14)))]),
    ("apis",           None,              False, "apis"),
    ("tables",         "テーブル定義",    False, "tables"),
    ("checks",         "チェック・エラー一覧", False, [("checks", None, C(("ID", 8), ("チェック内容", 26), ("エラーコード", 13), ("レベル", 8), ("発生条件", 50), ("メッセージ（ja）", 46), ("要件Slide", 9)))]),
    ("sqls",           "SQL一覧",         False, [("sqls", None, C(("SQL-ID", 9), ("名称", 18), ("業務説明", 58), ("テーブル／Mapper", 34), ("使用場面", 12)))]),
    ("acceptance",     "受入基準",        True,  [("acceptance", None, C(("AC-ID", 9), ("受入項目", 30), ("合格条件（テスト可能な形）", 60), ("優先度", 8), ("関連", 16)))]),
    ("questions",      "要確認事項",      True,  [("questions", None, C(("No", 5), ("質問", 40), ("選択肢・備考", 30), ("影響", 14), ("暫定設計方針", 34), ("状態", 8), ("回答", 30), ("回答日", 11), ("担当", 10)))]),
    ("impl_map",       "実装対照",        False, [("impl_map", None, C(("業務節（シート／ID）", 30), ("フロントエンド", 46), ("バックエンド", 46)))]),
]

SCHEMA = {
    "meta": {"system": "（必須）システム名＝項目配置の system_name", "feature": "機能名", "title": "（任意）表紙タイトル",
             "doc_no": "B04-G-xxx-DD", "screen_ids": "SCR-B-xx-xx-xx", "api_ids": "API-B-xx-xx-xx",
             "version": "1.00", "created": "YYYY-MM-DD", "updated": "YYYY-MM-DD", "author": "", "reviewer": "", "approver": "",
             "requirement": "要件定義書_xxx.pptx", "docs_dir": "docs/{機能}/", "related": "—",
             "repo": "<repo> @ <branch/commit>", "status": "作成中 / レビュー待ち / 承認済", "body_lang": "ja|zh"},
    "revisions": [{"版数": "1.00", "改訂日": "YYYY-MM-DD", "改訂箇所": "全体", "改訂内容": "新規作成", "作成者": ""}],
    "overview": {"summary": [], "out_of_scope": [], "principles": [], "permissions": [], "structure": []},
    "traceability": [{"Slide／注釈": "S3 ②", "要件内容（PPT原文要約）": "", "設計対応（シート／ID）": "SCR-xxx §3 / BR-01", "既存コード／実装": "", "状態": "✅|⏳|△|新規"}],
    "current_state": {"tables": [], "backend": [], "frontend": [], "logic_points": [], "similar": [], "risks": [], "scope": []},
    "flows": [{"No": "F-01", "シナリオ": "", "目的": "", "トリガー": "", "入力": "", "処理": ["step1", "step2"], "出力": "", "境界・例外": "", "関連（BR/AC/API/Slide）": ""}],
    "business_rules": [{"規則ID": "BR-01", "条件": "", "結果": "", "エラーコード": "", "関連フロー／Slide": ""}],
    "screens": [{"id": "SCR-B-xx-xx-xx", "name": "画面名", "change_type": "新規|改修", "ppt_source": "xxx.pptx slide n 注釈②", "status": "todo",
                 "sheet": "（任意・31文字以内）", "overview": [["目的", ""], ["入口", ""], ["レイアウト形態", ""], ["権限", ""]],
                 "layout": "ASCII 線框 or 説明", "layout_images": ["/abs/path/slide3.png"],
                 "items": [], "transitions": [], "events": [], "validations": [], "i18n": [], "ppt_diff": [], "impl_status": [], "details": []}],
    "apis": [{"id": "API-B-xx-xx-xx-01", "name": "", "method": "GET", "path": "/api/...", "screens": "SCR-...", "status": "todo",
              "sheet": "（任意）", "basic": [["Controller（業務名）", ""], ["契約", "openapi.yaml"]], "summary": "1～3文", "request": [], "response": [], "auth": [], "logic": [], "db": [],
              "errors": [], "relations": [], "tests": [], "details": []}],
    "tables": [{"name": "dbo.table_name", "description": "", "change": "新規|変更|参照のみ", "columns": [], "indexes": [],
                "entity": "", "mapper": ""}],
    "migrations": [{"スクリプト": "carbonapi/src/main/resources/sql/xxx.sql", "環境": "dev/stg/prd", "説明": ""}],
    "checks": [], "sqls": [], "acceptance": [], "questions": [], "impl_map": [],
    "extra_sheets": [{"name": "シート名", "blocks": [{"type": "table", "title": "", "headers": ["A", "B"], "widths": [20, 40], "rows": []},
                                                    {"type": "text", "title": "", "text": ""},
                                                    {"type": "kv", "title": "", "rows": [["k", "v"]]},
                                                    {"type": "image", "title": "", "path": "/abs/x.png", "width_px": 900},
                                                    {"type": "flows", "title": "", "rows": []}]}],
}

INVALID_SHEET_CHARS = re.compile(r"[\[\]\:\*\?\/\\]")


def safe_sheet_name(name, used):
    n = INVALID_SHEET_CHARS.sub("_", str(name)).strip()[:31] or "Sheet"
    base, k = n, 2
    while n in used:
        suf = f"_{k}"
        n = base[: 31 - len(suf)] + suf
        k += 1
    used.add(n)
    return n


def disp_width(s):
    return sum(2 if unicodedata.east_asian_width(ch) in "WFA" else 1 for ch in s)


def to_text(v, numbered=False):
    if v is None:
        return ""
    if isinstance(v, (list, tuple)):
        parts = [to_text(x) for x in v]
        if numbered:
            return "\n".join(p if re.match(r"^\s*(\d+[\.\)．]|[-・※→])", p) else f"{i}. {p}" for i, p in enumerate(parts, 1))
        return "\n".join(parts)
    if isinstance(v, dict):
        return "\n".join(f"{k}: {to_text(x)}" for k, x in v.items())
    return str(v)


def row_values(row, headers):
    if isinstance(row, dict):
        out = []
        for h in headers:
            v = row.get(h)
            if v is None:  # tolerant key match (ignore full/half width, spaces)
                hn = unicodedata.normalize("NFKC", h).replace(" ", "")
                for k, x in row.items():
                    kn = unicodedata.normalize("NFKC", str(k)).replace(" ", "")
                    if kn == hn or hn.startswith(kn):
                        v = x
                        break
            out.append(v)
        return out
    row = list(row)
    return row + [None] * (len(headers) - len(row))


GRID_N = 26      # 方眼 columns for multi-section sheets
GRID_W = 5.0     # width of each grid column (total ≈ 130 chars → A4 landscape)
FLOW_KEYS = ["目的", "トリガー", "入力", "処理", "出力", "境界・例外", "関連（BR/AC/API/Slide）"]


class Book:
    """Two layouts:
    - list sheets (one table): plain columns, freeze header, autofilter (easy to sort/filter/edit)
    - multi-section sheets (表紙/機能概要/現状分析/処理フロー/画面/API/テーブル定義/extra):
      日式「方眼」grid of GRID_N narrow columns; each table column is a merged span sized by its width.
    """

    def __init__(self, data, blank=False):
        self.d = data or {}
        self.meta = self.d.get("meta", {})
        self.blank = blank
        self.wb = openpyxl.Workbook()
        self.used = set()
        self.first = True
        self.toc = []
        self.links = {}

    # ---------- sheet ----------
    def new_sheet(self, name, desc="", landscape=True, grid=False):
        if self.first:
            ws = self.wb.active
            ws.title = safe_sheet_name(name, self.used)
            self.first = False
        else:
            ws = self.wb.create_sheet(safe_sheet_name(name, self.used))
        ws.sheet_view.showGridLines = False
        ws.sheet_view.zoomScale = 85
        ws.page_setup.paperSize = ws.PAPERSIZE_A4
        ws.page_setup.orientation = "landscape" if landscape else "portrait"
        ws.page_setup.fitToWidth = 1
        ws.page_setup.fitToHeight = 0
        ws.sheet_properties.pageSetUpPr.fitToPage = True
        ws.page_margins = PageMargins(left=0.4, right=0.4, top=0.5, bottom=0.5)
        ws.oddFooter.center.text = "&P / &N"
        ws._widths = {}
        ws._grid = grid
        if grid:
            self.set_widths(ws, [GRID_W] * GRID_N)
        if name != "表紙":
            self.toc.append((ws.title, desc))
        return ws

    def set_widths(self, ws, widths):
        for i, w in enumerate(widths, 1):
            if w and w > ws._widths.get(i, 0):
                ws._widths[i] = w
                ws.column_dimensions[get_column_letter(i)].width = w

    def preset(self, ws, *colspecs):
        if ws._grid:
            return
        for cols in colspecs:
            if cols:
                self.set_widths(ws, [w for _, w in cols])

    def ncols(self, ws):
        return GRID_N if ws._grid else max(list(ws._widths.keys()) + [2])

    def wsum(self, ws, c1, c2):
        return sum(ws._widths.get(i, 9) for i in range(c1, c2 + 1))

    # ---------- cells ----------
    def _cell(self, ws, r, c1, c2, val, label=False, fill=None, font=None, align=None):
        if c2 > c1:
            ws.merge_cells(start_row=r, start_column=c1, end_row=r, end_column=c2)
        c = ws.cell(row=r, column=c1, value=val if val != "" else None)
        c.font = font or (BOLD_FONT if label else BODY_FONT)
        c.alignment = align or (CENTER if label else WRAP)
        for k in range(c1, c2 + 1):
            cc = ws.cell(row=r, column=k)
            cc.border = BORDER
            if fill is not None:
                cc.fill = fill
            elif label:
                cc.fill = BAND_LABEL_FILL
        return c

    def fit_height(self, ws, row, texts_widths):
        lines = 1
        for t, w in texts_widths:
            if not t:
                continue
            cap = max(int((w or 10) * 1.05), 4)
            n = sum(max(1, math.ceil(disp_width(seg) / cap)) for seg in str(t).split("\n"))
            lines = max(lines, n)
        ws.row_dimensions[row].height = min(max(16, 14 * lines + 4), 409)

    def band(self, ws, sheet_title):
        ws._band = sheet_title
        return 4

    @staticmethod
    def _split(widths, k, weights=(0.2, 0.36, 0.26, 0.18)):
        """Split columns into k contiguous groups whose widths follow `weights`, each >= 2 cols."""
        n = len(widths)
        total = float(sum(widths))
        cum = [sum(weights[:i + 1]) / sum(weights) for i in range(k)]
        groups, start, acc = [], 1, 0.0
        for i, w in enumerate(widths, 1):
            acc += w
            left = k - len(groups) - 1
            if left > 0 and acc >= total * cum[len(groups)] - w / 2 and i - start >= 1 and n - i >= 2 * left:
                groups.append((start, i))
                start = i + 1
        groups.append((start, n))
        return groups

    def finish_bands(self):
        m = self.meta
        cells = [("システム名", m.get("system", "")), ("機能名", m.get("feature", "")),
                 ("文書番号", m.get("doc_no", "")), ("版数", m.get("version", "")),
                 ("シート名", None), ("作成者", m.get("author", "")),
                 ("作成日", m.get("created", "")), ("更新日", m.get("updated") or m.get("created", ""))]
        for ws in self.wb.worksheets:
            if not hasattr(ws, "_band"):
                continue
            n = self.ncols(ws)
            widths = [ws._widths.get(i, 9) for i in range(1, n + 1)]
            vals = [(k, v if v is not None else ws._band) for k, v in cells]
            groups = self._split(widths, 4) if n >= 8 else None
            if groups and len(groups) == 4 and all(b > a for a, b in groups):
                for r in (1, 2):
                    for gi, (c1, c2) in enumerate(groups):
                        lab, val = vals[(r - 1) * 4 + gi]
                        lab_end = c1
                        while lab_end < c2 - 1 and self.wsum(ws, c1, lab_end) < 10:
                            lab_end += 1
                        self._cell(ws, r, c1, lab_end, lab, label=True)
                        self._cell(ws, r, lab_end + 1, c2, val,
                                   align=Alignment(horizontal="left", vertical="center", wrap_text=True))
            else:
                for r in (1, 2):
                    txt = "　｜　".join(f"{k}：{v}" for k, v in vals[(r - 1) * 4:(r - 1) * 4 + 4])
                    self._cell(ws, r, 1, n, txt, fill=BAND_LABEL_FILL,
                               align=Alignment(horizontal="left", vertical="center", wrap_text=True))
            ws.row_dimensions[1].height = 18
            ws.row_dimensions[2].height = 18

    def section(self, ws, row, title, ncol=None, sub=False):
        ncol = max(ncol or self.ncols(ws), 2)
        fill = KEY_FILL if sub else SECTION_FILL
        self._cell(ws, row, 1, ncol, title, fill=fill,
                   font=Font(name=FONT, size=10 if sub else 11, bold=True),
                   align=Alignment(vertical="center", wrap_text=True))
        for k in range(1, ncol + 1):
            ws.cell(row=row, column=k).border = Border()
        ws.row_dimensions[row].height = 18 if sub else 20
        return row + 1

    # ---------- spans for grid mode ----------
    def spans(self, ws, widths):
        """Return [(c1,c2)] for each logical column."""
        if not ws._grid:
            return [(i, i) for i in range(1, len(widths) + 1)]
        total = min(GRID_N, max(len(widths), round(sum(widths) / GRID_W)))
        raw = [w / float(sum(widths)) * total for w in widths]
        sp = [max(1, int(round(x))) for x in raw]
        while sum(sp) > total:
            i = max(range(len(sp)), key=lambda j: sp[j] - raw[j])
            if sp[i] > 1:
                sp[i] -= 1
            else:
                break
        while sum(sp) < total:
            i = max(range(len(sp)), key=lambda j: raw[j] - sp[j])
            sp[i] += 1
        out, c = [], 1
        for s in sp:
            out.append((c, c + s - 1))
            c += s
        return out

    # ---------- blocks ----------
    def table(self, ws, row, headers_widths, rows, title=None):
        headers = [h for h, _ in headers_widths]
        widths = [w for _, w in headers_widths]
        if not ws._grid:
            self.set_widths(ws, widths)
        sp = self.spans(ws, widths)
        if title:
            row = self.section(ws, row, title)
        for (c1, c2), h in zip(sp, headers):
            self._cell(ws, row, c1, c2, h, fill=HEADER_FILL, font=HEADER_FONT, align=CENTER)
        ws.row_dimensions[row].height = 20 if max(disp_width(h) for h in headers) < 30 else 32
        hdr_row = row
        row += 1
        rows = list(rows or [])
        if not rows:
            if self.blank:
                rows = [[None] * len(headers)] * 3
            else:
                rows = [["—", "該当なし"] + [None] * (len(headers) - 2)] if len(headers) > 1 else [["該当なし"]]
        for r in rows:
            vals = row_values(r, headers)
            tw = []
            for (c1, c2), h, v, w in zip(sp, headers, vals, widths):
                txt = to_text(v, numbered=h.startswith("処理"))
                short = len(txt) <= 4 and "\n" not in txt
                al = Alignment(horizontal="center" if short and w <= 10 else "left", vertical="top", wrap_text=True)
                fill = None
                key = txt.strip()
                is_status = "状態" in h or h in ("PPT", "設計", "コード", "衝突")
                for mark, color in (STATUS_FILLS.items() if is_status else []):
                    if key == mark or key.startswith(mark):
                        fill = PatternFill("solid", start_color=color, end_color=color)
                        break
                self._cell(ws, row, c1, c2, txt, align=al, fill=fill if fill else PatternFill(fill_type=None))
                tw.append((txt, self.wsum(ws, c1, c2)))
            self.fit_height(ws, row, tw)
            row += 1
        return row + 1, hdr_row

    def kv(self, ws, row, pairs, title=None, sub=False, key_w=16):
        n = self.ncols(ws)
        if not ws._grid and not ws._widths:
            self.set_widths(ws, [22, 80])
            n = 2
        kend = 1
        while kend < n - 1 and self.wsum(ws, 1, kend) < key_w:
            kend += 1
        if title:
            row = self.section(ws, row, title, sub=sub)
        pairs = list(pairs or []) or ([[None, None]] * 2 if self.blank else [["—", "該当なし"]])
        for p in pairs:
            if isinstance(p, dict):
                k, v = row_values(p, ["項目", "内容"])
            else:
                k, v = (list(p) + [None, None])[:2]
            self._cell(ws, row, 1, kend, to_text(k), fill=KEY_FILL, font=BOLD_FONT, align=WRAP)
            txt = to_text(v, numbered=str(k).startswith("処理"))
            self._cell(ws, row, kend + 1, n, txt)
            self.fit_height(ws, row, [(txt, self.wsum(ws, kend + 1, n)), (to_text(k), self.wsum(ws, 1, kend))])
            row += 1
        return row + 1

    def flow_blocks(self, ws, row, flows, title=None):
        """設計書記述規範 §3: fixed block 目的/トリガー/入力/処理/出力/境界 (+関連) per scenario."""
        if title:
            row = self.section(ws, row, title)
        flows = list(flows or []) or ([{}] if self.blank else [])
        if not flows:
            return self.kv(ws, row, [["—", "該当なし"]])
        for f in flows:
            if not isinstance(f, dict):
                f = dict(zip([h for h, _ in FLOW_COLS], f))
            vals = row_values(f, ["No", "シナリオ"] + FLOW_KEYS)
            head = f"{vals[0] or 'F-xx'}　{vals[1] or '{シナリオ（業務語）}'}"
            pairs = [[k, v] for k, v in zip(FLOW_KEYS, vals[2:]) if v or self.blank or k != FLOW_KEYS[-1]]
            row = self.kv(ws, row, pairs, title=head, sub=True)
        return row

    def text(self, ws, row, text, title=None):
        n = self.ncols(ws)
        if title:
            row = self.section(ws, row, title)
        txt = to_text(text) or ("" if self.blank else "該当なし")
        mono = any(ch in txt for ch in "┌│└─├")
        self._cell(ws, row, 1, n, txt, font=Font(name="MS Gothic" if mono else FONT, size=10))
        self.fit_height(ws, row, [(txt, self.wsum(ws, 1, n))])
        return row + 2

    def image(self, ws, row, path, width_px=900, title=None):
        if title:
            row = self.section(ws, row, title)
        if not path or not os.path.exists(str(path)):
            ws.cell(row=row, column=1, value=f"（画像なし: {path}）").font = BODY_FONT
            return row + 2
        from openpyxl.drawing.image import Image as XLImage
        img = XLImage(path)
        if img.width > width_px:
            ratio = width_px / img.width
            img.width, img.height = int(img.width * ratio), int(img.height * ratio)
        ws.add_image(img, f"A{row}")
        return row + int(img.height / 20) + 2

    def sections(self, ws, row, spec, data):
        data = data or {}
        for key, title, cols in spec:
            val = data.get(key)
            if key == "details":
                row = self.flow_blocks(ws, row, val, title)
            elif key in ("overview", "basic", "auth"):
                row = self.kv(ws, row, val, title)
            elif cols is None:
                row = self.text(ws, row, val, title)
                if key == "layout":
                    for p in data.get("layout_images", []) or []:
                        row = self.image(ws, row, p)
            else:
                row = self.table(ws, row, cols, val, title)[0]
        return row

    # ---------- sheets ----------
    def cover(self):
        m = self.meta
        ws = self.new_sheet("表紙", landscape=False)
        self.set_widths(ws, [4, 22, 60, 4])
        ws.merge_cells("B4:C4")
        ws["B4"] = m.get("title") or f"{m.get('feature', '{機能名}')} 詳細設計書"
        ws["B4"].font, ws["B4"].alignment = TITLE_FONT, CENTER
        ws.row_dimensions[4].height = 40
        ws.merge_cells("B5:C5")
        ws["B5"] = m.get("system", "")
        ws["B5"].font, ws["B5"].alignment = Font(name=FONT, size=12), CENTER
        pairs = [("文書番号", m.get("doc_no", "")), ("機能名", m.get("feature", "")),
                 ("画面番号", m.get("screen_ids", "")), ("API番号", m.get("api_ids", "")),
                 ("版数", m.get("version", "")), ("作成日", m.get("created", "")),
                 ("更新日", m.get("updated", "")), ("作成者", m.get("author", "")),
                 ("レビュー者", m.get("reviewer", "")), ("承認者", m.get("approver", "")),
                 ("状態", m.get("status", "")), ("要件参照", m.get("requirement", "")),
                 ("機能ディレクトリ", m.get("docs_dir", "")), ("関連設計書", m.get("related", "")),
                 ("対象コード", m.get("repo", ""))]
        r = 8
        for k, v in pairs:
            self._cell(ws, r, 2, 2, k, fill=KEY_FILL, font=BOLD_FONT, align=WRAP)
            self._cell(ws, r, 3, 3, v)
            self.fit_height(ws, r, [(str(v), 60)])
            r += 1
        r += 1
        legend = "記号：○ 必須／△ 条件付き必須／× 対象外・不可／✅ 実装済／⏳ 設計済・未実装／△(状態) 要件と差異あり"
        ws.merge_cells(start_row=r, start_column=2, end_row=r, end_column=3)
        ws.cell(row=r, column=2, value=legend).font = Font(name=FONT, size=9, color="595959")

    def finish_index(self):
        ws, row = self._index
        self.table(ws, row, [("No", 5), ("シート", 30), ("内容", 70)],
                   [[i, n, d] for i, (n, d) in enumerate(self.toc, 1)])
        for r in range(1, ws.max_row + 1):
            c = ws.cell(row=r, column=2)
            if c.value in self.wb.sheetnames and c.value != ws.title:
                c.hyperlink = Hyperlink(ref=c.coordinate, location=f"'{c.value}'!A1", display=c.value)
                c.font = LINK_FONT

    def build(self):
        d = self.d
        for key, name, required, kind in CATALOG:
            present = bool(d.get(key)) or (key == "screen_list" and d.get("screens")) or (key == "api_list" and d.get("apis"))
            if not (required or present or self.blank):
                continue
            if kind == "cover":
                self.cover()
            elif kind == "screens":
                for s in (d.get("screens") or ([{}] if self.blank else [])):
                    sid = s.get("id", "SCR-xxx")
                    ws = self.new_sheet(s.get("sheet") or sid, f"画面設計：{sid} {s.get('name', '')}", grid=True)
                    self.links[sid] = ws.title
                    row = self.band(ws, ws.title)
                    head = [("画面ID", sid), ("画面名", s.get("name", "")), ("変更種別", s.get("change_type", "")),
                            ("要件来源（PPT）", s.get("ppt_source", "")), ("実装状態", s.get("status", ""))]
                    row = self.kv(ws, row, head, title=f"{sid}　{s.get('name', '')}")
                    self.sections(ws, row, SCREEN_SECTIONS, s)
            elif kind == "apis":
                for a in (d.get("apis") or ([{}] if self.blank else [])):
                    aid = a.get("id", "API-xxx")
                    ws = self.new_sheet(a.get("sheet") or aid, f"API設計：{aid} {a.get('name', '')}", grid=True)
                    self.links[aid] = ws.title
                    row = self.band(ws, ws.title)
                    head = [("API ID", aid), ("名称", a.get("name", "")), ("HTTP", a.get("method", "")),
                            ("Path", a.get("path", "")), ("画面", a.get("screens", "")), ("実装状態", a.get("status", ""))]
                    head += [tuple((list(x) + [None, None])[:2]) if not isinstance(x, dict) else tuple(row_values(x, ["項目", "内容"]))
                             for x in (a.get("basic") or [])]
                    row = self.kv(ws, row, head, title=f"{aid}　{a.get('name', '')}")
                    self.sections(ws, row, API_SECTIONS, a)
            elif kind == "tables":
                ws = self.new_sheet(name, "テーブル定義・インデックス・移行スクリプト", grid=True)
                row = self.band(ws, ws.title)
                for t in (d.get("tables") or ([{}] if self.blank else [])):
                    title = f"{t.get('name', '{schema}.{table}')}（{t.get('change', '')}）{t.get('description', '')}"
                    row = self.table(ws, row, TABLE_SECTIONS_COLS, t.get("columns"), title)[0]
                    if t.get("indexes") or self.blank:
                        row = self.table(ws, row, INDEX_COLS, t.get("indexes"), "インデックス／一意制約")[0]
                    if t.get("entity") or t.get("mapper"):
                        row = self.kv(ws, row, [("Entity", t.get("entity", "")), ("Mapper", t.get("mapper", ""))])
                if d.get("migrations") or self.blank:
                    row = self.table(ws, row, C(("スクリプト", 50), ("環境", 14), ("説明", 40)), d.get("migrations"), "移行スクリプト")[0]
            elif kind == "index":
                ws = self.new_sheet(name, "シート一覧")
                self.preset(ws, [("No", 5), ("シート", 30), ("内容", 70)])
                self.toc.pop()
                self._index = (ws, self.band(ws, ws.title))
            elif key == "flows":
                ws = self.new_sheet(name, "業務語による処理フロー（目的/トリガー/入力/処理/出力/境界）", grid=True)
                row = self.band(ws, ws.title)
                self.flow_blocks(ws, row, d.get("flows"))
            else:
                desc = {"revisions": "版数・改訂内容", "overview": "要件概要・対象外・実現方針・権限・構成",
                        "traceability": "PPT 要件 ⇔ 設計 ⇔ 既存コードのトレーサビリティ",
                        "current_state": "既存コード調査（主キー・入口・既存ロジック・リスク）",
                        "business_rules": "業務ルール BR-xx", "screen_list": "画面一覧", "api_list": "API一覧",
                        "checks": "入力チェック・エラーコード・メッセージ", "sqls": "SQL 一覧（業務説明）",
                        "acceptance": "受入基準 AC-xx（Human 承認ゲート）", "questions": "要確認事項（BA/PO 回答待ち）",
                        "impl_map": "実装対照（開発用：ファイル・関数名はここだけ）"}.get(key, "")
                multi = len(kind) > 1
                ws = self.new_sheet(name, desc, grid=multi)
                self.preset(ws, *[c for _, _, c in kind])
                row = self.band(ws, ws.title)
                rows = None
                if key == "screen_list" and not d.get("screen_list"):
                    rows = [[s.get("id"), s.get("name"), s.get("change_type"), s.get("ppt_source"), s.get("status"), None]
                            for s in d.get("screens", [])]
                elif key == "api_list" and not d.get("api_list"):
                    rows = [[a.get("id"), a.get("name"), a.get("method"), a.get("path"), a.get("screens"), a.get("status"), None]
                            for a in d.get("apis", [])]
                src = d.get(key)
                first_hdr = None
                for skey, stitle, cols in kind:
                    val = rows if rows is not None else (src.get(skey) if isinstance(src, dict) else src)
                    row, hdr = self.table(ws, row, cols, val, stitle)
                    first_hdr = first_hdr or hdr
                if not multi and first_hdr:
                    ws.freeze_panes = ws.cell(row=first_hdr + 1, column=1)
                    ws.auto_filter.ref = f"A{first_hdr}:{get_column_letter(len(kind[0][2]))}{max(first_hdr + 1, ws.max_row)}"
                    ws.print_title_rows = f"{first_hdr}:{first_hdr}"
        for ex in d.get("extra_sheets", []) or []:
            ws = self.new_sheet(ex.get("name", "追加"), ex.get("desc", ""), grid=True)
            row = self.band(ws, ws.title)
            for b in ex.get("blocks", []):
                t = b.get("type")
                if t == "table":
                    cols = list(zip(b["headers"], b.get("widths") or [18] * len(b["headers"])))
                    row = self.table(ws, row, cols, b.get("rows"), b.get("title"))[0]
                elif t == "kv":
                    row = self.kv(ws, row, b.get("rows"), b.get("title"))
                elif t == "text":
                    row = self.text(ws, row, b.get("text"), b.get("title"))
                elif t == "image":
                    row = self.image(ws, row, b.get("path"), b.get("width_px", 900), b.get("title"))
                elif t == "flows":
                    row = self.flow_blocks(ws, row, b.get("rows"), b.get("title"))
        for lst, col in (("画面一覧", 6), ("API一覧", 7)):
            if lst in self.wb.sheetnames:
                ws = self.wb[lst]
                for r in range(1, ws.max_row + 1):
                    v = ws.cell(row=r, column=1).value
                    if v in self.links:
                        c = ws.cell(row=r, column=col, value=self.links[v])
                        c.hyperlink = Hyperlink(ref=c.coordinate, location=f"'{self.links[v]}'!A1", display=self.links[v])
                        c.font = LINK_FONT
        if hasattr(self, "_index"):
            self.finish_index()
        self.finish_bands()
        self.wb.properties.creator = self.meta.get("author") or ""
        self.wb.properties.lastModifiedBy = self.meta.get("author") or ""
        self.wb.properties.title = self.meta.get("title") or self.meta.get("feature", "")
        return self.wb


# ---------- lint: 設計書記述規範 ----------
FUNC_RE = re.compile(r"\b[a-z][a-z0-9]+(?:[A-Z][a-z0-9]+){1,}\b(?:\(\))?|\b\w+\.(?:vue|ts|java|xml)\b|#\w+\(")
MAIN_TEXT_SHEETS = ("処理フロー", "業務ルール", "受入基準")


def lint(data):
    w = []
    m = data.get("meta", {})
    for k in ("feature", "doc_no", "version", "created", "requirement"):
        if not m.get(k):
            w.append(f"meta.{k} が空")
    def scan(where, val):
        for hit in set(FUNC_RE.findall(to_text(val))):
            w.append(f"[記述規範] {where}: 関数名/ファイル名らしき語 '{hit}' → 業務語に直し、実装対照シートへ")
    for f in data.get("flows", []):
        fid = f.get("No") if isinstance(f, dict) else f[0]
        if isinstance(f, dict):
            for k in ("目的", "トリガー", "入力", "処理", "出力", "境界・例外"):
                if not f.get(k):
                    w.append(f"[処理フロー] {fid}: '{k}' が空（目的/トリガー/入力/処理/出力/境界 は固定構成）")
                scan(f"処理フロー {fid}.{k}", f.get(k))
    for s in data.get("screens", []):
        if not s.get("ppt_source"):
            w.append(f"[画面] {s.get('id')}: 要件来源（PPT slide/注釈）が空")
        if s.get("change_type") == "改修" and not s.get("ppt_diff"):
            w.append(f"[画面] {s.get('id')}: 改修画面なのに PPT vs 現状 差異表が空")
        for d in s.get("details", []):
            if isinstance(d, dict):
                for k in ("目的", "トリガー", "処理", "出力", "境界・例外"):
                    scan(f"{s.get('id')} 実装詳細.{k}", d.get(k))
        if s.get("id") and not re.match(r"^SCR-", str(s.get("id"))):
            w.append(f"[ID] 画面ID '{s.get('id')}' は SCR- で始めること")
    for a in data.get("apis", []):
        if a.get("id") and not re.match(r"^API-", str(a.get("id"))):
            w.append(f"[ID] API ID '{a.get('id')}' は API- で始めること")
        if not a.get("logic"):
            w.append(f"[API] {a.get('id')}: ビジネスロジック(BL)が空（『Service参照』だけは不可）")
    for i, t in enumerate(data.get("traceability", []), 1):
        v = row_values(t, ["No", "Slide／注釈"])
        if not v[1]:
            w.append(f"[要件対応表] 行{i}: Slide／注釈 が空")
    for q in data.get("questions", []):
        v = row_values(q, ["No", "質問", "選択肢・備考", "影響", "暫定設計方針", "状態"])
        if not v[5]:
            w.append(f"[要確認事項] {v[0]}: 状態が空（未回答/回答済）")
    for r in data.get("business_rules", []):
        v = row_values(r, ["規則ID"])
        if v[0] and not re.match(r"^BR-", str(v[0])):
            w.append(f"[ID] 規則ID '{v[0]}' は BR- で始めること")
    for r in data.get("acceptance", []):
        v = row_values(r, ["AC-ID"])
        if v[0] and not re.match(r"^AC-", str(v[0])):
            w.append(f"[ID] '{v[0]}' は AC- で始めること")
    if not data.get("acceptance"):
        w.append("[受入基準] AC が 1 件もない")
    return w


def load(path):
    with open(path, encoding="utf-8") as f:
        if path.endswith((".yaml", ".yml")):
            import yaml  # optional
            return yaml.safe_load(f)
        return json.load(f)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("input", nargs="?")
    ap.add_argument("-o", "--out")
    ap.add_argument("--blank", action="store_true", help="emit the empty template with every sheet")
    ap.add_argument("--schema", action="store_true", help="print JSON skeleton")
    ap.add_argument("--no-lint", action="store_true")
    ap.add_argument("--system", help="--blank 時のシステム名（省略時はプレースホルダ）")
    a = ap.parse_args()
    if a.schema:
        print(json.dumps(SCHEMA, ensure_ascii=False, indent=2))
        return
    if a.blank:
        data = {"meta": {"system": a.system or "{システム名}", "feature": "{機能名}", "doc_no": "{B04-G-xxx-DD}", "version": "1.00",
                         "created": "YYYY-MM-DD", "title": "{機能名} 詳細設計書"}}
    else:
        if not a.input:
            ap.error("input JSON required (or --blank / --schema)")
        data = load(a.input)
        if not str((data.get("meta") or {}).get("system", "")).strip():
            sys.exit("ERROR: meta.system（システム名）が未設定です。項目配置の system_name を入れてください。")
    out = a.out or (os.path.splitext(a.input)[0] + ".xlsx" if a.input else "設計書_テンプレート.xlsx")
    wb = Book(data, blank=a.blank).build()
    wb.save(out)
    print(f"saved: {out}  sheets={wb.sheetnames}")
    if not a.blank and not a.no_lint:
        ws = lint(data)
        print(f"lint: {len(ws)} warning(s)")
        for x in ws:
            print("  - " + x)


if __name__ == "__main__":
    main()
