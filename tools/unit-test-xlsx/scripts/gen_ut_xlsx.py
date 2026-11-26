#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""単体テスト項目 xlsx 生成 + lint（仓库模板 OOXML 最小修改）

用法（--config は init.sh で生成した project.json。必須）:
  python3 gen_ut_xlsx.py cases.json -o 単体テスト項目_{機能}.xlsx --config project.json
                         [--design design.json|docs_dir|設計書.xlsx]
                         [--locale-dir DIR] [--template X.xlsx] [--trace-col] [--strict] [--trace-report trace.md]
  python3 gen_ut_xlsx.py --schema          # 打印 cases.json 骨架
  python3 gen_ut_xlsx.py --lint-only cases.json --config project.json [--design ...]

項目配置から読むもの: ids.error_code（错误码正则）、i18n.languages（先頭＝正文語）、i18n.locale_dir（--locale-dir 省略時、
カレント＝プロジェクトのルートからの相対）、unit_test.locale_files（各言語の locale ファイル、先に読んだ方が優先）、
unit_test.error_message_templates / unit_test.language_labels（code 行の展開）、unit_test.template（テンプレート）。

设计要点（与仓库 docs/単体テスト項目テンプレート/README.md 一致）:
  * 以 templates/単体テスト項目_テンプレート.xlsx 为底，ZIP 成员原样拷贝，只替换
    画面レイアウト判定 / 画面操作処理判定 / 項目チェック判定 的 sheetData 和 項目総計 的少数单元格。
  * 試験観点 sheet、隐藏的 DB書き込み判定 sheet 字节级不变（生成后校验）。
  * sharedStrings 保留原始 <si>（含振假名 rPh），只追加新字符串
    （仓库旧 helper 会把振假名拼进表头，如「試験項目シケンコウモク」——这里修正）。
  * 同步更新：数据验证范围（最新結果 / 試験観点下拉 / 表示タイプ / 詰め方）、自动筛选、
    _FilterDatabase / Print_Area、項目総計 COUNTIF 范围；删除旧 calcChain，打开时全量重算。
  * 画面レイアウト判定 底部的凡例（記号・データタイプ・表示タイプ一覧）挪到最后一条 Case 之后保留，
    表示タイプ下拉的引用随之更新。
