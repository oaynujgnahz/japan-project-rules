#!/usr/bin/env python3
"""設計書 JSON → API設計書 xlsx。

使い方:
  python3 export_api.py docs/{機能}/design.json [-o 出力.xlsx] [--template templates/API設計書_模板.xlsx]
出力の既定値: JSON と同じフォルダの API設計書_{フォルダ名}.xlsx（api_doc.file_name で変更可）
"""
import argparse, copy, os, warnings
import openpyxl
warnings.filterwarnings("ignore")
from tpl import validate, Sheet, Proto, HERE, die, load_spec, out_path, sheet_title, title_of, write_history, strip_props

# [CMPF] 版式：原型行号对应按 CMPF 样本做的 API 模板；换公司模板要重新标行号（将来移到 project.json）
# テンプレート「API（サンプル）」シートの原型行
R_BLANK = 4
R_SEC, R_URL, R_NAME = 5, 6, 7
R_REQ, R_REQ_H, R_REQ_ROW = 9, 10, 11
R_RES, R_RES_H, R_RES_ROW, R_RES_CHILD = 24, 25, 26, 27
R_OPS = 49
R_STEP, R_TEXT, R_LABEL = 51, 52, 53
R_TBL_H, R_TBL_ROW = 54, 55
R_SQL_H, R_SQL_ROW = 66, 67
R_FROM, R_JOIN = 72, 88
R_COND1, R_COND = 75, 95
R_SET_H, R_SET_TOP, R_SET_ROW = 203, 204, 205
R_RESULT = 228
H_ITEM = {"A": "項番", "C": "論理名", "P": "物理名", "AE": "データ型", "AH": "備考"}


def table(s, headers, rows):
    h = (list(headers) + [None] * 4)[:4]
    s.emit(R_TBL_H, {"D": h[0] or "項番", "F": h[1], "Q": h[2], "AB": h[3]})
    for i, r in enumerate(rows, 1):
        s.emit(R_TBL_ROW, {"D": i, "F": r[0], "Q": r[1], "AB": r[2] if len(r) > 2 else None})


def sql(s, b):
    lab = b.get("labels") or {}
    if b.get("select"):
        s.emit(R_TEXT, {"C": lab.get("select", "検索SQL")})
        s.emit(R_SQL_H, {"C": "項番", "E": "テーブル", "O": "取得項目名", "AC": "備考"})
        for i, x in enumerate(b["select"], 1):
            s.emit(R_SQL_ROW, {"C": i, "E": x.get("table"), "O": x.get("item"), "AC": x.get("note")})
    if b.get("tables"):
        s.emit(R_TEXT, {"C": lab.get("tables", "検索テーブル")})
        for i, t in enumerate(b["tables"], 1):
            if t.get("join"):
                s.emit(R_JOIN, {"C": i, "E": t.get("name"), "R": t["join"], "X": t.get("on")})
            else:
                s.emit(R_FROM, {"C": i, "E": t.get("name")})
    if b.get("where"):
        s.emit(R_TEXT, {"C": lab.get("where", "検索条件")})
        for i, w in enumerate(b["where"]):
            op = w.get("op", "=")
            v = {"H": w.get("item"), "V": (" " + op) if op else "", "AB": w.get("value")}
            if i == 0: s.emit(R_COND1, v)
            else: v["E"] = w.get("conj", "AND"); s.emit(R_COND, v)
    for key, label in (("group", "グループ"), ("sort", "ソート")):
        if b.get(key):
            s.emit(R_TEXT, {"C": lab.get(key, label)})
            for x in b[key]:
                if isinstance(x, str): x = {"item": x}
                s.emit(R_COND1, {"H": x.get("item"), "V": "", "AB": x.get("order")})


def block(s, b):
    k = b.get("kind")
    if k == "text": s.emit(R_TEXT, {"C": b["text"]})
    elif k == "label": s.emit(R_LABEL, {"D": b["text"]})
    elif k == "gap": s.gap(b.get("n", 1))
    elif k == "check":
        table(s, b.get("headers") or ["項番", "チェック項目", "エラー条件", "備考"],
              [[r.get("name"), r.get("condition"), r.get("note")] for r in b["rows"]])
    elif k == "table":
        table(s, b.get("headers") or ["項番", "項目", "内容", "備考"],
              [r.get("cols") if isinstance(r, dict) else r for r in b["rows"]])
    elif k == "set":
        table(s, b.get("headers") or ["項番", "項目", "設定値", "備考"],
              [[r.get("item"), r.get("value"), r.get("note")] for r in b["rows"]])
    elif k == "sql": sql(s, b)
    elif k == "response":
        s.emit(R_SET_H, {"C": "項番", "E": "レスポンス", "R": "設定値"})
        for i, r in enumerate(b["rows"], 1):
            if r.get("level") == 1: s.emit(R_SET_TOP, {"C": i, "E": r.get("item"), "R": r.get("value")})
            else: s.emit(R_SET_ROW, {"C": i, "F": r.get("item"), "R": r.get("value")})
    elif k == "result":
        for r in b["rows"]: s.emit(R_RESULT, {"C": r.get("item"), "H": "←", "J": r.get("value")})
    else:
        die(f"不明な block kind: {k!r}（text/label/check/table/set/sql/response/result/gap）")


