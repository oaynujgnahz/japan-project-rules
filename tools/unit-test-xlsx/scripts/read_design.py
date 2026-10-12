#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""設計書読取ツール（単体テスト Case のトレース確認用）

  python3 read_design.py <src> [<src> ...] --ids      # ID 一覧（ID / 種別 / 名称 / 出典）
  python3 read_design.py <src> [<src> ...] --json     # 同上を JSON で出力
  python3 read_design.py <src> [<src> ...] --dump     # 設計書本文をテキスト化（読む用）
  python3 read_design.py <中間JSON> --draft -o draft.cases.json   # Case 骨架を起草（要手直し）

<src> に指定できるもの（複数可・混在可）:
  * docs/{機能}/ ディレクトリ
      中の 中間 JSON（design.json / *.design.json）があればそれを最優先で使う。
      無ければ API設計書_*.xlsx + 画面設計書_*.xlsx + MD/YAML（README・詳細設計書・
      06_画面設計書・07_API設計書・验收标准・openapi.yaml など）をまとめて読む。
  * API設計書_{機能}.xlsx / 画面設計書_{機能}.xlsx（片方だけでも可。足りない方は警告）
  * 個別の .md / .yaml ファイル
  * 中間 JSON（docs/{機能}/design.json。設計書 MD → xlsx の間に作る JSON。
    形式は tools/design-xlsx/README.md「JSON 格式说明」）

読み取りの優先順位: 中間 JSON ＞ 2 本の設計書 xlsx + MD。
`--no-json` を付けると中間 JSON があっても xlsx + MD を読む（突き合わせ用）。
中間 JSON では screens[] / apis[] とその下の items / events / steps / check・table(branch) 行を再帰的にたどり、
各要素の id と refs{br,ac,q}、error_code、api_id を集める。画面・API・エラーコードは Case 必須、
画面項目・事件・処理步骤・检查项・分岐の要素 ID は一覧に出す（--all）が必須にはしない（BR/AC で追溯するため）。

抽出する ID: SCR-… / API-… / BR-nn / AC-nn / Q-nn / BL-nn / F-nn / エラーコード（XXXX0000-E/W）。
「BR-nn 欠番」「AC-nn（撤回）」のように書かれた ID は欠番として別扱い（Case 必須から外す・再利用を警告）。
依存: 標準ライブラリ + openpyxl（xlsx を読むときだけ）。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional

# ------------------------------------------------------------------ ID patterns
# kind, regex, required(=Case で必ず覆う)
# [CMPF] ID 写法：SCR-/API-/BR-/AC-/Q-/BL-/F- 和错误码格式是 CMPF 的约定；将来 ID 规则只在 project.yaml 定义一份，设计书和单体 case 两个工具共读
ID_PATTERNS = [
    ("SCR", re.compile(r"(?<![\w-])SCR-[A-Za-z0-9][\w-]*[A-Za-z0-9](?![\w-])"), True),
    ("API", re.compile(r"(?<![\w-])API-[A-Za-z0-9][\w-]*[A-Za-z0-9](?![\w-])"), True),
    ("BR", re.compile(r"(?<![\w-])BR-\d{1,3}(?![\w-])"), True),
    ("AC", re.compile(r"(?<![\w-])AC-(?:[A-Z]{1,6}-)?\d{1,3}(?![\w-])"), True),
    ("ERR", re.compile(r"(?<![\w-])[A-Z]{2,8}\d{3,5}-[EW](?![\w-])"), True),
    ("Q", re.compile(r"(?<![\w-])Q-\d{1,3}(?![\w-])"), False),
    ("BL", re.compile(r"(?<![\w-])BL-\d{1,3}(?![\w-])"), False),
    ("F", re.compile(r"(?<![\w-])F-\d{1,3}(?![\w-])"), False),
]
KIND_LABEL = {"SCR": "画面", "API": "API", "BR": "業務ルール", "AC": "受入基準", "ERR": "エラー",
              "Q": "要確認", "BL": "処理ロジック", "F": "処理フロー"}
REQUIRED_KINDS = {k for k, _p, req in ID_PATTERNS if req}
# [CMPF] ID 写法：欠番的写法「BR-nn 欠番」「（撤回）」是 CMPF 设计书的约定
WITHDRAWN_RE = re.compile(r"([A-Z]{1,4}-[\w-]*\d)\s*[（(【]?\s*(?:欠番|撤回|廃止|削除済|withdrawn)")
# [CMPF] 模板：跳过的 sheet 名（表紙/変更履歴/改訂履歴/実装対照）是 CMPF 设计书 xlsx 的 sheet 名
SKIP_SHEETS = {"表紙", "変更履歴", "改訂履歴", "実装対照"}
JSON_GLOBS = ("design.json", "*.design.json", "design_*.json")


