#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""単体テスト項目 xlsx 生成 + lint（テンプレート xlsx を OOXML 最小修改）

用法:
  python3 gen_ut_xlsx.py cases.json --config project.json -o docs/{機能}/単体テスト項目_{機能}.xlsx
                         [--design docs/{機能}/ [API設計書_x.xlsx 画面設計書_x.xlsx ...]]
                         [--template テンプレート.xlsx] [--locale-dir frontend/src/locale]
                         [--trace-report trace.md] [--strict] [--trace-col]
  python3 gen_ut_xlsx.py --schema               # cases.json の骨架を表示
  python3 gen_ut_xlsx.py --lint-only cases.json --config project.json [--design ...]
  --config（init.sh で生成した項目配置）は必須。錯誤码格式・locale 目录・语言・各语言文件/文言格式/语言名都从这里取，
  没有配置、示例配置（_example）、缺键、占位符一律报错退出。

設計要点（.cursor/rules/unit-test-case-docs.mdc と一致させる）:
  * テンプレート xlsx を底にし、ZIP 成員は原样コピー。置き換えるのは
    画面レイアウト判定 / 画面操作処理判定 / 項目チェック判定 の sheetData と 項目総計 の一部セルだけ
    （openpyxl で読んで保存し直す「整本重存」はしない＝拡張データ入力規則（下拉）が消えないように）。
  * 試験観点 sheet・隠し sheet DB書き込み判定 はバイト単位で不変（生成後に検証）。
  * sharedStrings は既存 <si>（振り仮名 rPh 含む）を保持し、新しい文字列だけ追加。
  * Case 行数がテンプレートの予約行を超えても、入力規則（最新結果 / 試験観点 / 表示タイプ / 詰め方）、
    オートフィルタ、_FilterDatabase / Print_Area、項目総計 の COUNTIF 範囲を実際の行に合わせて伸縮する。
    calcChain は削除し、開いたとき全再計算。
  * 生成後に openpyxl で読み直し、sheet 構成・隠し状態・項目総計の範囲と CASE 数を実際の行数で照合する。
  * 依存: 標準ライブラリ + openpyxl。
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
# [CMPF] 模板：模板文件名「単体テスト項目_テンプレート.xlsx」和后备位置 docs/ai-native/ 是 CMPF 仓库的约定
TEMPLATE_NAME = "単体テスト項目_テンプレート.xlsx"
# テンプレートの探索順: --template > このツールの templates/ > カレントの docs/ai-native/
TEMPLATE_CANDIDATES = [HERE.parent / "templates" / TEMPLATE_NAME, Path("docs") / "ai-native" / TEMPLATE_NAME]
# locale 目录・语言・文件名・错误码格式全部取自 --config 的项目配置（i18n.locale_dir / i18n.languages /
# unit_test.locale_files / ids.error_code），不回落任何项目的默认值。--locale-dir 只覆盖目录。
CFG: dict = {}
LANGS: List[str] = []          # i18n.languages。先頭が本文言語（多言語対応チェック以外の行）

# [CMPF] 模板：試験観点 16 词・表示タイプ・詰め方 取自 CMPF 单体模板的 試験観点 sheet 和 画面レイアウト判定 凡例
VIEWPOINTS = [
    "画面レイアウト", "分岐網羅", "設定値", "データパターン", "境界値", "初期化チェック",
    "ロールチェック", "NULL値チェック", "デグレ試験", "性能改善対応", "他システム連携IF",
    "例外処理の網羅", "タイムアウト処理", "多言語対応チェック", "非同期処理チェック", "セッション・認証処理",
]
DISPLAY_TYPES = ["TT", "BTN", "LBL", "DRP", "TXT", "RBT", "CHK", "INP", "CMB", "TBL", "IB", "LNK"]
ALIGN = ["左", "中", "右", "-"]
VAGUE = {"正常", "正常に動作する", "正常終了", "正しく動作する", "問題ない", "問題なし", "OK", "仕様通り",
         "設計通り", "想定通り", "同上", "正常に表示される", "正常に処理される", "成功", "可", "可能", "できる",
         "許可", "許可される", "NG にならない"}