def items(s, rows):
    for i, r in enumerate(rows, 1):
        if r.get("child"):
            s.emit(R_RES_CHILD, {"A": i, "D": r.get("name"), "P": r.get("physical"), "AE": r.get("data_type"), "AH": r.get("note")})
        else:
            s.emit(R_REQ_ROW if s._sec == "req" else R_RES_ROW,
                   {"A": i, "C": r.get("name"), "P": r.get("physical"), "AE": r.get("data_type"), "AH": r.get("note")})


def render_api(ws, src, a):
    s = Sheet(ws, src, start=5, blank_row=R_BLANK)
    s.emit(R_SEC, {"A": "API情報"})
    s.emit(R_URL, {"A": "URL", "F": a.get("url")})
    disp = a.get("title") or (f"{a['name']}（{a['method']}）" if a.get("method") else a["name"])
    s.emit(R_NAME, {"A": "名称", "F": disp})
    s.gap()
    req = a.get("request") or {}
    s.emit(R_REQ, {"A": "リクエスト", "H": req.get("note", "（タイプ\u3000⇒\u3000G:グループ、e:要素）")})
    s.emit(R_REQ_H, H_ITEM); s._sec = "req"; items(s, req.get("items") or [])
    s.gap()
    res = a.get("response") or {}
    s.emit(R_RES, {"A": "レスポンス", "H": res.get("note", "（タイプ\u3000⇒\u3000G:グループ）")})
    s.emit(R_RES_H, H_ITEM); s._sec = "res"; items(s, res.get("items") or [])
    s.gap()
    s.emit(R_OPS, {"A": "操作概要"}); s.gap()
    steps = a.get("steps") or []
    for n, st in enumerate(steps, 1):
        s.emit(R_STEP, {"B": title_of(st, n)})
        for b in st.get("body") or []: block(s, b)
        if n < len(steps): s.gap()
    ws.print_area = f"A1:BJ{s.r}"


def main():
    ap = argparse.ArgumentParser(description="設計書 JSON → API設計書 xlsx")
    ap.add_argument("spec"); ap.add_argument("-o", "--out")
    ap.add_argument("--template", default=os.path.join(HERE, "templates", "API設計書_模板.xlsx"))
    args = ap.parse_args()
    spec = load_spec(args.spec); validate(spec, args.spec)
    apis = spec.get("apis") or []
    if not apis: die("apis が空です")
    src = openpyxl.load_workbook(args.template); dst = openpyxl.load_workbook(args.template)
    proto_name = [n for n in dst.sheetnames if n.startswith("API（")][0]
    doc = spec.get("api_doc") or {}
    if spec.get("system"): dst["表紙"]["J5"] = spec["system"]
    dst["表紙"]["J13"] = doc.get("feature_label") or spec["feature"]
    write_history(dst["変更履歴"], spec, doc.get("id") or apis[0]["id"], doc=doc)
    # API一覧
    l = dst["API一覧"]; p7 = Proto(src["API一覧"], 7)
    for i, a in enumerate(apis):
        r = 7 + i
        if i:
            for c, st in p7.styles.items(): l.cell(r, c)._style = copy.copy(st)
            for x, y in p7.merges:
                if not any(m.min_row == r and m.min_col == x for m in l.merged_cells.ranges):
                    l.merge_cells(start_row=r, start_column=x, end_row=r, end_column=y)
            l[f"A{r}"] = "=ROW()-6"
        l[f"C{r}"] = a["name"]; l[f"X{r}"] = a.get("summary")
    # API シート（2 本目以降はコピー）
    sheets = [dst[proto_name]] + [dst.copy_worksheet(dst[proto_name]) for _ in apis[1:]]
    for ws, a in zip(sheets, apis):
        ws.title = sheet_title(a.get("sheet") or f"API（{a['name']}）")
        render_api(ws, src[proto_name], a)
    strip_props(dst)
    out = out_path(args.spec, doc, "API設計書", args.out)
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    dst.save(out); print(out)


if __name__ == "__main__":
    main()