class Inventory:
    def __init__(self):
        self.ids: Dict[str, dict] = {}       # id -> {kind, name, sources:set}
        self.withdrawn: Dict[str, str] = {}  # id -> source
        self.sources: List[str] = []
        self.warnings: List[str] = []
        self.mode = ""

    def add(self, i: str, kind: str, name: str, src: str, required: Optional[bool] = None, etype: str = ""):
        e = self.ids.setdefault(i, {"kind": kind, "name": "", "sources": set(), "required": None, "type": ""})
        if name and not e["name"]:
            e["name"] = name
        if required is not None and e["required"] is not True:
            e["required"] = required
        if etype and not e["type"]:
            e["type"] = etype
        e["sources"].add(src)

    def is_required(self, i: str) -> bool:
        e = self.ids[i]
        if i in self.withdrawn:
            return False
        return e["kind"] in REQUIRED_KINDS if e["required"] is None else e["required"]

    def as_dict(self, required_only: bool = True) -> Dict[str, str]:
        """gen_ut_xlsx.py のカバレッジ確認用: {id: 名称} （欠番・非必須種別は除く）"""
        return {i: (e["name"] or KIND_LABEL.get(e["kind"], "")) for i, e in self.ids.items()
                if i not in self.withdrawn and (not required_only or self.is_required(i))}

    def to_json(self) -> dict:
        return {"mode": self.mode, "sources": self.sources, "warnings": self.warnings,
                "withdrawn": self.withdrawn,
                "ids": [{"id": i, "kind": e["kind"], "type": e["type"], "name": e["name"],
                         "required": self.is_required(i), "sources": sorted(e["sources"])}
                        for i, e in sorted(self.ids.items(), key=lambda kv: (kv[1]["kind"], kv[0]))]}


def kind_of(i: str) -> str:
    for k, p, _r in ID_PATTERNS:
        if p.fullmatch(i):
            return k
    return "OTHER"


# ------------------------------------------------------------------ text extraction
def _md_files(d: Path) -> List[Path]:
    return [p for p in sorted(d.rglob("*")) if p.is_file() and p.suffix.lower() in (".md", ".yaml", ".yml")
            and not p.name.startswith("._") and "単体テスト" not in p.name]


def _xlsx_text(p: Path) -> str:
    import warnings
    import openpyxl
    warnings.simplefilter("ignore")
    wb = openpyxl.load_workbook(p, read_only=True, data_only=True)
    out = []
    for ws in wb.worksheets:
        if ws.title in SKIP_SHEETS:
            continue
        out.append(f"## [{ws.title}]")
        for row in ws.iter_rows(values_only=True):
            cells = [str(v) for v in row if v not in (None, "")]
            if cells:
                out.append(" | ".join(cells))
    wb.close()
    return "\n".join(out)


def _scan_text(inv: Inventory, text: str, src: str):
    for m in WITHDRAWN_RE.finditer(text):
        inv.withdrawn.setdefault(m.group(1), src)
    for line in text.splitlines():
        for k, pat, _r in ID_PATTERNS:
            for m in pat.finditer(line):
                i = m.group(0)
                # 表の行「| BR-nn | 名称 | …」なら次のセルを名称として拾う
                name = ""
                rest = line[m.end():]
                mm = re.match(r"\s*\|\s*([^|]{1,60}?)\s*\|", rest)
                if mm and not any(p.search(mm.group(1)) for _k, p, _ in ID_PATTERNS):
                    name = mm.group(1).strip()
                inv.add(i, k, name, src)


# ------------------------------------------------------------------ intermediate JSON
# 形式: tools/design-xlsx/README.md「JSON 格式说明」
#   顶层 feature / version / screens[] / apis[]
#   screen{id,type:"screen",name,refs,items[],events[{…,steps[]}]}
#   api{id,type:"api",name,refs,steps[{…,body[{kind:"check",rows[{id,type:"check",name,error_code,refs}]},
#                                          {kind:"table",rows[{id,type:"branch",name,refs}]}…]}]}
#   追踪字段 refs = {"br": [...], "ac": [...], "q": [...]}
TRACE_TYPES = {"screen", "item", "event", "api", "step", "check", "branch"}
TOP_TYPES = {"screen", "api"}
WITHDRAWN_STATUS = {"withdrawn", "欠番", "撤回", "廃止", "deleted"}


