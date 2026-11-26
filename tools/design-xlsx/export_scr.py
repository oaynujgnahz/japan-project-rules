#!/usr/bin/env python3
"""設計書 JSON → 画面設計書 xlsx。

使い方:
  python3 export_scr.py docs/{機能}/design.json [-o 出力.xlsx] [--template templates/画面設計書_模板.xlsx]
出力の既定値: JSON と同じフォルダの 画面設計書_{フォルダ名}.xlsx（screen_doc.file_name で変更可）
画像パス（layout.images[].path）は JSON ファイルからの相対パス。
"""
import argparse, copy, os, warnings
import openpyxl
warnings.filterwarnings("ignore")
from tpl import validate, Sheet, HERE, die, load_spec, out_path, sheet_title, title_of, to_date, write_history, strip_props

# [CMPF] 版式：sheet 名（レイアウト/画面項目/画面操作詳細）、列位置、原型行号对应按 CMPF 样本做的画面模板；换模板要改（将来移到 project.json）
BASE = ["レイアウト", "画面項目", "画面操作詳細"]
# 画面項目シートの列
ITEM_COLS = [("group", "C"), ("name", "J"), ("widget", "Q"), ("physical", "X"), ("event", "AB"), ("fixed", "AF"),
             ("io", "AJ"), ("required", "AL"), ("validation", "AP"), ("max_length", "AT"), ("min", "AX"), ("max", "BA"),
             ("unit", "BD"), ("format", "BJ"), ("initial", "BO"), ("sort", "BT"), ("remarks", "CD")]


def hdr(ws, sid, kind, spec):
    ws["A1"] = sid
    ws[{"lay": "AW2", "item": "BF2", "op": "AW2"}[kind]] = to_date(spec.get("date"))
    ws[{"lay": "BD2", "item": "BM2", "op": "BD2"}[kind]] = spec.get("author") or "—"


def layout(ws, src, sc, spec, base_dir):
    lay = sc.get("layout") or {}
    hdr(ws, sc["id"], "lay", spec); ws["A6"] = lay.get("summary")
    s = Sheet(ws, src, start=10, blank_row=8)
    s.emit_blank()
    for im in lay.get("images") or []:
        ws[f"B{s.r}"] = im.get("caption"); s.emit_blank()
        p = im["path"] if os.path.isabs(im["path"]) else os.path.join(base_dir, im["path"])
        if not os.path.exists(p): die(f"画像が見つかりません: {p}")
        s.image(p, width_px=im.get("width_px", 1000))
    ws[f"A{s.r}"] = "変更点" if lay.get("notes") else None
    ws[f"A{s.r}"].font = copy.copy(ws["A9"].font); s.emit_blank()
    for n in lay.get("notes") or []:
        ws[f"B{s.r}"] = n; s.emit_blank()
    ws.print_area = f"A1:BJ{s.r}"


def items(ws, src, sc, spec):
    hdr(ws, sc["id"], "item", spec)
    s = Sheet(ws, src, start=7, blank_row=4)
    spans = []
    for i, it in enumerate(sc.get("items") or [], 1):
        vals = {"A": i}
        for k, col in ITEM_COLS:
            v = it.get(k)
            if k == "sort" and v is None: v = "-"
            vals[col] = v if v != "" else None
        rr = s.emit(7, vals)
        if it.get("group") or not spans: spans.append([rr, rr])
        else: spans[-1][1] = rr
    for a, b in spans:
        if b > a:
            for x in range(a, b + 1): ws.unmerge_cells(f"C{x}:I{x}")
            ws.merge_cells(f"C{a}:I{b}")


