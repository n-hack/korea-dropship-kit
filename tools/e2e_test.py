#!/usr/bin/env python3
"""部品を1本につないで、候補から証拠の保存までを検体で通す（ネットに出ない・お金は動かない）

  python3 e2e_test.py

流れ … 候補 → 出せない品を外す(kc) → 利益(rieki) → 下限の売値(floor_krw) → 出す順と数(pace)
      → 出品データ(coupang.build) → 注文が来た(orders.plan) → 発注してよいか(abiz.gate)
      → 発注データ(abiz.build) → 証拠を台帳に(shoko.add) → 問い合わせ(cs.draft)
"""
import sys, tempfile, os
import kc, rieki, pace, coupang, orders, abiz, shoko, cs

R = dict(rate=0.116015, usd=0.000737)
cands = [
    {"asin": "A1", "title": "シマノ スピニングリール 23 セドナ C3000", "brand": "shimano", "jpy": 6000, "kg": 0.4, "krw": 90000},
    {"asin": "A2", "title": "Anker USB急速充電器 20W スマホ 充電器", "brand": "anker", "jpy": 2000, "kg": 0.2, "krw": 60000},
    {"asin": "A3", "title": "スノーピーク チタンシングルマグ", "brand": "snowpeak", "jpy": 3500, "kg": 0.2, "krw": 30000},
]
bad = 0
ok = []
for c in cands:
    j, why = kc.judge(c["title"])
    if j == "止める":
        print("・外した", c["asin"], why); continue
    p = rieki.calc(c["krw"], c["jpy"], c["kg"] * 1.3, **R)["利益_円"]
    if c["krw"] < coupang.MIN_KRW or p < 500:
        print("・外した", c["asin"], f"売値{c['krw']}ウォン・利益{p}円"); continue
    c["profit"] = p
    c["floor"] = rieki.floor_krw(c["jpy"], c["kg"] * 1.3, 500, **R)
    ok.append(c)
bad += [c["asin"] for c in ok] != ["A1"]
print("✅" if [c["asin"] for c in ok] == ["A1"] else "🔴", "残ったのは A1 だけ（A2 は充電器で外す・A3 は5万ウォン未満）")

today = pace.pick(ok, 0, 0)
body = coupang.build({"asin": today[0]["asin"], "title_ko": "시마노 스피닝릴", "krw": today[0]["krw"], "category": 1,
                      "images": ["https://example.com/a.jpg"]}, coupang.DUMMY)
bad += body["items"][0]["externalVendorSku"] != "A1"
print("✅ 出品データに ASIN が入った", "下限の売値", today[0]["floor"])

order = {"orderId": 77, "receiver": {"name": "김", "addr1": "서울", "postCode": "04524"},
         "overseaShippingInfoDto": {"personalCustomsClearanceCode": "P123"},
         "orderItems": [{"externalVendorSkuCode": "A1", "shippingCount": 1}]}
plan = orders.plan(order, lambda a: {"stock": 99, "jpy": 6000, "weight_g": 400}, R["rate"], R["usd"], lambda it: 90000)[0]
bad += plan["act"] != "仕入れる"
print("✅" if plan["act"] == "仕入れる" else "🔴", "注文 → 仕入れる")

go, why = abiz.gate(plan, [], 0, 0)
bad += not go
print("✅" if go else "🔴", "1件目から人の確認なしで発注（既定）：", why)
go, why = abiz.gate(plan, [{"key": "77-A1"}], 0, 1)
bad += go
print("✅" if not go else "🔴", "同じ注文は2回発注しない：", why)
b = abiz.build(plan["orderId"], plan["asin"], plan["qty"])

p = tempfile.mktemp()
shoko.add({"kounyusaki": "Amazon.co.jp", "date": "2026-10-01", "asin": "A1", "title": cands[0]["title"], "qty": 1,
           "jpy": 6000, "amazon_order": "250-1", "coupang_order": "77"}, p)
bad += len(shoko.find("77", p)) != 1
print("✅ 証拠が注文番号で引ける")
os.remove(p)

c, body = cs.draft("언제 도착하나요?")
bad += c != "配送"
print("✅ 問い合わせ → 定型の回答")
print("不一致", bad, "件")
sys.exit(1 if bad else 0)