def is_design_json(d) -> bool:
    return isinstance(d, dict) and isinstance(d.get("screens", []), list) and isinstance(d.get("apis", []), list) \
        and ("screens" in d or "apis" in d)


def walk_elements(node, parent_type: str = ""):
    """screens/apis 以下を再帰的にたどり、追踪字段（id + type）を持つ要素を yield する"""
    if isinstance(node, list):
        for x in node:
            yield from walk_elements(x, parent_type)
    elif isinstance(node, dict):
        t = node.get("type")
        if node.get("id") and (t in TRACE_TYPES or isinstance(node.get("refs"), dict)):
            yield node
        for k, v in node.items():
            if isinstance(v, (list, dict)) and k != "refs":
                yield from walk_elements(v, t or parent_type)


def _strings(node):
    if isinstance(node, str):
        yield node
    elif isinstance(node, list):
        for x in node:
            yield from _strings(x)
    elif isinstance(node, dict):
        for v in node.values():
            yield from _strings(v)


def _refs(el) -> List[str]:
    r = el.get("refs") or {}
    out = []
    if isinstance(r, dict):
        for key in ("br", "ac", "q"):
            out += [str(x) for x in (r.get(key) or [])]
    elif isinstance(r, list):  # 念のため配列形式も受ける
        out = [str(x) for x in r]
    return out


def load_intermediate_json(path: Path, inv: Inventory) -> bool:
    """中間 JSON（tools/design-xlsx/README.md「JSON 格式说明」）を読む。読めたら True。"""
    try:
        d = json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        inv.warnings.append(f"中間 JSON を読めない: {path.name}（{e}）→ xlsx/MD にフォールバック")
        return False
    if not is_design_json(d):
        inv.warnings.append(f"中間 JSON の形式が想定外（screens[] / apis[] が無い）: {path.name} → xlsx/MD にフォールバック")
        return False
    src = path.name
    n = 0
    for el in walk_elements([d.get("screens", []), d.get("apis", [])]):
        eid, t = str(el["id"]), str(el.get("type") or "")
        n += 1
        k = kind_of(eid)
        inv.add(eid, k if k != "OTHER" else "ELEM", str(el.get("name") or ""), src,
                required=(t in TOP_TYPES) if t else None, etype=t)
        if str(el.get("status") or "").lower() in WITHDRAWN_STATUS:
            inv.withdrawn.setdefault(eid, src)
        for r in _refs(el):
            rk = kind_of(r)
            inv.add(r, rk if rk != "OTHER" else "ELEM", "", src)
        code = str(el.get("error_code") or "").strip()
        if code and code not in ("-", "—"):
            inv.add(code, "ERR", str(el.get("name") or ""), src, required=True)
    # api ブロックの api_id、本文中の「BR-nn 欠番」等も拾う
    def api_ids(node):
        if isinstance(node, dict):
            if node.get("kind") == "api" and node.get("api_id"):
                inv.add(str(node["api_id"]), "API", "", src)
            for v in node.values():
                api_ids(v)
        elif isinstance(node, list):
            for v in node:
                api_ids(v)
    api_ids(d.get("screens", []))
    for t in _strings(d):
        for m in WITHDRAWN_RE.finditer(t):
            inv.withdrawn.setdefault(m.group(1), src)
    if n == 0:
        inv.warnings.append(f"中間 JSON に id 付き要素が無い: {path.name}")
    return True


# ------------------------------------------------------------------ resolve sources
# [CMPF] 模板：按文件名前缀 API設計書 / 画面設計書 区分两份设计书 xlsx，是 CMPF 的命名约定
def _classify_xlsx(p: Path) -> Optional[str]:
    if p.name.startswith("._") or "単体テスト" in p.name:
        return None
    if p.name.startswith("API設計書"):
        return "api"
    if p.name.startswith("画面設計書"):
        return "screen"
    return "other"


