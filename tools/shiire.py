#!/usr/bin/env python3
"""仕入れ元の選び方（土台③）… 注文ごとに、使える仕入れ元の中からいちばん手残りが多い口を選ぶ

  python3 shiire.py --selftest

決めたこと
  ① 既定の仕入れ元は Amazon ビジネス（Ordering API で機械が買える・請求書が真贋調査の証拠になる）
  ② 卸（NETSEA 等）は【会員登録が済んで config/oroshi.json に鍵がある時だけ】候補に入れる
     … 登録はオーナーの事務作業。登録前は Amazon だけで回る
     … 卸は「消費者直送可（ds_flg=Y）」の品だけ・直送先は HANIRO の倉庫
  ③ 同じ品が複数の口にあれば「仕入れ値＋日本国内の送料」が安い方。差が小さい（3%未満）なら Amazon
     （納期が安定し、請求書の形が揃うため）
  ④ どの口も在庫が無ければ仕入れない（orders.py が「取り消し候補」にする）
"""
import json, os, sys
import paths

OROSHI_CONF = paths.conf("oroshi.json")


def oroshi_ready():
    return os.path.exists(OROSHI_CONF)


def choose(offers, oroshi_ok=None):
    """offers … [{src:"amazon"|"netsea", stock, jpy, ship_jpy, ds_ok(卸のみ)}] → 選んだ1件 or None"""
    oroshi_ok = oroshi_ready() if oroshi_ok is None else oroshi_ok
    ok = []
    for o in offers:
        if not o.get("stock"):
            continue
        if o["src"] != "amazon" and (not oroshi_ok or not o.get("ds_ok")):
            continue
        ok.append({**o, "total": o["jpy"] + o.get("ship_jpy", 0)})
    if not ok:
        return None
    best = min(ok, key=lambda o: o["total"])
    amz = next((o for o in ok if o["src"] == "amazon"), None)
    if amz and best is not amz and amz["total"] <= best["total"] * 1.03:
        return amz
    return best


def selftest():
    bad = 0
    A = {"src": "amazon", "stock": 5, "jpy": 10000, "ship_jpy": 0}
    N = {"src": "netsea", "stock": 5, "jpy": 8000, "ship_jpy": 700, "ds_ok": True}
    cases = [
        ([A, N], False, "amazon", "卸が未登録なら Amazon"),
        ([A, N], True, "netsea", "卸が登録済みで8,700円 < 10,000円なら卸"),
        ([A, {**N, "jpy": 9500}], True, "amazon", "差が3%未満なら Amazon"),
        ([{**A, "stock": 0}, {**N, "ds_ok": False}], True, None, "在庫なし・直送不可なら仕入れない"),
    ]
    for offers, reg, want, name in cases:
        got = (choose(offers, reg) or {}).get("src")
        bad += got != want
        print("✅" if got == want else "🔴", name, "→", got)
    print("不一致", bad, "件")
    return bad


if __name__ == "__main__":
    sys.exit(1 if selftest() else 0)
