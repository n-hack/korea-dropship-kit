#!/usr/bin/env python3
"""HANIRO の配送申請ファイルを作る … orders.plan の「haniro」材料を、一括アップロード用の表にする

  python3 haniro.py --selftest

HANIRO は Excel 一括アップロードで配送申請できる（公式の手順：見本を落とす→赤い列が必須→アップロード→失敗行はエラー表で直して再送）
見本の列名はログイン後にしか取れない → 列の対応表を config/haniro_cols.json に置き、会員登録後に見本に合わせて書き換える
  （対応表が無い間は、項目名をそのまま列名にした仮の表を作る＝中身の検算はできる・アップロードはしない）
アップロードはブラウザで行う（API は公式に記載なし）。エージェントがブラウザを操作できるなら任せてよい
"""
import csv, json, os, sys
import paths

COLS_CONF = paths.conf("haniro_cols.json")
FIELDS = ["receiver", "zip", "addr", "phone", "pcc", "item", "qty", "price_jpy", "tracking_jp", "order_ref"]
MUST = ["receiver", "zip", "addr", "phone", "pcc", "item", "qty", "price_jpy"]


def cols():
    try:
        return json.load(open(COLS_CONF))
    except (FileNotFoundError, ValueError):
        return {f: f for f in FIELDS}   # 仮（見本の列名が分かるまで）


def rows_from(plans):
    """plans … orders.plan の出力のうち act=="仕入れる" のもの → 表の行（欠けがあれば止める）"""
    out, bad = [], []
    for p in plans:
        h = dict(p.get("haniro") or {})
        h["order_ref"] = f"{p.get('orderId')}-{p.get('asin')}"
        miss = [k for k in MUST if h.get(k) in (None, "")]
        if miss:
            bad.append((h["order_ref"], miss))
            continue
        out.append(h)
    return out, bad


def write(rows, path):
    m = cols()
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow([m.get(k, k) for k in FIELDS])
        for r in rows:
            w.writerow([r.get(k, "") for k in FIELDS])
    return path


def selftest():
    import tempfile
    bad = 0
    plans = [{"orderId": 1, "asin": "A1", "act": "仕入れる", "haniro": {"receiver": "김", "zip": "04524", "addr": "서울 1",
              "phone": "050-1", "pcc": "P1", "item": "우타마로", "qty": 1, "price_jpy": 1329}},
             {"orderId": 2, "asin": "A2", "act": "仕入れる", "haniro": {"receiver": "이", "zip": "", "addr": "부산",
              "phone": "050-2", "pcc": "P2", "item": "x", "qty": 1, "price_jpy": 100}}]
    rows, ng = rows_from(plans)
    ok = len(rows) == 1 and ng == [("2-A2", ["zip"])]
    bad += not ok
    print("✅" if ok else "🔴", "郵便番号の欠けた注文は表に入れず、どの欄が欠けたかを返す", ng)
    fd, p = tempfile.mkstemp(suffix=".csv")
    os.close(fd)
    p = write(rows, p)
    txt = open(p, encoding="utf-8-sig").read()
    ok = "1-A1" in txt and "P1" in txt and txt.splitlines()[0].startswith("receiver")
    bad += not ok
    print("✅" if ok else "🔴", "表に注文の印と通関番号が入る")
    os.remove(p)
    print("不一致", bad, "件")
    return bad


if __name__ == "__main__":
    sys.exit(1 if selftest() else 0)