def load(srcs: List[str], use_json: bool = True) -> Inventory:
    inv = Inventory()
    jsons: List[Path] = []
    xlsxs: List[Path] = []
    texts: List[Path] = []
    for s in srcs:
        p = Path(s)
        if not p.exists():
            inv.warnings.append(f"見つからない: {s}")
            continue
        if p.is_dir():
            for g in JSON_GLOBS:
                jsons += [x for x in sorted(p.rglob(g)) if not x.name.startswith("._")]
            xlsxs += [x for x in sorted(p.rglob("*.xlsx")) if _classify_xlsx(x)]
            texts += _md_files(p)
        elif p.suffix.lower() == ".json":
            jsons.append(p)
        elif p.suffix.lower() == ".xlsx":
            if _classify_xlsx(p):
                xlsxs.append(p)
        else:
            texts.append(p)

    # 1) 中間 JSON 優先
    if use_json and jsons:
        ok = [j for j in dict.fromkeys(jsons) if load_intermediate_json(j, inv)]
        if ok:
            inv.mode = "json"
            inv.sources = [str(j) for j in ok]
            return inv

    # 2) 2 本の xlsx + MD
    inv.mode = "xlsx+md"
    kinds = {}
    for x in dict.fromkeys(xlsxs):
        kinds.setdefault(_classify_xlsx(x), []).append(x)
    if not kinds.get("api") and not kinds.get("screen"):
        if xlsxs:
            inv.warnings.append("API設計書_*.xlsx / 画面設計書_*.xlsx が見つからない（他の xlsx のみ読む）")
        elif texts:
            inv.warnings.append("設計書 xlsx が見つからない → MD/YAML のみで ID を抽出（xlsx 導出前の段階なら問題なし）")
    else:
        if not kinds.get("api"):
            inv.warnings.append("API設計書_*.xlsx が見つからない（画面設計書のみ）→ API 側の ID は MD から補う")
        if not kinds.get("screen"):
            inv.warnings.append("画面設計書_*.xlsx が見つからない（API設計書のみ）→ 画面側の ID は MD から補う")
    for x in dict.fromkeys(xlsxs):
        try:
            _scan_text(inv, _xlsx_text(x), x.name)
            inv.sources.append(str(x))
        except Exception as e:  # noqa: BLE001
            inv.warnings.append(f"xlsx を読めない: {x.name}（{e}）")
    for t in dict.fromkeys(texts):
        _scan_text(inv, t.read_text(encoding="utf-8", errors="ignore"), t.name)
        inv.sources.append(str(t))
    if not inv.sources:
        inv.warnings.append("読める設計書が 1 つも無い")
    return inv


def inventory(srcs) -> Dict[str, str]:
    """互換 API: {id: 名称}（Case 必須の ID のみ・欠番除く）"""
    if isinstance(srcs, (str, Path)):
        srcs = [str(srcs)]
    return load(list(srcs)).as_dict()


def dump(srcs: List[str]) -> str:
    out = []
    for s in srcs:
        p = Path(s)
        items = []
        if p.is_dir():
            items = [x for x in sorted(p.rglob("*.xlsx")) if _classify_xlsx(x)] + _md_files(p)
        elif p.exists():
            items = [p]
        for x in items:
            out.append(f"# ===== {x.name}")
            out.append(_xlsx_text(x) if x.suffix.lower() == ".xlsx" else x.read_text(encoding="utf-8", errors="ignore"))
    return "\n\n".join(out)


# ------------------------------------------------------------------ draft (from intermediate JSON)
# 画面設計書「各種凡例」の論理項目種別 → 単体テンプレートの表示タイプ（無いものは TODO のまま）
# [CMPF] 模板：论理项目种别 → 表示タイプ 的对应来自 CMPF 画面設計書「各種凡例」和单体模板凡例
WIDGET_TYPE = {"項目ラベル": "LBL", "ラベル": "LBL", "テキストボックス": "TXT", "テキストエリア": "TXT", "ボタン": "BTN",
               "リンク": "LNK", "プルダウン": "DRP", "ドロップダウン": "DRP", "コンボボックス": "CMB",
               "ラジオボタン": "RBT", "チェックボックス": "CHK", "一覧": "TBL", "テーブル": "TBL", "タイトル": "TT",
               "画像ボタン": "IB"}


