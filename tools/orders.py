#!/usr/bin/env python3
"""受注 → 仕入れ指示 → HANIRO 配送申請の材料（売れた瞬間に回す部分）

  python3 orders.py --selftest    … 検体の注文で「仕入れ指示」と「配送申請の材料」を作って確かめる（ネットに出ない）
  python3 orders.py poll          … クーパンの新しい注文（ACCEPT）を取り、指示を出す（鍵が要る・まだ動かない）

正本 … developers.coupang.com「PO List Query」（2026-09-27 取得）
  GET /v2/providers/openapi/apis/api/v5/vendors/{vendorId}/ordersheets?createdAtFrom&createdAtTo&status=ACCEPT
  受取人 … receiver.name / addr1 / addr2 / postCode / safeNumber
  個人通関番号 … overseaShippingInfoDto.personalCustomsClearanceCode
  品 … orderItems[].externalVendorSkuCode（出品時に ASIN を入れてある）/ shippingCount
流れ
  ① 注文ごとに ASIN の今の在庫と値段を見る（kp.detail＝Keepa API）
  ② 在庫なし／利益が下限割れ → 仕入れず「取り消し候補」（取消率1%以下を守るため見張りで先に止めておくのが本筋）
  ③ 仕入れる → Amazon の届け先は HANIRO（My HANIRO アドレス）・受取人名は会員名（HANIRO 公式 STEP2）
  ④ HANIRO の配送申請の材料（韓国の受取人・個人通関番号・品名・数量・価格）を作る
Amazon での購入は Amazon ビジネスの Ordering API（abiz.py）で行う。最初の数件は人が確かめてから自動に切り替える
"""
import sys, json
import paths
import rieki

CONF = paths.conf("coupang.json")


def plan(order, detail, rate, usd, krw_of_item, min_profit=500, customs_ok=False):
    """customs_ok … 出品で関税を告知済み（kanzei_ok.mark）の品は保留にしない"""
    """1注文 → 仕入れ指示か取り消し候補"""
    out = []
    rc = order["receiver"]
    pcc = (order.get("overseaShippingInfoDto") or {}).get("personalCustomsClearanceCode", "")
    for it in order["orderItems"]:
        asin = it["externalVendorSkuCode"]
        d = detail(asin)
        n = it.get("shippingCount", 1)
        if d["stock"] < n or not d["jpy"]:
            out.append({"orderId": order["orderId"], "asin": asin, "act": "取り消し候補", "why": "仕入れ元に在庫なし"})
            continue
        c = rieki.calc(krw_of_item(it), d["jpy"] * n, (d["weight_g"] or 1500) / 1000 * 1.3 * n, rate=rate, usd=usd)
        if c["利益_円"] < min_profit:
            out.append({"orderId": order["orderId"], "asin": asin, "act": "取り消し候補", "why": f"利益{c['利益_円']}円"})
            continue
        if not pcc:
            out.append({"orderId": order["orderId"], "asin": asin, "act": "保留", "why": "個人通関番号が無い（買い手に確認）"})
            continue
        if c["関税の確認が要る"] and not customs_ok:
            # 韓国無在庫の講師（11年）「関税がかかる品は、仕入れる前に買い手へ確認し、了承を得てから買う。これで4〜5年関税トラブル0件」
            # 了承が無いまま買うと、韓国の税関で買い手に請求が行きクレーム・返品になる → 仕入れずに保留し、確認を送る
            out.append({"orderId": order["orderId"], "asin": asin, "act": "保留",
                        "why": "関税がかかる見込み（仕入れ値が150ドル超）→ 買い手の了承を得てから仕入れる"})
            continue
        out.append({"orderId": order["orderId"], "shipmentBoxId": order.get("shipmentBoxId"), "asin": asin,
                    "act": "仕入れる", "qty": n, "jpy": d["jpy"], "profit": c["利益_円"],
                    "customs_check": c["関税の確認が要る"],
                    "haniro": {"receiver": rc["name"], "zip": rc["postCode"], "addr": (rc["addr1"] + " " + rc.get("addr2", "")).strip(),
                               "phone": rc.get("safeNumber", ""), "pcc": pcc, "item": it.get("sellerProductName", ""),
                               "qty": n, "price_jpy": d["jpy"]}})
    return out


def selftest():
    orders = [
        {"orderId": 1, "shipmentBoxId": 11, "receiver": {"name": "김", "addr1": "서울", "addr2": "1", "postCode": "04524", "safeNumber": "050-1"},
         "overseaShippingInfoDto": {"personalCustomsClearanceCode": "P123456789012"},
         "orderItems": [{"externalVendorSkuCode": "OK", "shippingCount": 1, "sellerProductName": "우타마로"}]},
        {"orderId": 2, "receiver": {"name": "이", "addr1": "부산", "postCode": "1"}, "overseaShippingInfoDto": {"personalCustomsClearanceCode": "P1"},
         "orderItems": [{"externalVendorSkuCode": "NOSTOCK", "shippingCount": 1}]},
        {"orderId": 3, "receiver": {"name": "박", "addr1": "대구", "postCode": "1"}, "overseaShippingInfoDto": {"personalCustomsClearanceCode": "P1"},
         "orderItems": [{"externalVendorSkuCode": "UP", "shippingCount": 1}]},
        {"orderId": 4, "receiver": {"name": "최", "addr1": "인천", "postCode": "1"},
         "orderItems": [{"externalVendorSkuCode": "OK", "shippingCount": 1}]},
        {"orderId": 5, "receiver": {"name": "정", "addr1": "서울", "postCode": "1"}, "overseaShippingInfoDto": {"personalCustomsClearanceCode": "P1"},
         "orderItems": [{"externalVendorSkuCode": "WATCH", "shippingCount": 1}]},
    ]
    fake = {"OK": {"stock": 99, "jpy": 1329, "weight_g": 1000},
            "NOSTOCK": {"stock": 0, "jpy": 1329, "weight_g": 1000},
            "UP": {"stock": 99, "jpy": 3500, "weight_g": 1000},
            "WATCH": {"stock": 99, "jpy": 246400, "weight_g": 300}}
    want = {1: "仕入れる", 2: "取り消し候補", 3: "取り消し候補", 4: "保留", 5: "保留"}
    bad = 0
    for o in orders:
        r = plan(o, lambda a: fake[a], 0.116015, 0.000737, lambda it: 2973550 if it.get("externalVendorSkuCode") == "WATCH" else 34480)[0]
        ok = r["act"] == want[o["orderId"]]
        bad += not ok
        print("✅" if ok else "🔴", o["orderId"], r["act"], r.get("why", ""), r.get("haniro", ""))
    print("不一致", bad, "件")
    return bad


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        sys.exit(1 if selftest() else 0)
    print(__doc__)