# [CMPF] 正文语言：Case 正文要求日文；ZH_ONLY 用于 meta.lang=ja 时检出简体中文混入（见 lint 的 text_checks）
ZH_ONLY = set("这们为没时后对个说么样还过从让发录删页确认击选择据项请显隐设输键钮创该页时间应")
# メッセージコードの書式は項目配置 ids.error_code（configure() で設定）。Locale 読取・言語別展開・言語行チェックで共用
CODE_RE: "re.Pattern" = None  # type: ignore[assignment]
# [CMPF] ID 写法：BR-/AC-/Q- 是 CMPF 设计书的编号约定；将来 ID 规则只在 project.json 定义一份，设计书和单体 case 两个工具共读
TRACE_RE = re.compile(r"(?<![\w-])(?:BR|AC|Q)-(?:[A-Z]{1,6}-)?\d{1,3}(?![\w-])")
ANY_ID_RE = re.compile(r"(?<![\w-])[A-Z]{1,4}-[\w-]*\d(?![\w-])")
VERIFY_VALUES = {"JUnit", "結合", "手動"}
FUNC_RE = re.compile(r"\b[a-z]+[A-Z][A-Za-z0-9]*\s*\(|\b\w+\.(java|vue|ts|tsx|xml)\b|src/main/|src/views/")

# 样式 ID（取自模板数据行，同仓库 scripts/ooxml_unit_test_workbook.py）
# [CMPF] 模板：以下样式 ID 是 CMPF 单体模板 styles.xml 的 cellXfs 编号（按列 A〜AA / A〜L / A〜K），换模板必须重取
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

# [CMPF] 模板：6 个 sheet 的 XML 位置按 CMPF 模板顺序写死（sheet1 試験観点 / sheet2 項目総計 / sheet3〜5 三个 Case sheet / sheet6 DB書き込み判定）
SHEET_FILES = {"summary": "xl/worksheets/sheet2.xml", "layout": "xl/worksheets/sheet3.xml",
               "operation": "xl/worksheets/sheet4.xml", "check": "xl/worksheets/sheet5.xml"}
FIXED_FILES = ["xl/worksheets/sheet1.xml", "xl/worksheets/sheet6.xml"]  # 試験観点 / DB書き込み判定

SCHEMA = {
    "_comment": "サンプル骨架（架空）。値はすべて置き換えること",
    "meta": {"feature": "{機能}", "author": "", "created": "YYYY-MM-DD", "updater": "", "updated": "",
             "design_doc": "docs/{機能}/", "lang": "ja"},
    "layout": [{"section": "【SCR-xxx 画面名】エリア名", "ref": "SCR-xxx", "cases": [
        {"viewpoint": "画面レイアウト", "name": "項目名", "type": "BTN", "label": "ラベル表示内容（画面文言そのまま）",
         "max_len": "-", "required": "-", "align": "左", "format": "-", "dtype": "-", "note": "特記事項（判定できる補足）",
         "ref": "SCR-xxx / BR-xx / AC-xx", "verify": "結合"}]}],
    "operation": [{"section": "【SCR-xxx / API-xxx】シナリオ", "ref": "API-xxx", "cases": [
        {"viewpoint": "分岐網羅", "item": "試験項目", "step": "処理ステップ（操作）", "branch": "分岐（条件）",
         "branch1": "-", "branch2": "-", "expected": "予想結果（画面表示・値・DB 結果を具体的に）",
         "ref": "BR-xx / AC-xx / Q-xx", "verify": "JUnit"}]}],
    "check": [{"section": "【SCR-xxx】入力チェック", "ref": "SCR-xxx", "cases": [
        {"viewpoint": "境界値", "field": "項目名", "screen": "画面名", "branch1": "入力値・条件",
         "branch2": "-", "expected": "予想結果", "ref": "BR-xx"},
        {"viewpoint": "例外処理の網羅", "field": "項目名", "screen": "画面名", "branch1": "未入力",
         "code": "XXXX0000-E", "pair": True, "ref": "AC-xx",
         "_comment": "code 指定時は locale から文言を引き、日本語行＋英語行（多言語対応チェック）を自動展開"}]}],
}