def block(s, ws, b):
    k = b.get("kind")
    if k == "step": s.emit(12, {"B": b["text"]})
    elif k == "text": s.emit(13, {"C": b["text"]})
    elif k == "ref": s.emit(48, {"C": b["text"], "T": b.get("see")})
    elif k == "api":
        r1 = s.emit(14, {"C": "項番", "E": "API名", "L": b["api"]})
        s.emit(15, {"E": "項目名", "P": "I/O", "R": "設定値", "AH": "備考／設定条件"})
        ws.merge_cells(f"C{r1}:D{r1+1}")
        for i, r in enumerate(b.get("rows") or [], 1):
            s.emit(16, {"C": i, "E": r.get("item"), "P": r.get("io", "I"), "R": r.get("value"), "AH": r.get("note") or ""})
    elif k == "params":
        s.emit(49, {"C": "項番", "E": "パラメータ", "P": "I/O", "R": "設定値", "AH": "備考／設定条件"})
        for i, r in enumerate(b.get("rows") or [], 1):
            s.emit(50, {"C": i, "E": r.get("item"), "P": r.get("io", "I"), "R": r.get("value"), "AH": r.get("note")})
    elif k == "display":
        r1 = s.emit(27, {"C": "項番", "E": "画面項目名", "U": "状態", "AB": "設定値", "AO": "備考／設定条件"}); s.emit(28)
        for a, z in [("C", "D"), ("E", "T"), ("U", "AA"), ("AB", "AN"), ("AO", "BB")]: ws.merge_cells(f"{a}{r1}:{z}{r1+1}")
        spans = []
        for i, r in enumerate(b.get("rows") or [], 1):
            g = r.get("group") or None
            rr = s.emit(29, {"C": i, "E": g, "K": r.get("item"), "U": r.get("state"), "AB": r.get("value"), "AO": r.get("note") or ""})
            if g or not spans: spans.append([rr, rr])
            else: spans[-1][1] = rr
        for a, z in spans: ws.merge_cells(f"E{a}:J{z}")
    else:
        die(f"不明な block kind: {k!r}（step/text/ref/api/params/display）")


def ops(ws, src, sc, spec):
    hdr(ws, sc["id"], "op", spec)
    s = Sheet(ws, src, start=5, blank_row=4)
    s.emit(5, {"A": "起動パラメータ"})
    s.emit(6, {"A": "項番", "C": "論理名", "P": "備考"})
    params = sc.get("params") or []
    if params:
        for i, p in enumerate(params, 1): s.emit(7, {"A": i, "C": p.get("name"), "P": p.get("note")})
    else:
        s.emit(7, {"A": "-", "C": "なし"})
    s.emit_blank(); s.emit(9, {"A": "操作概要"})
    for n, ev in enumerate(sc.get("events") or [], 1):
        s.emit(10, {"A": "処理名", "H": title_of(ev, n)}); s.emit_blank()
        for b in ev.get("steps") or []: block(s, ws, b)
        s.emit_blank()
    ws.print_area = f"A1:BJ{s.r}"


def main():
    ap = argparse.ArgumentParser(description="設計書 JSON → 画面設計書 xlsx")
    ap.add_argument("spec"); ap.add_argument("-o", "--out")
    ap.add_argument("--template", default=os.path.join(HERE, "templates", "画面設計書_模板.xlsx"))
    args = ap.parse_args()
    spec = load_spec(args.spec); validate(spec, args.spec)
    screens = spec.get("screens") or []
    if not screens: die("screens が空です")
    base_dir = os.path.dirname(os.path.abspath(args.spec))
    src = openpyxl.load_workbook(args.template); dst = openpyxl.load_workbook(args.template)
    doc = spec.get("screen_doc") or {}
    if spec.get("system"): dst["表紙"]["J5"] = spec["system"]
    dst["表紙"]["J13"] = doc.get("feature_label") or spec["feature"]
    write_history(dst["変更履歴"], spec, doc.get("id") or screens[0]["id"], doc=doc)
    tail = [n for n in dst.sheetnames if n not in ["表紙", "変更履歴"] + BASE]
    sets = []
    for i, sc in enumerate(screens):
        ws3 = [dst[b] if i == 0 else dst.copy_worksheet(dst[b]) for b in BASE]
        sets.append((sc, ws3))
    order = ["表紙", "変更履歴"]
    for sc, ws3 in sets:
        suf = sc["sheet_suffix"] if "sheet_suffix" in sc else (sc["name"] if len(screens) > 1 else "")
        for b, ws in zip(BASE, ws3):
            ws.title = sheet_title(f"{b}（{suf}）" if suf else b)
            order.append(ws.title)
    dst._sheets = [dst[n] for n in order + tail]
    for sc, (wl, wi, wo) in sets:
        layout(wl, src["レイアウト"], sc, spec, base_dir)
        items(wi, src["画面項目"], sc, spec)
        ops(wo, src["画面操作詳細"], sc, spec)
    strip_props(dst)
    out = out_path(args.spec, doc, "画面設計書", args.out)
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    dst.save(out); print(out)


if __name__ == "__main__":
    main()
