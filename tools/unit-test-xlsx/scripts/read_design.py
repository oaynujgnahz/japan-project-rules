#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""设计书读取助手（単体テスト Case 用）

  python3 read_design.py <src> --ids --config project.json   # 列出需要被 Case 覆盖的 ID（画面/API/BR/AC/错误码）
  python3 read_design.py <design.json> --draft -o draft.cases.json --config project.json [--feature 機能名]
                                                  # 从设计 JSON 起草 Case 骨架（再由人/agent 补充、精修）
  python3 read_design.py <src> --dump             # 把设计书正文转成纯文本（MD 目录 / xlsx 都可），方便阅读

--config 是 init.sh 生成的 project.json：错误码按 ids.error_code，画面 / API ID 按 ids.screen_id / ids.api_id 抽取。
gen_ut_xlsx.py 经由调用时自动设定。

<src> 可以是：
  * 设计书 bot（tools/design-xlsx/gen_design_xlsx.py）的 design.json
  * 仓库 docs/{機能}/ 目录（README / 詳細設計書 / 06_画面設計書 / 07_API設計書 / 验收标准 / openapi.yaml）
  * cmpf-design-doc-xlsx 生成的 設計書.xlsx 或仓库里的任意设计书 xlsx
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # tools/project_config.py
import project_config  # noqa: E402

CODE_REGEX = None  # configure() で ids.error_code
ID_PATTERNS: list = []
LANGS: list = []        # i18n.languages（先頭＝正文語）
LANG_LABELS: dict = {}  # unit_test.language_labels（--draft の多言語 Case の備考）


def configure(cfg: dict) -> None:
    """項目配置を反映する（ids.screen_id / ids.api_id / ids.error_code）。gen_ut_xlsx.py からも呼ぶ。"""
    global CODE_REGEX
    ids = cfg["ids"]
    LANGS[:] = list(cfg["i18n"]["languages"])
    LANG_LABELS.clear()
    LANG_LABELS.update({k: v for k, v in (cfg.get("unit_test", {}).get("language_labels") or {}).items()
                        if not str(k).startswith("_")})
    CODE_REGEX = rf"(?:{ids['error_code']})"
    ID_PATTERNS[:] = [
        (re.compile(rf"\b(?:{ids['screen_id']})\b"), "画面"),
        (re.compile(rf"\b(?:{ids['api_id']})\b"), "API"),
        (re.compile(r"\bBR-\d{1,3}\b"), "業務ルール"),
        (re.compile(r"\bAC-(?:[A-Z]{1,6}-)?\d{1,3}\b"), "受入基準"),
        (re.compile(r"\b" + CODE_REGEX + r"\b"), "エラー"),
    ]


def _need_config():
    if CODE_REGEX is None:
        sys.exit("ERROR: read_design: 項目配置が未設定（--config project.json を指定。gen_ut_xlsx.py 経由なら自動）")


def _texts_from_path(src: Path) -> List[str]:
    if src.is_dir():
        out = []
        for p in sorted(src.rglob("*")):
            if p.suffix.lower() in (".md", ".yaml", ".yml") and "単体テスト" not in p.name:
                out.append(p.read_text(encoding="utf-8", errors="ignore"))
        return out
    if src.suffix.lower() == ".xlsx":
        import warnings
        import openpyxl
        warnings.simplefilter("ignore")
        wb = openpyxl.load_workbook(src, data_only=True)
        out = []
        for ws in wb.worksheets:
            if ws.title in ("改訂履歴", "実装対照"):
                continue
            for row in ws.iter_rows(values_only=True):
                cells = [str(v) for v in row if v not in (None, "")]
                if cells:
                    out.append(" | ".join(cells))
        return ["\n".join(out)]
    return [src.read_text(encoding="utf-8")]


def inventory(src: str) -> Dict[str, str]:
    _need_config()
    p = Path(src)
    ids: Dict[str, str] = {}
    if p.suffix.lower() == ".json":
        d = json.loads(p.read_text(encoding="utf-8"))
        for s in d.get("screens", []):
            ids[s["id"]] = s.get("name", "")
        for a in d.get("apis", []):
            ids[a["id"]] = a.get("name", "")
        for b in d.get("business_rules", []):
            bid = b.get("規則ID") if isinstance(b, dict) else b[0]
            ids[bid] = (b.get("結果") if isinstance(b, dict) else b[2]) or ""
        for ac in d.get("acceptance", []):
            aid = ac.get("AC-ID") if isinstance(ac, dict) else ac[0]
            ids[aid] = (ac.get("受入項目") if isinstance(ac, dict) else ac[1]) or ""
        for c in d.get("checks", []):
            code = c.get("エラーコード") if isinstance(c, dict) else c[2]
            for cd in re.findall(CODE_REGEX, code or ""):
                ids.setdefault(cd, c.get("チェック内容", "") if isinstance(c, dict) else c[1])
        return ids
    for t in _texts_from_path(p):
        for pat, label in ID_PATTERNS:
            for m in pat.findall(t):
                ids.setdefault(m, label)
    return ids


# ------------------------------------------------------------------ draft
def _rows(lst, keys):
    for x in lst or []:
        if isinstance(x, dict):
            yield [x.get(k, "") for k in keys]
        else:
            yield list(x) + [""] * (len(keys) - len(x))


TYPE_MAP = {"n-button": "BTN", "button": "BTN", "n-select": "DRP", "select": "DRP", "n-input": "INP",
            "input": "INP", "text": "LBL", "label": "LBL", "n-upload": "BTN", "n-alert": "LBL", "n-data-table": "TBL",
            "table": "TBL", "n-checkbox": "CHK", "checkbox": "CHK", "n-radio": "RBT", "radio": "RBT", "link": "LNK"}