# ---------------------------------------------------------------- locale
class Locale:
    """i18n.languages の各言語について unit_test.locale_files を読み、{言語: {コード: 文言}} を作る"""

    def __init__(self, d: Optional[Path]):
        self.msgs: Dict[str, Dict[str, str]] = {lang: {} for lang in LANGS}
        if not d:
            return
        body = CFG["ids"]["error_code"]
        pat = re.compile(rf"'(?P<code>{body})'\s*:\s*(?:'(?P<v1>(?:\\'|[^'])*)'|\n\s*'(?P<v2>(?:\\'|[^'])*)')", re.M)
        fn = re.compile(rf"'(?P<code>{body})'\s*:\s*\(\{{[^}}]*\}}\)\s*=>\s*`(?P<v>[^`]*)`")
        for lang in LANGS:
            target = self.msgs[lang]
            for rel in CFG["unit_test"]["locale_files"][lang]:
                p = d / rel
                if not p.exists():
                    continue
                text = p.read_text(encoding="utf-8")
                for m in fn.finditer(text):
                    target.setdefault(m.group("code"), re.sub(r"\$\{[^}]*\}", "{0}", m.group("v")))
                for m in pat.finditer(text):
                    v = (m.group("v1") or m.group("v2") or "").replace("\\'", "'")
                    if v and not v.startswith("(") and m.group("code") not in target:
                        target[m.group("code")] = v

    @property
    def primary(self) -> Dict[str, str]:
        return self.msgs[LANGS[0]]

    def msg(self, code: str, lang: str, param: Optional[str] = None) -> Optional[str]:
        raw = self.msgs.get(lang, {}).get(code)
        if raw is None:
            return None
        if param is not None:
            raw = raw.replace("{0}", param)
        return raw


def _msg_text(lang: str, text: str, code: str) -> str:
    return CFG["unit_test"]["error_message_templates"][lang].replace("{code}", code).replace("{text}", text)


def _label(lang: str) -> str:
    return CFG["unit_test"]["language_labels"][lang]


# ---------------------------------------------------------------- case normalisation
# code 行は i18n.languages の順に展開する：先頭言語の行（分岐2＝その言語名）＋ 残りの言語ごとに 多言語対応チェック 行。
# 文言の書式は unit_test.error_message_templates、言語名は unit_test.language_labels。"pair": false なら先頭言語の行だけ。
def expand_check_cases(groups: List[dict], loc: Locale, warnings: List[str]) -> List[dict]:
    out = []
    first, others = LANGS[0], LANGS[1:]
    for g in groups:
        rows = []
        for c in g.get("cases", []):
            code = c.get("code")
            if code and not c.get("expected"):
                txt = loc.msg(code, first, c.get(f"param_{first}", c.get("param")))
                if txt is None:
                    warnings.append(f"[check] {code} の {first} 文言が locale に無い（expected を手書きするか locale を確認）")
                    txt = "（文言要確認）"
                base = dict(c)
                base["branch2"] = c.get("branch2") or _label(first)
                base["expected"] = _msg_text(first, txt, code)
                rows.append(base)
                if c.get("pair", True):
                    for lang in others:
                        t = loc.msg(code, lang, c.get(f"param_{lang}", c.get("param")))
                        if t is None:
                            warnings.append(f"[check] {code} の {lang} 文言が locale に無い")
                            t = "(message TBD)"
                        e = dict(c)
                        e["viewpoint"] = "多言語対応チェック"
                        e["branch2"] = _label(lang)
                        e["expected"] = _msg_text(lang, t, code)
                        rows.append(e)
            else:
                rows.append(c)
        out.append({"section": g.get("section"), "ref": g.get("ref"), "cases": rows})
    return out


# ---------------------------------------------------------------- lint
def disp_width(s: str) -> int:
    return sum(2 if unicodedata.east_asian_width(ch) in "WFA" else 1 for ch in s)


