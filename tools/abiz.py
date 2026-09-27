#!/usr/bin/env python3
"""Amazon ビジネス Ordering API で仕入れを発注する（届け先＝HANIRO 福岡倉庫）

  python3 abiz.py --selftest    … 発注データの形と止める条件を検体で確かめる（ネットに出ない・お金は動かない）

正本 … docs.business.amazon.com「Ordering API overview」（2026-09-27 取得）
  POST /ordering/2022-10-30/orders（リージョン FE＝JP）・認証は Login with Amazon（OAuth 2.0）
  役割 AmazonBusinessOrderPlacement を申請／届け先は事前に登録・許可した住所だけ（未許可の住所はエラー）
  body … externalId ／ lineItems[{externalId, quantity, attributes:[SelectedProductReference{ProductIdentifier=ASIN}]}]
お金が動くので、ここは必ず止める条件を先に置く
  オーナーの方針（既定）「売れてから買うので、1件ごとの確認はいらない。AIが買ってよい」… 変えたければ MAX_ONE・HUMAN_FIRST を設定
    「売れてから買うんだったら上限なしでいい」→ 1件の上限と人の確認は【置かない】（既定0＝無効）
  残すのは ① 1日の合計の上限（機械の桁間違いが一晩で増えるのを止める栓）② 同じ注文を2回発注しない
鍵 … 登録後に config/abiz.json。まだ無いので send は動かない
"""
import sys, json, os
import paths

PATH = "/ordering/2022-10-30/orders"
LEDGER = paths.data("abiz_ledger.jsonl")
MAX_ONE, MAX_DAY, HUMAN_FIRST = 0, 300000, 0  # 0＝その関門は無効。1日の合計の栓は30万円から（カード枠1,000万円の3%・枠に合わせて変える）


def build(order_id, asin, qty):
    return {
        "externalId": f"cp-{order_id}-{asin}",
        "lineItems": [{
            "externalId": f"cp-{order_id}-{asin}-1",
            "quantity": qty,
            "attributes": [{"attributeType": "SelectedProductReference",
                            "productReference": {"productReferenceType": "ProductIdentifier", "id": asin}}],
            "expectations": [],
        }],
        "attributes": [],   # 届け先（HANIRO の許可済み住所）・支払い方法は登録後に Amazon ビジネス側の設定を指す
        "expectations": [],
    }


def offer_to_detail(asin, offers):
    """Product Search API（getProductsByAsins／searchOffersRequest）の offers → watch.py が使う形
    公式の欄 … price.amount ／ merchant.name ／ availability ／ shippingOptions[].shippingCost ／ condition
    送料込みの一番安い新品を選ぶ（kp.py の送料800円の見込みを実額に置き換える）"""
    best = None
    for o in offers or []:
        cond = o.get("condition")
        cond = cond.get("conditionValue") if isinstance(cond, dict) else cond  # 欄の形は登録後に実物で確かめる
        if cond not in ("NEW", "New", None):
            continue
        price = ((o.get("price") or {}).get("value") or o.get("price") or {}).get("amount")
        if price is None:
            continue
        ship = min([((s.get("shippingCost") or {}).get("amount") or 0) for s in (o.get("shippingOptions") or [])] or [0])
        total = float(price) + float(ship)
        if best is None or total < best[0]:
            best = (total, o)
    if not best:
        return {"asin": asin, "stock": 0, "jpy": None, "seller": "", "amazon_honntai": False, "weight_g": None}
    name = ((best[1].get("merchant") or {}).get("name")) or ""
    return {"asin": asin, "stock": 99, "jpy": round(best[0]), "seller": name,
            "amazon_honntai": name.startswith("Amazon"), "weight_g": None, "soryo_mikomi": False}


def gate(plan, ledger, today_total, sent_count):
    """plan … orders.py の「仕入れる」1件 → (送ってよいか, 理由)"""
    key = f"{plan['orderId']}-{plan['asin']}"
    amount = plan["jpy"] * plan.get("qty", 1)
    if any(l.get("key") == key for l in ledger):
        return False, "同じ注文はもう発注済み"
    if MAX_ONE and amount > MAX_ONE:
        return False, f"1件 {amount}円 が上限 {MAX_ONE}円 を超える"
    if today_total + amount > MAX_DAY:
        return False, f"今日の合計が上限 {MAX_DAY}円 を超える"
    if sent_count < HUMAN_FIRST:
        return False, f"最初の{HUMAN_FIRST}件は人の確認待ち（{sent_count + 1}件目）"
    return True, "発注してよい"


def selftest():
    base = {"orderId": 1, "asin": "B0088B5FTE", "jpy": 1329, "qty": 1}
    cases = [
        ((base, [], 0, 10), True),
        ((base, [{"key": "1-B0088B5FTE"}], 0, 10), False),   # 同じ注文は2回買わない
        (({**base, "jpy": 35000}, [], 0, 10), True),         # 1件の上限は置かない（既定）
        ((base, [], 299000, 10), False),                     # 1日の合計の栓
        ((base, [], 0, 0), True),                            # 1件目から人の確認なしで買う（既定）
    ]
    bad = 0
    for args, want in cases:
        ok, why = gate(*args)
        bad += ok != want
        print("✅" if ok == want else "🔴", why)
    d = offer_to_detail("X", [
        {"condition": "NEW", "price": {"value": {"amount": 1200}}, "merchant": {"name": "他店"}, "shippingOptions": [{"shippingCost": {"amount": 500}}]},
        {"condition": "NEW", "price": {"value": {"amount": 1400}}, "merchant": {"name": "Amazon.co.jp"}, "shippingOptions": [{"shippingCost": {"amount": 0}}]},
        {"condition": "USED", "price": {"value": {"amount": 500}}, "merchant": {"name": "中古屋"}},
    ])
    for good, name in [(d["jpy"] == 1400, "送料込みで一番安い新品（1,200＋500より1,400）"), (d["amazon_honntai"], "Amazon本体"),
                       (offer_to_detail("Y", [])["stock"] == 0, "出品が無ければ在庫0")]:
        bad += not good
        print("✅" if good else "🔴", name)
    b = build(1, "B0088B5FTE", 2)
    li = b["lineItems"][0]
    for good, name in [(li["quantity"] == 2, "数量"), (li["attributes"][0]["productReference"]["id"] == "B0088B5FTE", "ASIN"),
                       (b["externalId"] == "cp-1-B0088B5FTE", "注文の見分け番号")]:
        bad += not good
        print("✅" if good else "🔴", name)
    print("不一致", bad, "件")
    return bad


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        sys.exit(1 if selftest() else 0)
    print(__doc__)
