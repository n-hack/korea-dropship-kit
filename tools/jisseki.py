#!/usr/bin/env python3
"""実績の台帳 … 1注文ごとに「オーナーの手元に残った額」を実額で残し、月ごとに足す（物差しは利益額）

  python3 jisseki.py --selftest
  python3 jisseki.py --month 2026-10      … その月の合計

1行 … 注文番号・売値（ウォン）・入金（円・実額）・仕入れ（円・Amazon の請求書）・HANIRO の請求（円）・返品や取消の損（円）・還付の見込み（仕入れ×10/110）
見込み（rieki.calc）と実額を並べて残す → 見込みの式がずれていないかを毎月確かめる（安全側を重ねすぎていないか）
"""
import sys, json, datetime
import paths

LEDGER = paths.data("jisseki.jsonl")
MUST = ["order", "date", "krw", "nyukin_jpy", "shiire_jpy", "haniro_jpy"]


def add(rec, path=LEDGER):
    miss = [k for k in MUST if rec.get(k) in (None, "")]
    if miss:
        raise ValueError(f"実績に欠け: {miss}")
    rec = dict(rec)
    rec.setdefault("son_jpy", 0)
    rec["kanpu_jpy"] = round(rec["shiire_jpy"] * 10 / 110)
    rec["rieki_jpy"] = rec["nyukin_jpy"] - rec["shiire_jpy"] - rec["haniro_jpy"] - rec["son_jpy"] + rec["kanpu_jpy"]
    with open(path, "a") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return rec


def month(ym, path=LEDGER):
    rows = []
    try:
        rows = [json.loads(l) for l in open(path) if json.loads(l)["date"].startswith(ym)]
    except FileNotFoundError:
        pass
    tot = sum(r["rieki_jpy"] for r in rows)
    mik = sum(r.get("mikomi_jpy", 0) for r in rows)
    return {"件数": len(rows), "利益_円": tot, "見込みの合計_円": mik, "見込みとの差_円": tot - mik}


def selftest():
    import tempfile, os
    p = tempfile.mktemp()
    bad = 0
    r = add({"order": "C1", "date": "2026-10-03", "krw": 303420, "nyukin_jpy": 31500, "shiire_jpy": 22330,
             "haniro_jpy": 1120, "mikomi_jpy": 9074}, p)
    ok = r["rieki_jpy"] == 31500 - 22330 - 1120 + round(22330 * 10 / 110)
    bad += not ok
    print("✅" if ok else "🔴", "1件の利益＝入金−仕入れ−送料−損＋還付", r["rieki_jpy"])
    m = month("2026-10", p)
    ok = m["件数"] == 1 and m["見込みとの差_円"] == r["rieki_jpy"] - 9074
    bad += not ok
    print("✅" if ok else "🔴", "月の合計と見込みとの差", m)
    try:
        add({"order": "C2", "date": "2026-10-04"}, p); print("🔴 欠けがあっても入った"); bad += 1
    except ValueError:
        print("✅ 欠けがあれば止まる")
    os.remove(p)
    print("不一致", bad, "件")
    return bad


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        sys.exit(1 if selftest() else 0)
    if "--month" in sys.argv:
        print(month(sys.argv[sys.argv.index("--month") + 1]))