def lint(data: dict, layout, operation, check, design_ids: Optional[Dict[str, str]], lang: str,
         loc: Optional["Locale"] = None, withdrawn: Optional[Dict[str, str]] = None) -> List[str]:
    w: List[str] = []
    seen = set()

    def text_checks(where: str, c: dict, fields: List[str]):
        for f in fields:
            v = str(c.get(f, "") or "")
            if FUNC_RE.search(v):
                w.append(f"{where}: 「{f}」に関数名/ファイルパスらしき記述 → 業務語で書く（{v[:40]}）")
            # [CMPF] 正文语言：meta.lang=ja 时检查简体中文混入（label 是画面原文，不查）
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
    for must in ("画面レイアウト", "分岐網羅") + (("多言語対応チェック",) if len(LANGS) > 1 else ()):
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
    # トレース: 各 Case に BR/AC（未確定なら Q）が付いているか（unit-test-case-docs.mdc「写法」）
    no_trace, bad_verify, no_verify, used_withdrawn = [], [], 0, set()
    for kind, c, g in allcases:
        refs = f"{c.get('ref') or ''} {g.get('ref') or ''} {g.get('section') or ''}"
        if not TRACE_RE.search(refs):
            no_trace.append(str(c.get("name") or c.get("item") or c.get("field") or "?"))
        for i in ANY_ID_RE.findall(refs):
            # 「BR-nn 欠番」のように欠番であること自体を確認する Case は対象外
            if withdrawn and i in withdrawn and not re.search(rf"{re.escape(i)}\s*[（(【]?\s*(?:欠番|撤回|廃止)", refs):
                used_withdrawn.add(i)
        v = c.get("verify")
        if v in (None, ""):
            no_verify += 1
        elif v not in VERIFY_VALUES:
            bad_verify.append(str(v))
    if no_trace:
        w.append(f"[trace] BR/AC/Q の付いていない Case {len(no_trace)}件（例: {'、'.join(no_trace[:5])}）")
    if used_withdrawn:
        w.append(f"[trace] 欠番（撤回済み）の ID を参照している: {sorted(used_withdrawn)} → 欠番は再利用しない")
    if bad_verify:
        w.append(f"[verify] verify は {sorted(VERIFY_VALUES)} のいずれか: {sorted(set(bad_verify))}")
    if no_verify:
        w.append(f"[verify] JUnit で覆うか結合（联调）でしか確認できないかが未指定の Case {no_verify}件（verify 欄）")
    # 多言語: 先頭言語のエラーコード Case ごとに、残りの各言語の 多言語対応チェック Case が要る（i18n.languages）。
    # 多言語行の言語は 分岐2 の言語名（unit_test.language_labels）で判定。2 言語構成なら多言語行はすべて 2 番目の言語。
    multi = [c for _, c, _ in allcases if c.get("viewpoint") == "多言語対応チェック"]
    codes_first = set(CODE_RE.findall("\n".join(str(c.get("expected", "")) for _, c, _ in allcases if c.get("viewpoint") != "多言語対応チェック")))
    others = LANGS[1:]
    for lang in others:
        rows = multi if len(others) == 1 else [c for c in multi if str(c.get("branch2") or "").strip() == _label(lang)]
        codes_l = set(CODE_RE.findall("\n".join(str(c.get("expected", "")) for c in rows)))
        if codes_first - codes_l:
            w.append(f"[coverage] {_label(lang)}（多言語対応チェック）Case が無いエラーコード: {sorted(codes_first - codes_l)}")
    return w


# ---------------------------------------------------------------- design inventory
def design_inventory(srcs: Optional[List[str]]):
    """設計書（中間 JSON / API設計書・画面設計書 xlsx / docs/{機能}/ の MD）から ID 一覧と欠番を得る"""
    if not srcs:
        return {}, {}, []
    sys.path.insert(0, str(HERE))
    from read_design import load, configure  # noqa
    configure(CFG)
    inv = load(list(srcs))
    print(f"design: mode={inv.mode}（json=中間 JSON / xlsx+md=設計書 xlsx と MD）読込 {len(inv.sources)} 件、"
          f"Case 必須 ID {len(inv.as_dict())} 件、欠番 {len(inv.withdrawn)} 件")
    return inv.as_dict(), dict(inv.withdrawn), [f"[design] {x}" for x in inv.warnings]


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
# [CMPF] 模板：画面レイアウト判定 表头 2 行、Case 从第 3 行起、A〜AA 列；凡例在模板第 34〜57 行（表示タイプ一覧 46〜57 行），按 CMPF 模板写死
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


# [CMPF] 模板：画面操作処理判定 表头 1 行、A〜L 列（番号/試験観点/試験項目/処理ステップ/分岐/分岐明細１/分岐明細２/予想結果/判定履歴/担当者/最新結果/BUG票ID），最新結果=K 列
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


# [CMPF] 模板：項目チェック判定 表头 1 行、A〜K 列（B 試験観点/C 項目名/D 画面/E 分岐1/F 分岐2/G 予想結果/J 最新結果）
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


# [CMPF] 模板：項目総計 B1/D1/B2/D2=作成者・作成日・更新者・更新日，第 5〜7 行对应三个 Case sheet（最新結果列 Z/K/J），第 8 行合计
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


# [CMPF] 模板：命名范围 _FilterDatabase / Print_Area 的 localSheetId 和列范围（$A$2:$AA / $A$1:$L / $A$1:$K）按 CMPF 模板写死
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
    return ({"layout": ln, "operation": on, "check": cn},
            {"layout": (lf, ll), "operation": (of, ol), "check": (cf, cl)})