"""
from __future__ import annotations

import argparse
import json
import math
import re
import shutil
import sys
import unicodedata
import zipfile
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from xml.sax.saxutils import escape

HERE = Path(__file__).resolve().parent
SKILL = HERE.parent
sys.path.insert(0, str(HERE.parents[1]))  # tools/project_config.py
import project_config  # noqa: E402

TEMPLATE_NAME = "単体テスト項目_テンプレート.xlsx"
# テンプレートの探索順: --template > unit_test.template > このツールの templates/ > カレントの docs/ai-native/
TEMPLATE_CANDIDATES = [SKILL / "templates" / TEMPLATE_NAME, Path("docs") / "ai-native" / TEMPLATE_NAME]

VIEWPOINTS = [
    "画面レイアウト", "分岐網羅", "設定値", "データパターン", "境界値", "初期化チェック",
    "ロールチェック", "NULL値チェック", "デグレ試験", "性能改善対応", "他システム連携IF",
    "例外処理の網羅", "タイムアウト処理", "多言語対応チェック", "非同期処理チェック", "セッション・認証処理",
]
DISPLAY_TYPES = ["TT", "BTN", "LBL", "DRP", "TXT", "RBT", "CHK", "INP", "CMB", "TBL", "IB", "LNK"]
ALIGN = ["左", "中", "右", "-"]
VAGUE = {"正常", "正常に動作する", "正常終了", "正しく動作する", "問題ない", "問題なし", "OK", "仕様通り",
         "設計通り", "想定通り", "同上", "正常に表示される", "正常に処理される", "正常", "成功", "可"}
ZH_ONLY = set("这们为没时后对个说么样还过从让发录删页确认击选择据项请显隐设输键钮创该页时间应")
CFG: dict = {}
LANGS: List[str] = []
CODE_RE: "re.Pattern" = None  # configure() で ids.error_code から作る
FUNC_RE = re.compile(r"\b[a-z]+[A-Z][A-Za-z0-9]*\s*\(|\b\w+\.(java|vue|ts|tsx|xml)\b|src/main/|src/views/")

# 样式 ID（取自模板数据行，同仓库 scripts/ooxml_unit_test_workbook.py）
LAYOUT_SECTION_STYLE = "33"
LAYOUT_STYLES = {"A": "83", "B": "82", "C": "70", "D": "82", "E": "68", "F": "70", "G": "68", "H": "68",
                 "I": "68", "J": "82", "K": "68", "L": "82", "M": "68", "N": "69", "O": "68", "P": "69",
                 "Q": "68", "R": "70", "S": "68", "T": "70", "U": "68", "V": "70", "W": "68", "X": "59",
                 "Y": "60", "Z": "61", "AA": "67"}
OP_SECTION_STYLE = "33"  # 模板 画面操作処理判定!A2 的分组行样式（左对齐）；仓库旧 helper 用 55 会居中截断
OP_STYLES = {"A": "55", "B": "56", "C": "79", "D": "78", "E": "57", "F": "57", "G": "57", "H": "58",
             "I": "59", "J": "60", "K": "61", "L": "62"}
CHECK_STYLES = {"A": "55", "B": "87", "C": "67", "D": "67", "E": "60", "F": "82", "G": "60", "H": "59",
                "I": "60", "J": "61", "K": "67"}

SHEET_FILES = {"summary": "xl/worksheets/sheet2.xml", "layout": "xl/worksheets/sheet3.xml",
               "operation": "xl/worksheets/sheet4.xml", "check": "xl/worksheets/sheet5.xml"}
FIXED_FILES = ["xl/worksheets/sheet1.xml", "xl/worksheets/sheet6.xml"]  # 試験観点 / DB書き込み判定

SCHEMA = {
    "meta": {"feature": "機能名", "author": "AI", "created": "2026-10-09", "updater": "", "updated": "",
             "design_doc": "docs/{機能}/ または 設計書.xlsx", "lang": "ja"},
    "layout": [{"section": "【SCR-xxx 画面名】エリア名", "ref": "SCR-xxx", "cases": [
        {"viewpoint": "画面レイアウト", "name": "項目名", "type": "BTN", "label": "ラベル表示内容（画面文言そのまま）",
         "max_len": "-", "required": "-", "align": "左", "format": "-", "dtype": "-", "note": "特記事項（可判定な補足）",
         "ref": "SCR-xxx #3 / slide 4"}]}],
    "operation": [{"section": "【SCR-xxx / API-xxx】シナリオ", "ref": "API-xxx", "cases": [
        {"viewpoint": "分岐網羅", "item": "試験項目", "step": "処理ステップ（操作）", "branch": "分岐（条件）",
         "branch1": "-", "branch2": "-", "expected": "予想結果（可判定）", "ref": "BR-03 / BL-05 / AC-01"}]}],
    "check": [{"section": "（任意）【API-xxx 行チェック】", "cases": [
        {"viewpoint": "例外処理の網羅", "field": "項目名", "screen": "画面", "branch1": "入力値・条件",
         "branch2": "-", "expected": "予想結果", "ref": "§3-1"},
        {"viewpoint": "例外処理の網羅", "field": "プロセス", "screen": "取込ダイアログ", "branch1": "空欄",
         "code": "<ids.error_code に合うコード>", "pair": True, "ref": "A",
         "_comment": "code 指定時は locale から文言を引き、i18n.languages の各言語の行（2 言語目以降は多言語対応チェック）を自動展開"}]}],
}


# ---------------------------------------------------------------- locale
class Locale:
    """i18n.languages の各言語について unit_test.locale_files を順に読む（先に読んだ方が優先）"""

    def __init__(self, d: Optional[Path]):
        self.msgs: Dict[str, Dict[str, str]] = {l: {} for l in LANGS}
        if not d:
            return
        pat = re.compile(r"'(" + CODE_RE.pattern + r")'\s*:\s*(?:'((?:\\'|[^'])*)'|\n\s*'((?:\\'|[^'])*)')", re.M)
        cands = {l: [d / f for f in CFG["unit_test"]["locale_files"][l]] for l in LANGS}
        for lang, paths in cands.items():
            target = self.msgs[lang]
            for p in paths:
                if not p.exists():
                    continue
                text = p.read_text(encoding="utf-8")
                for m in re.finditer(r"'(" + CODE_RE.pattern + r")'\s*:\s*\(\{[^}]*\}\)\s*=>\s*`([^`]*)`", text):
                    target.setdefault(m.group(1), re.sub(r"\$\{[^}]*\}", "{0}", m.group(2)))
                for m in pat.finditer(text):
                    v = (m.group(2) or m.group(3) or "").replace("\\'", "'")
                    if v and not v.startswith("(") and m.group(1) not in target:
                        target[m.group(1)] = v

    @property
    def primary(self) -> Dict[str, str]:
        """正文語（i18n.languages の先頭）の文言"""
        return self.msgs[LANGS[0]]

    def msg(self, code: str, lang: str, param: Optional[str] = None) -> Optional[str]:
        raw = self.msgs.get(lang, {}).get(code)
        if raw is None:
            return None
        if param is not None:
            raw = raw.replace("{0}", param)
        return raw


# ---------------------------------------------------------------- case normalisation
def _label(lang: str) -> str:
    return CFG["unit_test"]["language_labels"][lang]


def _err_msg(lang: str, text: str, code: str) -> str:
    return CFG["unit_test"]["error_message_templates"][lang].replace("{code}", code).replace("{text}", text)


def expand_check_cases(groups: List[dict], loc: Locale, warnings: List[str]) -> List[dict]:
    out = []
    for g in groups:
        rows = []
        for c in g.get("cases", []):
            code = c.get("code")
            if code and not c.get("expected"):
                # 先頭言語＝正文行、2 言語目以降＝多言語対応チェック行（"pair": false なら正文行だけ）
                for i, lg in enumerate(LANGS if c.get("pair", True) else LANGS[:1]):
                    text = loc.msg(code, lg, c.get("param") if i == 0 else c.get(f"param_{lg}", c.get("param")))
                    if text is None:
                        warnings.append(f"[check] {code} の {lg} 文言が locale に無い" +
                                        ("（expected を手書きするか locale を確認）" if i == 0 else ""))
                        text = "（文言要確認）" if i == 0 else "(message TBD)"
                    r = dict(c)
                    if i == 0:
                        r["branch2"] = c.get("branch2") or _label(lg)
                    else:
                        r["viewpoint"] = "多言語対応チェック"
                        r["branch2"] = _label(lg)
                    r["expected"] = _err_msg(lg, text, code)
                    rows.append(r)
            else:
                rows.append(c)
        out.append({"section": g.get("section"), "ref": g.get("ref"), "cases": rows})
    return out


# ---------------------------------------------------------------- lint
def disp_width(s: str) -> int:
    return sum(2 if unicodedata.east_asian_width(ch) in "WFA" else 1 for ch in s)


def lint(data: dict, layout, operation, check, design_ids: Optional[Dict[str, str]], lang: str,
         loc: Optional["Locale"] = None) -> List[str]:
    w: List[str] = []
    seen = set()

    def text_checks(where: str, c: dict, fields: List[str]):
        for f in fields:
            v = str(c.get(f, "") or "")
            if FUNC_RE.search(v):
                w.append(f"{where}: 「{f}」に関数名/ファイルパスらしき記述 → 業務語で書く（{v[:40]}）")
            if lang == "ja" and f not in ("label",) and any(ch in ZH_ONLY for ch in v):
                w.append(f"{where}: 「{f}」に簡体字中国語らしき文字（{v[:30]}）")

    def common(where, c, req):
        vp = c.get("viewpoint")
        if vp not in VIEWPOINTS:
            w.append(f"{where}: 試験観点「{vp}」は 試験観点 sheet の16項目に無い")
        for f in req:
            if not str(c.get(f, "") or "").strip():
                w.append(f"{where}: 必須「{f}」が空")
        exp = str(c.get("expected", "") or "").strip()
        if "expected" in req and (exp in VAGUE or len(exp) < 4):
            w.append(f"{where}: 予想結果「{exp}」は判定不能（何がどうなるかを書く）")
        if any(c.get(k) for k in ("result", "tester", "history", "bug")):
            w.append(f"{where}: 最新結果/担当者/判定履歴/BUG票ID は空のまま（テスト実施者が記入）")
        if not (c.get("ref") or c.get("_section_ref")):
            w.append(f"{where}: ref（設計書 ID / slide）が無い → トレース不能")

    n = 0
    for g in layout:
        if not g.get("section"):
            w.append("[layout] section（【画面名】エリア）が無いグループ")
        for c in g["cases"]:
            n += 1
            c = dict(c, _section_ref=g.get("ref"))
            where = f"[layout#{n} {c.get('name','')}]"
            common(where, c, ["name", "type", "label"])
            if c.get("type") not in DISPLAY_TYPES:
                w.append(f"{where}: 表示タイプ「{c.get('type')}」は凡例 {DISPLAY_TYPES} に無い")
            if c.get("align", "左") not in ALIGN:
                w.append(f"{where}: 詰め方は 左/中/右/-")
            text_checks(where, c, ["name", "note"])
            key = ("L", c.get("name"), c.get("label"), c.get("viewpoint"))
            if key in seen:
                w.append(f"{where}: 重複行")
            seen.add(key)
    n = 0
    for g in operation:
        if not g.get("section"):
            w.append("[operation] section が無いグループ")
        for c in g["cases"]:
            n += 1
            c = dict(c, _section_ref=g.get("ref"))
            where = f"[operation#{n} {c.get('item','')}]"
            common(where, c, ["item", "step", "expected"])
            text_checks(where, c, ["item", "step", "branch", "branch1", "branch2", "expected"])
            key = ("O", c.get("item"), c.get("step"), c.get("branch"), c.get("branch1"), c.get("branch2"))
            if key in seen:
                w.append(f"{where}: 重複行（同じ 試験項目+処理ステップ+分岐）")
            seen.add(key)
    n = 0
    for g in check:
        for c in g["cases"]:
            n += 1
            c = dict(c, _section_ref=g.get("ref"))
            where = f"[check#{n} {c.get('field','')}]"
            common(where, c, ["field", "screen", "branch1", "expected"])
            text_checks(where, c, ["field", "branch1", "branch2", "expected"] if c.get("viewpoint") != "多言語対応チェック" else ["field"])
            key = ("C", c.get("field"), c.get("screen"), c.get("branch1"), c.get("branch2"))
            if key in seen:
                w.append(f"{where}: 重複行（同じ 項目名+画面+分岐1+分岐2）")
            seen.add(key)

    # coverage
    allcases = [("L", c, g) for g in layout for c in g["cases"]] + \
               [("O", c, g) for g in operation for c in g["cases"]] + [("C", c, g) for g in check for c in g["cases"]]
    blob = "\n".join(json.dumps(c, ensure_ascii=False) + str(g.get("ref") or "") + str(g.get("section") or "")
                     for _, c, g in allcases)
    check_blob = "\n".join(json.dumps(c, ensure_ascii=False) for kind, c, _g in allcases if kind == "C")
    vps = {c.get("viewpoint") for _, c, _ in allcases}
    for must in ("画面レイアウト", "分岐網羅", "多言語対応チェック"):
        if must not in vps and layout:
            w.append(f"[coverage] 観点「{must}」の Case が0件")
    if not any(c.get("viewpoint") == "初期化チェック" for _, c, _ in allcases):
        w.append("[coverage] 初期化チェック（初期表示・初期値）の Case が0件")
    if design_ids:
        miss, stale = [], []
        for i, label in design_ids.items():
            if CODE_RE.fullmatch(i) and loc is not None and loc.primary and i not in loc.primary:
                if i in check_blob:
                    w.append(f"[coverage] {i} は locale に無いのに Case で使用 → 現行コードのエラーコードに置換")
                stale.append(f"{i}（{label}）" if label else i)
                continue
            hay = blob
            if not re.search(rf"(?<![\w-]){re.escape(i)}(?![\w-])" if not CODE_RE.fullmatch(i) else re.escape(i), hay):
                miss.append(f"{i}（{label}）" if label else i)
        if miss:
            w.append(f"[coverage] 設計書の ID に対応 Case なし {len(miss)}件: " + "、".join(miss))
        if stale:
            w.append(f"[design] 設計書のエラーコードが現行 locale に無い {len(stale)}件（設計書が古い可能性 → 要確認事項に記載）: " + "、".join(stale))
        # ja/en pair for every message code used in check sheet
    codes_ja = set(CODE_RE.findall("\n".join(str(c.get("expected", "")) for _, c, _ in allcases if c.get("viewpoint") != "多言語対応チェック")))
    codes_en = set(CODE_RE.findall("\n".join(str(c.get("expected", "")) for _, c, _ in allcases if c.get("viewpoint") == "多言語対応チェック")))
    if len(LANGS) > 1 and codes_ja - codes_en:
        w.append(f"[coverage] {'・'.join(_label(l) for l in LANGS[1:])}（多言語対応チェック）Case が無いエラーコード: {sorted(codes_ja - codes_en)}")
    return w


# ---------------------------------------------------------------- design inventory
def design_inventory(src: Optional[str]) -> Dict[str, str]:
    """design.json（設計書 bot = tools/design-xlsx 形式）/ docs/{機能}/ 目录 / 設計書.xlsx から ID 一覧を作る"""
    if not src:
        return {}
    sys.path.insert(0, str(HERE))
    from read_design import inventory  # noqa
    return inventory(src)


# ---------------------------------------------------------------- OOXML helpers
_SHEETDATA_RE = re.compile(r"<sheetData\b[^>]*>.*?</sheetData>|<sheetData\s*/>", re.S)
_ROW_RE = re.compile(r"<row\b[^>]*?(?:/>|>.*?</row>)", re.S)


class SST:
    """sharedStrings: 既存 <si> は原文のまま保持し、新規文字列のみ追加する"""

    def __init__(self, xml: str):
        self.head = xml[: xml.index("<si")] if "<si" in xml else xml.replace("</sst>", "")
        self.raw: List[str] = re.findall(r"<si>.*?</si>|<si/>", xml, re.S)
        self.index: Dict[str, int] = {}
        for i, si in enumerate(self.raw):
            body = re.sub(r"<rPh\b.*?</rPh>", "", si, flags=re.S)
            txt = "".join(re.findall(r"<t[^>]*>(.*?)</t>", body, re.S))
            txt = txt.replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"').replace("&apos;", "'").replace("&amp;", "&")
            self.index.setdefault(txt, i)

    def add(self, s: str) -> int:
        if s in self.index:
            return self.index[s]
        sp = ' xml:space="preserve"' if (s != s.strip() or "\n" in s) else ""
        self.raw.append(f"<si><t{sp}>{escape(s)}</t></si>")
        self.index[s] = len(self.raw) - 1
        return self.index[s]

    def xml(self) -> bytes:
        head = re.sub(r'\scount="\d+"', f' count="{len(self.raw)}"', self.head, count=1)
        head = re.sub(r'\suniqueCount="\d+"', f' uniqueCount="{len(self.raw)}"', head, count=1)
        return (head + "".join(self.raw) + "</sst>").encode("utf-8")


def cell(ref: str, style: Optional[str], value=None, sst: Optional[SST] = None, formula: Optional[str] = None) -> str:
    a = f'r="{ref}"' + (f' s="{style}"' if style else "")
    if formula is not None:
        return f"<c {a}><f>{escape(formula)}</f></c>"
    if value is None or value == "":
        return f"<c {a}/>"
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return f"<c {a}><v>{value}</v></c>"
    return f'<c {a} t="s"><v>{sst.add(str(value))}</v></c>'


def col_widths(sheet_xml: str) -> Dict[str, float]:
    from openpyxl.utils import get_column_letter
    out = {}
    for m in re.finditer(r'<col\b[^>]*min="(\d+)"[^>]*max="(\d+)"[^>]*width="([\d.]+)"', sheet_xml):
        for i in range(int(m.group(1)), min(int(m.group(2)), 60) + 1):
            out[get_column_letter(i)] = float(m.group(3))
    return out


def est_height(values: Dict[str, str], widths: Dict[str, float], base: float = 11.0, minimum: float = 13.9) -> float:
    lines = 1
    for col, v in values.items():
        if v in (None, ""):
            continue
        wd = max(widths.get(col, 9.0), 3.0) * 0.9
        n = sum(max(1, math.ceil(disp_width(part) / wd)) for part in str(v).split("\n"))
        lines = max(lines, n)
    return max(minimum, round(lines * base + 4, 1))


def row(r: int, cells: List[str], ht: Optional[float] = None) -> str:
    h = f' ht="{ht}" customHeight="1"' if ht else ""
    return f'<row r="{r}"{h}>{"".join(cells)}</row>'


def header_rows(sheet_xml: str, upto: int) -> List[str]:
    m = _SHEETDATA_RE.search(sheet_xml)
    keep = []
    for rx in _ROW_RE.findall(m.group(0)):
        n = int(re.search(r'\br="(\d+)"', rx).group(1))
        if n <= upto:
            keep.append(rx)
    return keep


def rows_between(sheet_xml: str, lo: int, hi: int) -> List[Tuple[int, str]]:
    m = _SHEETDATA_RE.search(sheet_xml)
    out = []
    for rx in _ROW_RE.findall(m.group(0)):
        n = int(re.search(r'\br="(\d+)"', rx).group(1))
        if lo <= n <= hi:
            out.append((n, rx))
    return out


def shift_row(rx: str, old: int, new: int) -> str:
    rx = re.sub(rf'(<row\b[^>]*\br=")({old})(")', rf"\g<1>{new}\3", rx, count=1)
    return re.sub(rf'(<c\b[^>]*\br="[A-Z]+){old}(")', rf"\g<1>{new}\2", rx)


def set_sheet_data(sheet_xml: str, rows_xml: List[str]) -> str:
    return _SHEETDATA_RE.sub(lambda _: "<sheetData>" + "".join(rows_xml) + "</sheetData>", sheet_xml, count=1)


def set_dim(sheet_xml: str, ref: str) -> str:
    return re.sub(r'(<dimension\b[^>]*\bref=")[^"]+(")', rf"\g<1>{ref}\2", sheet_xml, count=1)


def set_dv(sheet_xml: str, formula1_contains: str, sqref: str, new_formula: Optional[str] = None) -> str:
    def rep(m):
        dv = m.group(0)
        if formula1_contains not in dv:
            return dv
        dv = re.sub(r'sqref="[^"]*"', f'sqref="{sqref}"', dv, count=1)
        if new_formula is not None:
            dv = re.sub(r"<formula1>.*?</formula1>", f"<formula1>{new_formula}</formula1>", dv, count=1)
        return dv
    return re.sub(r"<dataValidation\b[^>]*>.*?</dataValidation>", rep, sheet_xml, flags=re.S)


def set_x14_viewpoint_dv(sheet_xml: str, sqref: str) -> str:
    return re.sub(r"(<x14:dataValidation\b.*?試験観点!\$B\$3:\$B\$18.*?<xm:sqref>)[^<]*(</xm:sqref>)",
                  rf"\g<1>{sqref}\2", sheet_xml, count=1, flags=re.S)


def set_autofilter(sheet_xml: str, ref: str) -> str:
    return re.sub(r'(<autoFilter\b[^>]*\bref=")[^"]+(")', rf"\g<1>{ref}\2", sheet_xml, count=1)


def upsert(sheet_xml: str, r: int, col: str, cxml: str) -> str:
    ref = f"{col}{r}"
    m = re.search(rf'(<row\b[^>]*\br="{r}"[^>]*>)(.*?)(</row>)', sheet_xml, re.S)
    if not m:
        return sheet_xml.replace("</sheetData>", f'<row r="{r}">{cxml}</row></sheetData>', 1)
    body = m.group(2)
    cp = re.compile(rf'<c\b[^>]*\br="{ref}"[^>]*?(?:/>|>.*?</c>)', re.S)
    if cp.search(body):
        old = cp.search(body).group(0)
        sm = re.search(r'\bs="(\d+)"', old)
        if sm and ' s="' not in cxml:
            cxml = cxml.replace(f'r="{ref}"', f'r="{ref}" s="{sm.group(1)}"', 1)
        body = cp.sub(lambda _: cxml, body, count=1)
    else:
        body += cxml
    return sheet_xml[: m.start()] + m.group(1) + body + m.group(3) + sheet_xml[m.end():]


# ---------------------------------------------------------------- build sheets
def build_layout(xml: str, groups, sst: SST, trace: bool) -> Tuple[str, int, int, int]:
    widths = col_widths(xml)
    rows = header_rows(xml, 2)
    legend = rows_between(xml, 34, 57)
    r = 3
    first = last = 0
    count = 0
    for g in groups:
        rows.append(row(r, [cell(f"A{r}", LAYOUT_SECTION_STYLE, g["section"], sst)], 13.9))
        r += 1
        for c in g["cases"]:
            first = first or r
            vals = {"B": c.get("viewpoint"), "C": c.get("name"), "D": c.get("type", "TXT"),
                    "F": c.get("label") or c.get("name"), "H": c.get("font", "*"), "J": c.get("max_len", "-"),
                    "L": c.get("required", "-"), "N": c.get("align", "左"), "P": "-", "R": c.get("format", "-"),
                    "T": c.get("dtype", "-"), "V": c.get("note", "-")}
            if trace and c.get("ref"):
                vals["V"] = (vals["V"] if vals["V"] not in ("-", "") else "") + ("\n" if vals["V"] not in ("-", "") else "") + f"［{c['ref']}］"
            cells = [cell(f"A{r}", LAYOUT_STYLES["A"], formula=f"MAX(A$1:A{r-1})+1")]
            for col in ["B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L", "M", "N", "O", "P", "Q", "R", "S",
                        "T", "U", "V", "W", "X", "Y", "Z", "AA"]:
                cells.append(cell(f"{col}{r}", LAYOUT_STYLES[col], vals.get(col), sst))
            rows.append(row(r, cells, est_height(vals, widths)))
            last = r
            count += 1
            r += 1
    # legend
    leg_start = r + 1
    for old, rx in legend:
        rows.append(shift_row(rx, old, leg_start + (old - 34)))
    dt_first, dt_last = leg_start + (46 - 34), leg_start + (57 - 34)
    end = leg_start + (57 - 34)
    xml = set_sheet_data(xml, rows)
    xml = set_dim(xml, f"A1:AA{end}")
    first = first or 4
    last = last or 4
    rng = f"{first}:{last}"
    xml = set_dv(xml, '" ,OK,NG,NA"', f"Z{first}:Z{last}")
    xml = set_dv(xml, "$A$46:$A$56", f"D{first}:D{last}", f"$A${dt_first}:$A${dt_last}")
    xml = set_dv(xml, '"左,中,右,-"', f"N{first}:N{last}")
    xml = set_x14_viewpoint_dv(xml, f"B{first}:B{last}")
    return xml, count, first, last


def build_operation(xml: str, groups, sst: SST, trace: bool) -> Tuple[str, int, int, int]:
    widths = col_widths(xml)
    rows = header_rows(xml, 1)
    if trace:
        rows[0] = re.sub(r'<c r="M1"[^>]*?(?:/>|>.*?</c>)', "", rows[0]).replace(
            "</row>", cell("M1", "51", "設計書参照", sst) + "</row>")
    r = 2
    no = 1
    first = last = 0
    count = 0
    for g in groups:
        rows.append(row(r, [cell(f"A{r}", OP_SECTION_STYLE, g["section"], sst)], 13.9))
        r += 1
        for c in g["cases"]:
            first = first or r
            vals = {"A": no, "B": c.get("viewpoint"), "C": c.get("item"), "D": c.get("step"),
                    "E": c.get("branch", "-") or "-", "F": c.get("branch1", "-") or "-",
                    "G": c.get("branch2", "-") or "-", "H": c.get("expected")}
            cells = [cell(f"{col}{r}", OP_STYLES[col], vals.get(col), sst) for col in "ABCDEFGHIJKL"]
            if trace:
                cells.append(cell(f"M{r}", OP_STYLES["L"], c.get("ref") or g.get("ref"), sst))
            rows.append(row(r, cells, est_height({k: str(v) for k, v in vals.items() if k != "A"}, widths)))
            last = r
            no += 1
            count += 1
            r += 1
    first = first or 3
    last = last or 3
    lastcol = "M" if trace else "L"
    xml = set_sheet_data(xml, rows)
    xml = set_dim(xml, f"A1:{lastcol}{last}")
    xml = set_autofilter(xml, f"A1:{lastcol}{last}")
    xml = set_dv(xml, '" ,OK,NG,NA"', f"K{first}:K{last}")
    xml = set_x14_viewpoint_dv(xml, f"B{first}:B{last}")
    return xml, count, first, last


def build_check(xml: str, groups, sst: SST, trace: bool) -> Tuple[str, int, int, int]:
    widths = col_widths(xml)
    rows = header_rows(xml, 1)
    if trace:
        rows[0] = rows[0].replace("</row>", cell("L1", "85", "設計書参照", sst) + "</row>")
    r = 2
    first = last = 0
    count = 0
    for g in groups:
        if g.get("section"):
            rows.append(row(r, [cell(f"A{r}", OP_SECTION_STYLE, g["section"], sst)], 13.9))
            r += 1
        for c in g["cases"]:
            first = first or r
            vals = {"B": c.get("viewpoint"), "C": c.get("field"), "D": c.get("screen"),
                    "E": c.get("branch1"), "F": c.get("branch2", "-") or "-", "G": c.get("expected")}
            cells = [cell(f"A{r}", CHECK_STYLES["A"], formula=f"MAX(A$1:A{r-1})+1")]
            for col in "BCDEFGHIJK":
                cells.append(cell(f"{col}{r}", CHECK_STYLES[col], vals.get(col), sst))
            if trace:
                cells.append(cell(f"L{r}", CHECK_STYLES["K"], c.get("ref") or g.get("ref"), sst))
            rows.append(row(r, cells, est_height(vals, widths, minimum=22)))
            last = r
            count += 1
            r += 1
    first = first or 2
    last = last or 2
    lastcol = "L" if trace else "K"
    xml = set_sheet_data(xml, rows)
    xml = set_dim(xml, f"A1:{lastcol}{last}")
    xml = set_dv(xml, '" ,OK,NG,NA"', f"J{first}:J{last}")
    xml = set_x14_viewpoint_dv(xml, f"B{first}:B{last}")
    return xml, count, first, last


def patch_summary(xml: str, sst: SST, meta: dict, lr, orr, cr) -> str:
    for (r, col), v in {(1, "B"): meta.get("author", "AI"), (1, "D"): meta.get("created", ""),
                        (2, "B"): meta.get("updater", ""), (2, "D"): meta.get("updated", "")}.items():
        if v:
            xml = upsert(xml, r, col, cell(f"{col}{r}", None, v, sst))
    spec = {5: ("画面レイアウト判定", "B", "Z", lr), 6: ("画面操作処理判定", "B", "K", orr), 7: ("項目チェック判定", "B", "J", cr)}
    for r, (sh, bc, rc, (f, l)) in spec.items():
        fm = {"C": f'COUNTIF({sh}!${bc}${f}:${bc}${l},"<>")',
              "D": f"COUNTIF({sh}!${rc}${f}:${rc}${l},D$4)", "E": f"COUNTIF({sh}!${rc}${f}:${rc}${l},E$4)",
              "F": f"COUNTIF({sh}!${rc}${f}:${rc}${l},F$4)", "G": f"C{r}-D{r}-E{r}-F{r}", "H": f"IFERROR(G{r}/C{r},0)"}
        for col, formula in fm.items():
            xml = upsert(xml, r, col, cell(f"{col}{r}", None, formula=formula))
    for col in "CDEFG":
        xml = upsert(xml, 8, col, cell(f"{col}8", None, formula=f"SUM({col}5:{col}7)"))
    xml = upsert(xml, 8, "H", cell("H8", None, formula="IFERROR(G8/C8,0)"))
    return xml


def patch_workbook(xml: str, lay_end: int, op_last: int, chk_last: int, trace: bool) -> str:
    opc = "M" if trace else "L"
    chc = "L" if trace else "K"
    xml = re.sub(r"画面レイアウト判定!\$A\$2:\$AA\$\d+", f"画面レイアウト判定!$A$2:$AA${lay_end}", xml)
    xml = re.sub(r"画面操作処理判定!\$A\$1:\$L\$\d+", f"画面操作処理判定!$A$1:${opc}${op_last}", xml)
    xml = re.sub(r"(_FilterDatabase\" localSheetId=\"4\" hidden=\"1\">)項目チェック判定!\$A\$1:\$K\$\d+",
                 rf"\g<1>項目チェック判定!$A$1:${chc}${chk_last}", xml)
    xml = re.sub(r"(Print_Area\" localSheetId=\"4\">)項目チェック判定!\$A\$1:\$K\$\d+",
                 rf"\g<1>項目チェック判定!$A$1:${chc}${chk_last}", xml)
    if "fullCalcOnLoad" not in xml:
        xml = re.sub(r"<calcPr\b", '<calcPr fullCalcOnLoad="1"', xml, count=1)
    return xml


def write_xlsx(template: Path, out: Path, meta, layout, operation, check, trace=False) -> Dict[str, int]:
    with zipfile.ZipFile(template) as z:
        files = {n: z.read(n) for n in z.namelist()}
        infos = {i.filename: i for i in z.infolist()}
    sst = SST(files["xl/sharedStrings.xml"].decode("utf-8"))
    lx, ln, lf, ll = build_layout(files[SHEET_FILES["layout"]].decode("utf-8"), layout, sst, trace)
    ox, on, of, ol = build_operation(files[SHEET_FILES["operation"]].decode("utf-8"), operation, sst, trace)
    cx, cn, cf, cl = build_check(files[SHEET_FILES["check"]].decode("utf-8"), check, sst, trace)
    files[SHEET_FILES["layout"]] = lx.encode("utf-8")
    files[SHEET_FILES["operation"]] = ox.encode("utf-8")
    files[SHEET_FILES["check"]] = cx.encode("utf-8")
    files[SHEET_FILES["summary"]] = patch_summary(files[SHEET_FILES["summary"]].decode("utf-8"), sst, meta,
                                                  (lf, ll), (of, ol), (cf, cl)).encode("utf-8")
    lay_end = int(re.search(r'<dimension ref="A1:AA(\d+)"', lx).group(1))
    files["xl/workbook.xml"] = patch_workbook(files["xl/workbook.xml"].decode("utf-8"), lay_end, ol, cl, trace).encode("utf-8")
    files["xl/sharedStrings.xml"] = sst.xml()
    # stale calcChain
    files.pop("xl/calcChain.xml", None)
    files["[Content_Types].xml"] = re.sub(rb'<Override\s+[^>]*PartName="/xl/calcChain\.xml"[^>]*/>', b"", files["[Content_Types].xml"])
    files["xl/_rels/workbook.xml.rels"] = re.sub(rb'<Relationship\s+[^>]*calcChain[^>]*/>', b"", files["xl/_rels/workbook.xml.rels"])
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(".tmp.xlsx")
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zo:
        for n, data in files.items():
            zi = zipfile.ZipInfo(n, date_time=infos[n].date_time if n in infos else (2026, 1, 1, 0, 0, 0))
            zi.compress_type = zipfile.ZIP_DEFLATED
            zo.writestr(zi, data)
    shutil.move(tmp, out)
    # 固定 sheet 字节一致
    with zipfile.ZipFile(template) as zt, zipfile.ZipFile(out) as zo:
        for f in FIXED_FILES:
            assert zt.read(f) == zo.read(f), f"{f} が変更された（試験観点 / DB書き込み判定 は固定）"
    return {"layout": ln, "operation": on, "check": cn}


def verify(out: Path) -> List[str]:
    """openpyxl で再読込して構造を確認"""
    import warnings
    import openpyxl
    warnings.simplefilter("ignore")
    errs = []
    wb = openpyxl.load_workbook(out)
    names = [ws.title for ws in wb.worksheets]
    exp = ["試験観点", "項目総計", "画面レイアウト判定", "画面操作処理判定", "項目チェック判定", "DB書き込み判定"]
    if names != exp:
        errs.append(f"sheet 構成が違う: {names}")
    if wb["DB書き込み判定"].sheet_state != "hidden":
        errs.append("DB書き込み判定 が hidden でない")
    hdr = [wb["画面操作処理判定"].cell(1, i).value for i in range(1, 13)]
    if hdr != ["番号", "試験観点", "試験項目", "処理ステップ", "分岐", "分岐明細１", "分岐明細２", "予想結果", "判定履歴", "担当者", "最新結果", "BUG票ID"]:
        errs.append(f"画面操作処理判定 ヘッダー異常: {hdr}")
    return errs


def configure(cfg: dict) -> None:
    """項目配置を反映する（init_project.py の自検からも呼ぶ）"""
    global CODE_RE
    CFG.clear()
    CFG.update(cfg)
    LANGS[:] = list(cfg["i18n"]["languages"])
    CODE_RE = re.compile(rf"(?:{cfg['ids']['error_code']})")
    import read_design
    read_design.configure(cfg)


def _resolve_template(arg: Optional[str]) -> Path:
    """--template ＞ unit_test.template（絶対パス、またはカレント→規則リポジトリのルートの順に相対解決。
    指定したのに見つからなければエラー）＞ このツールの templates/ ＞ docs/ai-native/"""
    if arg:
        return Path(arg)
    t = str(CFG.get("unit_test", {}).get("template") or "").strip()
    if t:
        p = Path(t).expanduser()
        for c in ([p] if p.is_absolute() else [p, HERE.parents[2] / p]):
            if c.exists():
                return c
        sys.exit(f"ERROR: unit_test.template のテンプレートが見つからない: {t}（init.sh で直すか --template で指定）")
    for c in TEMPLATE_CANDIDATES:
        if c.exists():
            return c
    sys.exit(f"テンプレートが見つからない: {', '.join(map(str, TEMPLATE_CANDIDATES))}（--template で指定）")


def _resolve_locale(arg: Optional[str]) -> Optional[Path]:
    """--locale-dir ＞ i18n.locale_dir（カレント＝プロジェクトのルートからの相対）。無ければ None（文言は要確認になる）"""
    if arg:
        return Path(arg)
    d = Path(CFG["i18n"]["locale_dir"])
    return d if d.is_dir() else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cases", nargs="?")
    ap.add_argument("-o", "--out")
    ap.add_argument("--design", help="design.json / docs/{機能}/ / 設計書.xlsx（カバレッジ確認用）")
    ap.add_argument("--config", help="init.sh で生成した project.json（必須）")
    ap.add_argument("--locale-dir", help="locale ディレクトリ（省略時 i18n.locale_dir）")
    ap.add_argument("--template", help="テンプレート xlsx（省略時 unit_test.template → templates/ → docs/ai-native/）")
    ap.add_argument("--trace-col", action="store_true", help="操作/チェック sheet 右端に『設計書参照』列を追加（テンプレ外拡張・既定 OFF）")
    ap.add_argument("--strict", action="store_true", help="lint 警告があれば exit 1")
    ap.add_argument("--lint-only", action="store_true")
    ap.add_argument("--schema", action="store_true")
    ap.add_argument("--trace-report", help="ref → Case 対応表を Markdown で出力")
    a = ap.parse_args()
    if a.schema:
        print(json.dumps(SCHEMA, ensure_ascii=False, indent=2))
        return
    configure(project_config.load(a.config, "unit_test"))
    data = json.loads(Path(a.cases).read_text(encoding="utf-8"))
    meta = data.get("meta", {})
    loc = Locale(_resolve_locale(a.locale_dir))
    warns: List[str] = []
    layout = data.get("layout", [])
    operation = data.get("operation", [])
    check = expand_check_cases(data.get("check", []), loc, warns)
    warns += lint(data, layout, operation, check, design_inventory(a.design), meta.get("lang", LANGS[0]), loc)
    counts = None
    if not a.lint_only:
        out = Path(a.out or f"単体テスト項目_{meta.get('feature','機能')}.xlsx")
        counts = write_xlsx(_resolve_template(a.template), out, meta, layout, operation, check, a.trace_col)
        errs = verify(out)
        print(f"Generated: {out}")
        print(f"  画面レイアウト判定: {counts['layout']}  画面操作処理判定: {counts['operation']}  項目チェック判定: {counts['check']}"
              f"  合計: {sum(counts.values())}")
        for e in errs:
            print("ERROR:", e)
        if errs:
            sys.exit(2)
    if a.trace_report:
        lines = ["| ref | sheet | Case |", "|---|---|---|"]
        for nm, groups, key in (("画面レイアウト判定", layout, "name"), ("画面操作処理判定", operation, "item"), ("項目チェック判定", check, "field")):
            for g in groups:
                for c in g["cases"]:
                    lines.append(f"| {c.get('ref') or g.get('ref') or ''} | {nm} | {c.get(key,'')} / {c.get('branch1') or c.get('step') or c.get('label') or ''} |")
        Path(a.trace_report).write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"lint: {len(warns)} 件")
    for x in warns:
        print("  WARN", x)
    if a.strict and warns:
        sys.exit(1)


if __name__ == "__main__":
    main()