def draft(design: dict, feature: str) -> dict:
    _need_config()
    meta = design.get("meta", {})
    out = {"meta": {"feature": feature or meta.get("feature", ""), "author": "AI", "created": "", "updater": "",
                    "updated": "", "design_doc": meta.get("docs_dir", ""), "lang": meta.get("body_lang", LANGS[0])},
           "layout": [], "operation": [], "check": []}
    for s in design.get("screens", []):
        sid, name = s["id"], s.get("name", "")
        cases = []
        for it in _rows(s.get("items"), ["#", "項目", "物理名", "コンポーネント", "RW", "必須", "備考", "PPT"]):
            no, item, phys, comp, rw, req, note, ppt = (it + [""] * 8)[:8]
            cases.append({"viewpoint": "画面レイアウト", "name": item, "type": TYPE_MAP.get(str(comp).strip(), "TXT"),
                          "label": f"TODO: 画面文言（PPT/locale {LANGS[0]}）", "required": "○" if req in ("○", "◯") else "-",
                          "note": note or "-", "ref": f"{sid} #{no}" + (f" / slide {ppt}" if ppt else "")})
        for k in _rows(s.get("i18n"), ["key"] + LANGS):
            for j, lg in enumerate(LANGS[1:], start=2):  # 2 言語目以降の表示確認
                cases.append({"viewpoint": "多言語対応チェック", "name": f"{k[1]}（{lg}）", "type": "LBL", "label": k[j],
                              "note": f"{LANG_LABELS.get(lg, lg)}表示時", "ref": sid})
        out["layout"].append({"section": f"【{sid} {name}】", "ref": sid, "cases": cases})
        ops = [{"viewpoint": "初期化チェック", "item": "初期表示", "step": "TODO: 画面を開く操作",
                "expected": "TODO: 初期値・活性/非活性", "ref": sid}]
        for e in _rows(s.get("events"), ["操作", "トリガー", "API", "リクエスト", "成功", "失敗"]):
            ops.append({"viewpoint": "分岐網羅", "item": e[0], "step": f"{e[0]}を押下", "branch": "正常",
                        "expected": e[4] or "TODO", "ref": sid})
            if e[5] and e[5] not in ("—", "-"):
                ops.append({"viewpoint": "例外処理の網羅", "item": e[0], "step": f"{e[0]}を押下", "branch": "失敗",
                            "expected": e[5], "ref": sid})
        for t in _rows(s.get("transitions"), ["操作", "遷移先", "備考"]):
            ops.append({"viewpoint": "分岐網羅", "item": "画面遷移", "step": t[0], "branch": "-",
                        "expected": f"{t[1]}へ遷移する。{t[2] if t[2] not in ('—', '-') else ''}".strip(), "ref": sid})
        out["operation"].append({"section": f"【{sid} {name}】画面操作", "ref": sid, "cases": ops})
    for a in design.get("apis", []):
        aid = a["id"]
        ops = []
        for bl in _rows(a.get("logic"), ["BL", "処理", "条件", "結果", "エラー"]):
            ops.append({"viewpoint": "分岐網羅", "item": bl[1], "step": f"{a.get('method','')} {a.get('path','')}".strip(),
                        "branch": bl[2] or "-", "expected": bl[3] or "TODO", "ref": f"{aid} {bl[0]}"})
        for t in _rows(a.get("tests"), ["#", "観点", "期待"]):
            ops.append({"viewpoint": "分岐網羅", "item": t[1], "step": "TODO", "expected": t[2], "ref": aid})
        out["operation"].append({"section": f"【{aid} {a.get('name','')}】", "ref": aid, "cases": ops})
    br = [{"viewpoint": "分岐網羅", "item": b[0], "step": "TODO", "branch": b[1], "expected": b[2], "ref": b[0]}
          for b in _rows(design.get("business_rules"), ["規則ID", "条件", "結果"])]
    if br:
        out["operation"].append({"section": "【業務ルール】", "cases": br})
    ac = [{"viewpoint": "分岐網羅", "item": x[1], "step": "TODO", "expected": x[2], "ref": x[0]}
          for x in _rows(design.get("acceptance"), ["AC-ID", "受入項目", "合格条件（テスト可能な形）"])]
    if ac:
        out["operation"].append({"section": "【受入基準】", "cases": ac})
    chk = []
    for c in _rows(design.get("checks"), ["ID", "チェック内容", "エラーコード", "レベル", "発生条件", "メッセージ（ja）"]):
        for code in re.findall(CODE_REGEX, c[2] or "") or [None]:
            row = {"viewpoint": "例外処理の網羅", "field": c[1], "screen": "TODO", "branch1": c[4], "ref": c[0]}
            if code:
                row["code"] = code
            else:
                row["expected"] = "TODO"
            chk.append(row)
    if chk:
        out["check"].append({"section": None, "cases": chk})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("--ids", action="store_true")
    ap.add_argument("--draft", action="store_true")
    ap.add_argument("--dump", action="store_true")
    ap.add_argument("--feature", default="")
    ap.add_argument("-o", "--out")
    ap.add_argument("--config", help="init.sh 生成的 project.json（--ids / --draft 必须）")
    a = ap.parse_args()
    if not a.dump:
        configure(project_config.load(a.config, "read_design"))
    if a.draft:
        d = draft(json.loads(Path(a.src).read_text(encoding="utf-8")), a.feature)
        s = json.dumps(d, ensure_ascii=False, indent=1)
        (Path(a.out).write_text(s, encoding="utf-8") if a.out else print(s))
        return
    if a.dump:
        print("\n\n".join(_texts_from_path(Path(a.src))))
        return
    for k, v in inventory(a.src).items():
        print(f"{k}\t{v}")


if __name__ == "__main__":
    main()