def _range_rows(formula: str) -> Optional[Tuple[int, int]]:
    m = re.search(r"\$[A-Z]+\$(\d+):\$[A-Z]+\$(\d+)", formula or "")
    return (int(m.group(1)), int(m.group(2))) if m else None


def _sqref_covers(sqrefs: List[str], col: str, first: int, last: int) -> bool:
    for sq in sqrefs:
        for part in sq.split():
            m = re.fullmatch(rf"{col}(\d+)(?::{col}(\d+))?", part)  # 1 行だけだと "K3" になる
            if m and int(m.group(1)) <= first and int(m.group(2) or m.group(1)) >= last:
                return True
    return False


def verify(out: Path, counts: Optional[Dict[str, int]] = None, spans: Optional[Dict[str, Tuple[int, int]]] = None) -> List[str]:
    """openpyxl で読み直して構造と CASE 数を確認（保存はしない）"""
    import warnings
    import openpyxl
    warnings.simplefilter("ignore")
    errs = []
    wb = openpyxl.load_workbook(out)
    names = [ws.title for ws in wb.worksheets]
    # [CMPF] 模板：自检用的 sheet 名・顺序・隐藏 sheet・画面操作処理判定 表头文字・項目総計 行号 按 CMPF 模板写死
    exp = ["試験観点", "項目総計", "画面レイアウト判定", "画面操作処理判定", "項目チェック判定", "DB書き込み判定"]
    if names != exp:
        errs.append(f"sheet 構成が違う: {names}")
        return errs
    if wb["DB書き込み判定"].sheet_state != "hidden":
        errs.append("DB書き込み判定 が hidden でない")
    hdr = [wb["画面操作処理判定"].cell(1, i).value for i in range(1, 13)]
    if hdr != ["番号", "試験観点", "試験項目", "処理ステップ", "分岐", "分岐明細１", "分岐明細２", "予想結果", "判定履歴", "担当者", "最新結果", "BUG票ID"]:
        errs.append(f"画面操作処理判定 ヘッダー異常: {hdr}")
    if counts is None:
        return errs
    # 項目総計 の COUNTIF 範囲と実際の Case 行を照合
    summ = wb["項目総計"]
    spec = {5: ("layout", "画面レイアウト判定", "Z"), 6: ("operation", "画面操作処理判定", "K"), 7: ("check", "項目チェック判定", "J")}
    for r, (key, sh, rc) in spec.items():
        ws = wb[sh]
        rng = _range_rows(str(summ[f"C{r}"].value))
        # Case 行＝B 列が 試験観点 の16項目のどれかである行（凡例・ヘッダーは除外される）
        actual = sum(1 for i in range(1, ws.max_row + 1) if ws.cell(i, 2).value in VIEWPOINTS)
        if rng is None:
            errs.append(f"項目総計!C{r} の COUNTIF 範囲が読めない: {summ[f'C{r}'].value}")
            continue
        in_rng = sum(1 for i in range(rng[0], rng[1] + 1) if ws.cell(i, 2).value not in (None, ""))
        if counts[key] and in_rng != counts[key]:
            errs.append(f"{sh}: 項目総計の範囲 {rng} 内の Case {in_rng} 件 ≠ 生成 {counts[key]} 件")
        if counts[key] and actual != counts[key]:
            errs.append(f"{sh}: シート上の Case 行 {actual} 件 ≠ 生成 {counts[key]} 件（範囲外に Case 行がある）")
        if spans and counts[key]:
            f, l = spans[key]
            if rng != (f, l):
                errs.append(f"{sh}: 項目総計の範囲 {rng} ≠ Case 行 {f}-{l}")
            sq = [str(dv.sqref) for dv in ws.data_validations.dataValidation]
            if not _sqref_covers(sq, rc, f, l):
                errs.append(f"{sh}: 最新結果（{rc}列）の下拉が Case 行 {f}-{l} を覆っていない")
    return errs


def _resolve_template(arg: Optional[str]) -> Path:
    if arg:
        return Path(arg)
    for c in TEMPLATE_CANDIDATES:
        if c.exists():
            return c
    sys.exit(f"テンプレートが見つからない: {', '.join(map(str, TEMPLATE_CANDIDATES))}（--template で指定）")


def _resolve_locale(arg: Optional[str]) -> Optional[Path]:
    """--locale-dir ＞ 項目配置 i18n.locale_dir（カレント＝プロジェクトのルートからの相対）。見つからなければ None"""
    if arg:
        return Path(arg)
    d = Path(CFG["i18n"]["locale_dir"])
    return d if d.exists() else None


