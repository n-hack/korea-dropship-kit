#!/usr/bin/env python3
"""クーパン Open API … 購買代行（AGENT_BUY）の出品データを作り、署名して送る

  python3 coupang.py build cand.json        … 候補1件から出品データ（JSON）を作って表示（送らない）
  python3 coupang.py --selftest             … 署名と出品データの形を検体で確かめる（ネットに出ない）

正本 … developers.coupang.com「Product Creation」「How can I list products as an overseas buying agent?」（2026-09-27 取得）
  POST /v2/providers/seller_api/apis/api/v1/marketplace/seller-products
  購買代行 … deliveryMethod=AGENT_BUY ／ items[].overseasPurchased=OVERSEAS_PURCHASED ／ items[].pccNeeded=true（個人通関番号を客に求める）
  インボイスは2021年3月から必須でない
  externalVendorSku に ASIN を入れる → 売れた注文から仕入れ先を機械で辿れる
鍵 … 販売者登録のあとに config/coupang.json（vendorId・accessKey・secretKey・returnCenterCode・outboundShippingPlaceCode・vendorUserId）
      まだ無いので send は動かない。build と署名は今から使える
"""
import sys, json, hmac, hashlib, time, datetime, urllib.request
import paths

HOST = "https://api-gateway.coupang.com"
PATH = "/v2/providers/seller_api/apis/api/v1/marketplace/seller-products"
CONF = paths.conf("coupang.json")
MIN_KRW = 50000  # クーパンは5万ウォン以下だと返品希望で自動返金（iaRbJIRksaU・語り手）→ これ未満は出さない
SHIP_DAYS = 5  # 出荷（追跡番号を返す）までの日数。HANIRO 公式の配送スケジュール（haniroSchedule）… 倉庫発送は平日毎日・発送から韓国の配達完了まで +4営業日
               # 注文→Amazon ビジネスで購入→HANIRO 着 1〜2日＋入庫・申請 1日＋土日 → 出荷まで5日あれば足りる。遅延出荷率（5%以下）を守るため余裕を持たせた


def sign(method, path, query, access, secret, now=None):
    """CEA HMAC-SHA256（signed-date は UTC の yyMMdd'T'HHmmss'Z'）"""
    dt = (now or datetime.datetime.utcnow()).strftime("%y%m%dT%H%M%SZ")
    msg = dt + method + path + query
    sig = hmac.new(secret.encode(), msg.encode(), hashlib.sha256).hexdigest()
    return f"CEA algorithm=HmacSHA256, access-key={access}, signed-date={dt}, signature={sig}"


def price100(krw):
    return int(round(krw / 100.0)) * 100


def build(c, conf):
    """c … {asin, title_ko, krw, category, images:[url], brand}"""
    sale = price100(c["krw"])
    if sale < MIN_KRW:
        raise ValueError(f"売値 {sale}ウォン は下限 {MIN_KRW} 未満（5万ウォン以下は返品希望で自動返金・語り手）")
    return {
        "displayCategoryCode": c["category"],
        "sellerProductName": c["title_ko"][:100],
        "vendorId": conf["vendorId"],
        "saleStartedAt": datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        "saleEndedAt": "2099-01-01T23:59:59",
        "brand": c.get("brand", ""),
        "deliveryMethod": "AGENT_BUY",
        "deliveryCompanyCode": conf["deliveryCompanyCode"],   # HANIRO なら「ハイムシティ」のコード（登録後に一覧 API で引く）
        "deliveryChargeType": "FREE",
        "deliveryCharge": 0,
        "freeShipOverAmount": 0,
        "deliveryChargeOnReturn": conf["returnFee"],   # 返品の送料（買い手の自己都合・往復の国際送料を見て登録後に決める・推測しない）
        "remoteAreaDeliverable": "N",
        "unionDeliveryType": "NOT_UNION_DELIVERY",
        "returnCenterCode": conf["returnCenterCode"],
        "returnChargeName": conf.get("returnChargeName", "반품지"),
        "companyContactNumber": conf.get("companyContactNumber", ""),
        "returnZipCode": conf.get("returnZipCode", ""),
        "returnAddress": conf.get("returnAddress", ""),
        "returnAddressDetail": conf.get("returnAddressDetail", ""),
        "returnCharge": conf["returnFee"],
        "outboundShippingPlaceCode": conf["outboundShippingPlaceCode"],
        "vendorUserId": conf["vendorUserId"],
        "requested": True,
        "items": [{
            "itemName": c["title_ko"][:150],
            "originalPrice": sale,
            "salePrice": sale,
            "maximumBuyCount": 3,
            "maximumBuyForPerson": 0,
            "maximumBuyForPersonPeriod": 1,
            "outboundShippingTimeDay": SHIP_DAYS,
            "unitCount": 1,
            "adultOnly": "EVERYONE",
            "taxType": "TAX",
            "parallelImported": "NOT_PARALLEL_IMPORTED",
            "overseasPurchased": "OVERSEAS_PURCHASED",
            "pccNeeded": "true",
            "externalVendorSku": c["asin"],
            "images": [{"imageOrder": i, "imageType": "REPRESENTATION" if i == 0 else "DETAIL", "vendorPath": u}
                       for i, u in enumerate(c["images"][:10])],
            "attributes": c.get("attributes", []),
            # 商品告示情報（カテゴリごとの項目は Category meta data API で取る）… 値は「상세페이지 참조」で可（公式の例）
            "notices": [{"noticeCategoryName": n, "noticeCategoryDetailName": d, "content": "상세페이지 참조"}
                        for n, d in c.get("notice_fields", [])],
            # 認証 … KC が要らない品目は NOT_REQUIRED（公式）。KC 不可の品目は kc.py が出品前に外している
            "certifications": [{"certificationType": "NOT_REQUIRED", "certificationCode": ""}],
            "searchTags": [t[:20] for t in c.get("tags", [])][:20],   # 最大20語・各20字（公式）
        }],
    }


