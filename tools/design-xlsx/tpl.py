"""設計書 xlsx 共通部品：テンプレートの行（原型行）のスタイル・結合を複写して本文を書き出す。

export_api.py / export_scr.py から使う。単体では実行しない。
"""
import copy, datetime, json, os, re, sys
import openpyxl
from openpyxl.drawing.image import Image as XLImage

HERE = os.path.dirname(os.path.abspath(__file__))


class Proto:
    """テンプレートの 1 行分のスタイル・行内結合・行高。"""
    def __init__(self, ws, row):
        self.styles = {c: copy.copy(ws.cell(row, c)._style) for c in range(1, ws.max_column + 1)}
        self.merges = [(m.min_col, m.max_col) for m in ws.merged_cells.ranges if m.min_row == row and m.max_row == row]
        self.height = ws.row_dimensions[row].height


class Sheet:
    """dst シートの start 行以降を消して書き直す。原型行は src（同じテンプレートを別に読んだもの）から取る。"""
    def __init__(self, dst, src, start, blank_row=4):
        self.ws, self.src, self.r = dst, src, start
        self.blank = Proto(src, blank_row)
        for m in list(dst.merged_cells.ranges):
            if m.min_row >= start:
                dst.unmerge_cells(str(m))
        maxr = dst.max_row
        for r in range(start, maxr + 1):
            for c in range(1, dst.max_column + 1):
                cell = dst.cell(r, c); cell.value = None; cell._style = copy.copy(self.blank.styles.get(c, cell._style))
            dst.row_dimensions[r].height = None
        dst._images = []
        self.protos = {}

    def p(self, row):
        if row not in self.protos: self.protos[row] = Proto(self.src, row)
        return self.protos[row]

    def emit(self, proto_row, vals=None, height=None):
        vals = {k: v for k, v in (vals or {}).items() if v is not None}
        pr = self.p(proto_row); r = self.r
        for c, st in pr.styles.items(): self.ws.cell(r, c)._style = copy.copy(st)
        for a, b in pr.merges: self.ws.merge_cells(start_row=r, start_column=a, end_row=r, end_column=b)
        for col, v in vals.items(): self.ws[f"{col}{r}"] = v
        if height or pr.height: self.ws.row_dimensions[r].height = height or pr.height
        lines = max([str(v).count("\n") + 1 for v in vals.values()] + [1])
        if lines > 1: self.ws.row_dimensions[r].height = max(self.ws.row_dimensions[r].height or 15, 15 * lines)
        self.r += 1
        return r

    def gap(self, n=1):
        for _ in range(n): self.emit_blank()

    def emit_blank(self):
        r = self.r
        for c, st in self.blank.styles.items(): self.ws.cell(r, c)._style = copy.copy(st)
        self.r += 1

    def image(self, path, width_px=900, rows=None):
        try:
            import PIL  # noqa: F401  openpyxl needs Pillow to embed images
        except ImportError:
            print(f"WARNING: Pillow 未安装，跳过图片 {os.path.basename(path)}（python3 -m pip install pillow 后重新导出即可放入图片）", file=sys.stderr)
            self.ws[f"B{self.r}"] = f"（画像省略：{os.path.basename(path)}）"
            self.gap(2)
            return
        img = XLImage(path); ratio = width_px / img.width
        img.width, img.height = width_px, int(img.height * ratio)
        self.ws.add_image(img, f"B{self.r}")
        n = rows or int(img.height / 18) + 2
        self.gap(n)


def set_header(ws, cells):
    for k, v in cells.items(): ws[k] = v


# ---------------------------------------------------------------- spec helpers

def die(msg):
    print("ERROR: " + msg, file=sys.stderr); sys.exit(2)


def load_spec(path):
    try:
        with open(path, encoding="utf-8") as f:
            spec = json.load(f)
    except json.JSONDecodeError as e:
        die(f"{path}: JSON の書式エラー（{e.lineno} 行 {e.colno} 列）：{e.msg}")
    for k in ("feature",):
        if not spec.get(k): die(f"{path}: トップレベルに \"{k}\" がありません")
    return spec