def configure(cfg: dict) -> None:
    global CODE_RE
    CFG.clear()
    CFG.update(cfg)
    LANGS[:] = list(cfg["i18n"]["languages"])
    CODE_RE = re.compile(rf"(?<![\w-])(?:{cfg['ids']['error_code']})(?![\w-])")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cases", nargs="?", help="cases.json")
    ap.add_argument("-o", "--out", help="出力 xlsx（既定: ./単体テスト項目_{meta.feature}.xlsx）")
    ap.add_argument("--design", nargs="+", metavar="SRC",
                    help="設計書（docs/{機能}/、API設計書_*.xlsx、画面設計書_*.xlsx、中間 JSON。複数可）→ ID カバレッジ確認")
    ap.add_argument("--config", help="項目配置 project.json（init.sh で生成。必須。--schema 以外）")
    ap.add_argument("--locale-dir", help="メッセージ定義のディレクトリ（省略時は項目配置の i18n.locale_dir）")
    ap.add_argument("--template", help=f"テンプレート xlsx（省略時 {TEMPLATE_CANDIDATES[0].parent.name}/ → docs/ai-native/）")
    ap.add_argument("--trace-col", action="store_true", help="操作/チェック sheet 右端に『設計書参照』列を追加（テンプレ外拡張・既定 OFF）")
    ap.add_argument("--strict", action="store_true", help="lint 警告があれば exit 1")
    ap.add_argument("--lint-only", action="store_true", help="xlsx を作らず lint だけ")
    ap.add_argument("--schema", action="store_true", help="cases.json の骨架を表示")
    ap.add_argument("--trace-report", help="ref → Case 対応表を Markdown で出力")
    a = ap.parse_args()
    if a.schema:
        print(json.dumps(SCHEMA, ensure_ascii=False, indent=2))
        return
    sys.path.insert(0, str(HERE.parents[1]))
    import project_config  # tools/project_config.py
    configure(project_config.load(a.config, "unit_test"))
    if not a.cases:
        ap.error("cases.json を指定してください")
    data = json.loads(Path(a.cases).read_text(encoding="utf-8"))
    meta = data.get("meta", {})
    loc_dir = _resolve_locale(a.locale_dir)
    loc = Locale(loc_dir)
    warns: List[str] = []
    if loc_dir is None and any(c.get("code") for g in data.get("check", []) for c in g.get("cases", [])):
        warns.append(f"[locale] locale（{CFG['i18n']['locale_dir']}）が見つからない → code 行の文言が引けない（--locale-dir を指定）")
    layout = data.get("layout", [])
    operation = data.get("operation", [])
    check = expand_check_cases(data.get("check", []), loc, warns)
    ids, withdrawn, dwarn = design_inventory(a.design)
    warns += dwarn
    warns += lint(data, layout, operation, check, ids, meta.get("lang", "ja"), loc, withdrawn)
    if not a.lint_only:
        template = _resolve_template(a.template)
        out = Path(a.out or f"単体テスト項目_{meta.get('feature') or '機能'}.xlsx")
        counts, spans = write_xlsx(template, out, meta, layout, operation, check, a.trace_col)
        errs = verify(out, counts, spans)
        print(f"Generated: {out}")
        print(f"  画面レイアウト判定: {counts['layout']}  画面操作処理判定: {counts['operation']}  項目チェック判定: {counts['check']}"
              f"  合計: {sum(counts.values())}")
        for e in errs:
            print("ERROR:", e)
        if errs:
            sys.exit(2)
        print("  自検 OK: sheet 構成 / 隠し状態 / 項目総計の範囲・CASE 数 / 下拉範囲")
    if a.trace_report:
        lines = ["| ref | sheet | Case | verify |", "|---|---|---|---|"]
        for nm, groups, key in (("画面レイアウト判定", layout, "name"), ("画面操作処理判定", operation, "item"), ("項目チェック判定", check, "field")):
            for g in groups:
                for c in g["cases"]:
                    lines.append(f"| {c.get('ref') or g.get('ref') or ''} | {nm} | {c.get(key,'')} / "
                                 f"{c.get('branch1') or c.get('step') or c.get('label') or ''} | {c.get('verify') or ''} |")
        Path(a.trace_report).write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"lint: {len(warns)} 件")
    for x in warns:
        print("  WARN", x)
    if a.strict and warns:
        sys.exit(1)


if __name__ == "__main__":
    main()