def draft(d: dict, feature: str = "") -> dict:
    """中間 JSON から cases.json の骨架を作る。期待結果などは TODO で出すので必ず手直しする。
    画面項目 → layout、事件 → operation、API の処理步骤・分岐 → operation、检查项 → check。"""
    if not is_design_json(d):
        raise SystemExit("中間 JSON の形式が想定外（screens[] / apis[] が無い）")

    def ref(el):
        return " / ".join([str(el.get("id", ""))] + _refs(el))
    out = {"meta": {"feature": feature or d.get("feature", ""), "author": "", "created": "", "updater": "",
                    "updated": "", "design_doc": f"design.json v{d.get('version', '')}".strip(), "lang": "ja"},
           "layout": [], "operation": [], "check": []}
    for s in d.get("screens", []):
        sid, sname = s.get("id", ""), s.get("name", "")
        lay = [{"viewpoint": "画面レイアウト", "name": it.get("name", ""), "type": WIDGET_TYPE.get(str(it.get("widget", "")), "TODO"),
                "label": it.get("name", ""), "note": "TODO", "ref": ref(it)}
               for it in s.get("items", []) if isinstance(it, dict)]
        if lay:
            out["layout"].append({"section": f"【{sid} {sname}】", "ref": sid, "cases": lay})
        ops = [{"viewpoint": "初期化チェック" if "初期" in str(ev.get("name", "")) else "分岐網羅",
                "item": ev.get("name", ""), "step": "TODO", "branch": "TODO", "expected": "TODO", "ref": ref(ev)}
               for ev in s.get("events", []) if isinstance(ev, dict)]
        if ops:
            out["operation"].append({"section": f"【{sid} {sname}】画面操作", "ref": sid, "cases": ops})
    for a in d.get("apis", []):
        aid, aname = a.get("id", ""), a.get("name", "")
        ops, chk = [], []
        for el in walk_elements(a.get("steps", [])):
            t = el.get("type")
            if t in ("step", "branch"):
                ops.append({"viewpoint": "分岐網羅", "item": el.get("name", ""), "step": "TODO",
                            "branch": el.get("name", "") if t == "branch" else "TODO", "expected": "TODO", "ref": ref(el)})
            elif t == "check":
                row = {"viewpoint": "例外処理の網羅", "field": el.get("name", ""), "screen": "TODO",
                       "branch1": el.get("condition") or "TODO", "expected": "TODO", "ref": ref(el)}
                if el.get("error_code"):
                    row["code"] = el["error_code"]
                    row.pop("expected")
                chk.append(row)
        if ops:
            out["operation"].append({"section": f"【{aid} {aname}】", "ref": aid, "cases": ops})
        if chk:
            out["check"].append({"section": f"【{aid} {aname}】入力チェック", "ref": aid, "cases": chk})
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("src", nargs="+")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--ids", action="store_true", help="ID 一覧（既定）")
    g.add_argument("--json", action="store_true", help="ID 一覧を JSON で出力")
    g.add_argument("--dump", action="store_true", help="本文をテキスト化")
    g.add_argument("--draft", action="store_true", help="中間 JSON から cases.json 骨架を起草")
    ap.add_argument("--no-json", action="store_true", help="中間 JSON を使わず xlsx + MD を読む")
    ap.add_argument("--all", action="store_true", help="--ids で Q/BL/F・画面項目/事件/步骤などの要素 ID（非必須）も表示")
    ap.add_argument("--feature", default="")
    ap.add_argument("-o", "--out")
    a = ap.parse_args()
    if a.draft:
        d = draft(json.loads(Path(a.src[0]).read_text(encoding="utf-8")), a.feature)
        s = json.dumps(d, ensure_ascii=False, indent=1)
        (Path(a.out).write_text(s, encoding="utf-8") if a.out else print(s))
        return
    if a.dump:
        s = dump(a.src)
        (Path(a.out).write_text(s, encoding="utf-8") if a.out else print(s))
        return
    inv = load(a.src, use_json=not a.no_json)
    for w in inv.warnings:
        print("WARN", w, file=sys.stderr)
    if a.json:
        s = json.dumps(inv.to_json(), ensure_ascii=False, indent=1)
        (Path(a.out).write_text(s, encoding="utf-8") if a.out else print(s))
        return
    print(f"# mode={inv.mode}  sources={len(inv.sources)}", file=sys.stderr)
    lines = []
    for i, e in sorted(inv.ids.items(), key=lambda kv: (kv[1]["kind"], kv[0])):
        req = inv.is_required(i)
        if not a.all and not req and i not in inv.withdrawn:
            continue
        mark = "欠番" if i in inv.withdrawn else ("必須" if req else "-")
        label = KIND_LABEL.get(e["kind"], e["kind"]) + (f"/{e['type']}" if e["type"] else "")
        lines.append(f"{i}\t{label}\t{mark}\t{e['name']}\t{','.join(sorted(e['sources']))}")
    s = "\n".join(lines)
    (Path(a.out).write_text(s + "\n", encoding="utf-8") if a.out else print(s))


if __name__ == "__main__":
    main()
