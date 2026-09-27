#!/usr/bin/env python3
"""売れ方の集計 … 出品の台帳と注文から、分類ごとの「売れる割合」と「1件の利益」を出し、次に増やす分類を決める

  python3 urekata.py --selftest

なぜ … 売れる割合は出品してみないと分からない（SCHEME の最大の未知）。月ごとに数え、売れた分類を増やし、売れない品は入れ替える
  売れる割合 ＝ その月に売れた件数 ÷ その月に出品していた件数
  判断 … 割合と1件の利益の積（＝出品1件あたりの月の利益）が高い分類から枠を配る。30日以上売れていない品は入れ替え候補
"""
import sys
from collections import defaultdict


def summarize(listings, orders):
    """listings … [{asin, cat, days}]（days＝その月に出ていた日数）／ orders … [{asin, profit}]"""
    n = defaultdict(float)
    for l in listings:
        n[l["cat"]] += l.get("days", 30) / 30
    cat_of = {l["asin"]: l["cat"] for l in listings}
    sold, prof = defaultdict(int), defaultdict(float)
    for o in orders:
        c = cat_of.get(o["asin"], "?")
        sold[c] += 1
        prof[c] += o["profit"]
    out = []
    for c in n:
        rate = sold[c] / n[c] if n[c] else 0
        per = prof[c] / sold[c] if sold[c] else 0
        out.append({"cat": c, "出品": round(n[c]), "売れた": sold[c], "売れる割合": round(rate, 4),
                    "1件の利益": round(per), "出品1件あたり月の利益": round(rate * per)})
    return sorted(out, key=lambda x: -x["出品1件あたり月の利益"])


def stale(listings, sold_asins, days=30):
    return [l["asin"] for l in listings if l.get("age", 0) >= days and l["asin"] not in sold_asins]


def selftest():
    L = [{"asin": f"g{i}", "cat": "golf", "days": 30, "age": 40} for i in range(100)] + \
        [{"asin": f"w{i}", "cat": "watch", "days": 30, "age": 10} for i in range(100)]
    O = [{"asin": "g1", "profit": 8000}, {"asin": "g2", "profit": 9000}] + [{"asin": f"w{i}", "profit": 1000} for i in range(5)]
    s = summarize(L, O)
    bad = 0
    ok = s[0]["cat"] == "golf" and s[0]["出品1件あたり月の利益"] == 170
    bad += not ok
    print("✅" if ok else "🔴", "売れた数が少なくても利益の大きい分類が上に来る", s)
    st = stale(L, {"g1", "g2"})
    ok = len(st) == 98 and "g1" not in st
    bad += not ok
    print("✅" if ok else "🔴", "30日以上売れていない品を入れ替え候補に（98件）")
    print("不一致", bad, "件")
    return bad


if __name__ == "__main__":
    sys.exit(1 if selftest() else 0)