VI = "/v2/providers/seller_api/apis/api/v1/marketplace/vendor-items/{vid}"


def act(watch_action, vid, new_krw, conf):
    """watch.py の判断を クーパンの操作に変える（公式）
      止める   … PUT {VI}/sales/stop（本文なし）
      値を直す … PUT {VI}/prices/{price}?forceSalePriceUpdate=true（100ウォン単位）
      続ける   … 何もしない（止めていたら resume は人ではなく次の見張りで判断）"""
    if watch_action == "止める":
        path, q = VI.format(vid=vid) + "/sales/stop", ""
    elif watch_action == "値を直す":
        path, q = VI.format(vid=vid) + f"/prices/{price100(new_krw)}", "forceSalePriceUpdate=true"
    else:
        return None
    auth = sign("PUT", path, q, conf["accessKey"], conf["secretKey"])
    req = urllib.request.Request(HOST + path + (("?" + q) if q else ""), method="PUT",
                                 headers={"Authorization": auth, "Content-Type": "application/json;charset=UTF-8"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def _call(method, path, conf, body=None, q=""):
    auth = sign(method, path, q, conf["accessKey"], conf["secretKey"])
    req = urllib.request.Request(HOST + path + (("?" + q) if q else ""), method=method,
                                 data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Authorization": auth, "Content-Type": "application/json;charset=UTF-8"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def accept(shipment_box_ids, conf):
    """注文を受けたら「商品準備中」にする（公式 ordersheets/acknowledgement・1回50件まで）
    ※ 準備中に変えた後、配送先が変わっていないかを1件ずつ引き直す（公式の注意）"""
    path = f"/v2/providers/openapi/apis/api/v4/vendors/{conf['vendorId']}/ordersheets/acknowledgement"
    return _call("PUT", path, conf, {"vendorId": conf["vendorId"], "shipmentBoxIds": list(shipment_box_ids)[:50]})


def invoice(rows, conf):
    """HANIRO が出した追跡番号を返す（公式 orders/invoices・商品準備中の注文だけ）
    rows … [{shipmentBoxId, orderId, vendorItemId, invoiceNumber}]
    配送会社 … HANIRO を使う場合は「ハイムシティ」を選ぶ（韓進で登録すると追跡が反映されない事象あり・iaRbJIRksaU 680行）。コードは登録後に配送会社一覧 API で引いて config に入れる（推測で既定値を置かない）"""
    rows = [r for r in rows if r.get("moved")]   # 配送の記録が動き出した荷物だけ返す（動かない送り状は「仮の送り状」でペナルティ・11番街の決まり）
    if not rows:
        return None
    rows = [{k: v for k, v in r.items() if k != "moved"} for r in rows]
    path = f"/v2/providers/openapi/apis/api/v4/vendors/{conf['vendorId']}/orders/invoices"
    body = {"vendorId": conf["vendorId"], "orderSheetInvoiceApplyDtos": [
        {**r, "deliveryCompanyCode": conf["deliveryCompanyCode"], "splitShipping": False,
         "preSplitShipped": False, "estimatedShippingDate": ""} for r in rows]}
    return _call("POST", path, conf, body)


CAT_PATH = "/v2/providers/openapi/apis/api/v1/categorization/predict"


def category(title_ko, brand, conf):
    """カテゴリ推薦 API（公式・機械学習）… 韓国語の商品名からカテゴリ番号。SUCCESS 以外は出品しない（手数料がカテゴリで変わるため）"""
    body = {"productName": title_ko, "brand": brand}
    auth = sign("POST", CAT_PATH, "", conf["accessKey"], conf["secretKey"])
    req = urllib.request.Request(HOST + CAT_PATH, data=json.dumps(body).encode(), method="POST",
                                 headers={"Authorization": auth, "Content-Type": "application/json;charset=UTF-8"})
    with urllib.request.urlopen(req, timeout=30) as r:
        d = json.load(r).get("data", {})
    if d.get("autoCategorizationPredictionResultType") != "SUCCESS":
        return None, d.get("comment")
    return int(d["predictedCategoryId"]), d.get("predictedCategoryName")


def fill_attrs(meta_attrs, known):
    """カテゴリの属性の欄（Category meta data API の attributes）に、分かっている値を名前で当てて埋める
    （9本目 TUtE6AZ4l2g「商品詳細の欄は全部埋めると検索に効く」）。分からない欄は空のまま出さない（推測で埋めない）
    meta_attrs … [{"attributeTypeName": "색상", "required": "MANDATORY"|"OPTIONAL"}]
    known … {"브랜드": "CITIZEN", "모델명": "CB0287-68L", "색상": "블랙"}"""
    out, missing = [], []
    for a in meta_attrs:
        n = a.get("attributeTypeName", "")
        v = known.get(n)
        if v:
            out.append({"attributeTypeName": n, "attributeValueName": str(v)[:30]})
        elif a.get("required") == "MANDATORY":
            missing.append(n)
    return out, missing   # missing が残る品は出品しない（必須欄の空は審査で止まる）


def send(body, conf):
    auth = sign("POST", PATH, "", conf["accessKey"], conf["secretKey"])
    req = urllib.request.Request(HOST + PATH, data=json.dumps(body).encode(), method="POST",
                                 headers={"Authorization": auth, "Content-Type": "application/json;charset=UTF-8"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


DUMMY = {"returnFee": 1, "deliveryCompanyCode": "TEST", "vendorId": "A00000000", "returnCenterCode": "0", "outboundShippingPlaceCode": "0", "vendorUserId": "test"}


def _t_fill():
    m = [{"attributeTypeName": "색상", "required": "MANDATORY"}, {"attributeTypeName": "모델명", "required": "OPTIONAL"},
         {"attributeTypeName": "사이즈", "required": "MANDATORY"}]
    out, miss = fill_attrs(m, {"색상": "블랙", "모델명": "CB0287-68L"})
    return len(out) == 2 and miss == ["사이즈"]


def selftest():
    bad = 0
    # 署名 … 同じ入力なら同じ値・秘密鍵が変われば別の値（陰性対照）
    t = datetime.datetime(2026, 9, 27, 5, 0, 0)
    a = sign("POST", PATH, "", "ak", "sk", t)
    b = sign("POST", PATH, "", "ak", "sk", t)
    c = sign("POST", PATH, "", "ak", "sk2", t)
    for ok, name in [(a == b, "同じ入力で同じ署名"), (a != c, "鍵が違えば署名も違う"),
                     ("signed-date=260927T050000Z" in a, "日時の形")]:
        print("✅" if ok else "🔴", name); bad += not ok
    try:
        build({"asin": "X", "title_ko": "x", "krw": 22391, "category": 1, "images": ["u"]}, DUMMY)
        print("🔴 5万ウォン未満が通った"); bad += 1
    except ValueError:
        print("✅ 5万ウォン未満は止まる")
    body = build({"asin": "B0088B5FTE", "title_ko": "우타마로 주방세제 리필 250ml", "krw": 52391,
                  "category": 1, "images": ["https://example.com/a.jpg"]}, DUMMY)
    it = body["items"][0]
    for ok, name in [(body["deliveryMethod"] == "AGENT_BUY", "AGENT_BUY"),
                     (it["overseasPurchased"] == "OVERSEAS_PURCHASED", "OVERSEAS_PURCHASED"),
                     (it["pccNeeded"] == "true", "pccNeeded=true"),
                     (it["salePrice"] == 52400, "価格は100ウォン単位"),
                     (it["externalVendorSku"] == "B0088B5FTE", "SKU に ASIN"),
                     (it["images"][0]["imageType"] == "REPRESENTATION", "代表画像"),
                     (it["certifications"][0]["certificationType"] == "NOT_REQUIRED", "認証 NOT_REQUIRED"),
                     (len(build({"asin": "X", "title_ko": "x", "krw": 60000, "category": 1, "images": ["u"],
                                 "tags": ["가" * 30] * 25}, DUMMY)["items"][0]["searchTags"]) == 20, "検索語は20語まで")]:
        print("✅" if ok else "🔴", name); bad += not ok
    ok = invoice([{"shipmentBoxId": 1, "orderId": 1, "vendorItemId": 1, "invoiceNumber": "X", "moved": False}], DUMMY) is None
    bad += not ok
    print("✅" if ok else "🔴", "配送が動いていない送り状は返さない")
    ok = _t_fill(); bad += not ok
    print("✅" if ok else "🔴", "属性の欄：分かる値だけ埋め、必須の空（사이즈）を出品止めとして返す")
    print("不一致", bad, "件")
    return bad


def main():
    if "--selftest" in sys.argv:
        sys.exit(1 if selftest() else 0)
    if len(sys.argv) >= 3 and sys.argv[1] == "build":
        try:
            conf = json.load(open(CONF))
        except FileNotFoundError:
            conf = DUMMY
            print("※ 鍵がまだ無いので仮の値で作ります", file=sys.stderr)
        print(json.dumps(build(json.load(open(sys.argv[2])), conf), ensure_ascii=False, indent=1))
        return
    print(__doc__)


if __name__ == "__main__":
    main()