def to_date(v):
    """'2026-01-31' → datetime。None/空 → None。それ以外の文字列はそのまま。"""
    if not v: return None
    if isinstance(v, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", v):
        return datetime.datetime.strptime(v, "%Y-%m-%d")
    return v


def refs_list(el):
    r = el.get("refs") or {}
    return [x for k in ("br", "ac", "q") for x in (r.get(k) or [])]


def title_of(el, no):
    """表示用タイトル：title があればそのまま、無ければ「{no} {name}（BR-01・AC-01）」。"""
    if el.get("title"): return el["title"]
    t = f"{no} {el.get('name', '')}".strip()
    rs = refs_list(el)
    return t + (f"（{'・'.join(rs)}）" if rs else "")


_BAD = re.compile(r"[\[\]\*\?/\\:]")
def sheet_title(s):
    s = _BAD.sub("_", s)
    return s[:31]


def out_path(spec_path, doc, prefix, arg_out):
    if arg_out: return arg_out
    d = os.path.dirname(os.path.abspath(spec_path))
    name = (doc or {}).get("file_name") or f"{prefix}_{os.path.basename(d)}.xlsx"
    return os.path.join(d, name)


# [CMPF] 版式：表紙・変更履歴的单元格位置（A1/AW2/BD2/J5/J13、第 8 行起）按 CMPF 样本模板
def write_history(ws, spec, doc_id, first_row=8, doc=None):
    """変更履歴シート：A1 文書ID、AW2 作成日、BD2 作成者、8 行目以降に改訂履歴。"""
    ws["A1"] = doc_id
    ws["AW2"] = to_date(spec.get("date")); ws["BD2"] = spec.get("author") or "—"
    hist = (doc or {}).get("history") or spec.get("history") or [{"version": spec.get("version") or "1.00", "date": spec.get("date"),
                                     "author": spec.get("author"), "content": "初版作成"}]
    for i, h in enumerate(hist):
        r = first_row + i
        ws[f"A{r}"] = h.get("version"); ws[f"D{r}"] = to_date(h.get("date"))
        ws[f"J{r}"] = h.get("author") or "—"; ws[f"P{r}"] = h.get("content")


def strip_props(wb):
    p = wb.properties
    p.creator = ""; p.lastModifiedBy = None; p.title = None
    from openpyxl.packaging.custom import CustomPropertyList
    wb.custom_doc_props = CustomPropertyList()


# ---------------------------------------------------------------- validation
# 単体 case 側が追跡に使う要素：id / type / name / refs{br,ac,q} を必須にする。
_TRACK = {"screens": "screen", "items": "item", "events": "event", "apis": "api", "steps": "step"}


def validate(spec, path="design.json"):
    errs, ids = [], {}

    def chk(el, where, typ):
        for k in ("id", "type", "name"):
            if not el.get(k): errs.append(f"{where}: \"{k}\" がありません")
        if typ and el.get("type") and el["type"] != typ:
            errs.append(f"{where}: type は \"{typ}\" にしてください（今は \"{el['type']}\"）")
        r = el.get("refs")
        if not isinstance(r, dict) or any(not isinstance(r.get(k), list) for k in ("br", "ac", "q")):
            errs.append(f"{where}: refs は {{\"br\": [], \"ac\": [], \"q\": []}} の形にしてください")
        if el.get("id"):
            if el["id"] in ids: errs.append(f"{where}: id \"{el['id']}\" が重複（{ids[el['id']]} と同じ）")
            ids[el["id"]] = where

    if not spec.get("version"): errs.append("トップレベル: \"version\" がありません")
    for k in ("screens", "apis"):
        if not isinstance(spec.get(k), list): errs.append(f"トップレベル: \"{k}\" は配列にしてください（無ければ []）")
    for i, sc in enumerate(spec.get("screens") or []):
        w = f"screens[{i}]"; chk(sc, w, "screen")
        for j, it in enumerate(sc.get("items") or []): chk(it, f"{w}.items[{j}]", "item")
        for j, ev in enumerate(sc.get("events") or []): chk(ev, f"{w}.events[{j}]", "event")
    for i, a in enumerate(spec.get("apis") or []):
        w = f"apis[{i}]"; chk(a, w, "api")
        for j, st in enumerate(a.get("steps") or []):
            chk(st, f"{w}.steps[{j}]", "step")
            for k, b in enumerate(st.get("body") or []):
                if b.get("kind") == "check":
                    for m, r in enumerate(b.get("rows") or []): chk(r, f"{w}.steps[{j}].body[{k}].rows[{m}]", "check")
                elif b.get("kind") == "table":
                    for m, r in enumerate(b.get("rows") or []):
                        if isinstance(r, dict) and r.get("id"): chk(r, f"{w}.steps[{j}].body[{k}].rows[{m}]", None)
    if errs:
        die(f"{path}: JSON の形式エラー {len(errs)} 件\n  " + "\n  ".join(errs[:50]))
