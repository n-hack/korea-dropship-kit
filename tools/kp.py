#!/usr/bin/env python3
"""Keepa API で仕入れ元（Amazon.co.jp）の今の値段・在庫・重さを取る（Amazon の画面は読まない）

  python3 kp.py B0XXXXXXXX ...   … 値段・在庫・重さを表示（1件1トークン）
  python3 kp.py --tokens         … 残りトークン

鍵 … 環境変数 KEEPA_API_KEY か config/keepa.json の {"key": "..."}（Keepa の有料プランで発行）
トークン … Keepa はトークン制（プランごとに毎分回復）。details は1件1トークン・100件まとめて送れる／search は1回10トークン・最大20件

返す形（watch.py / orders.py / run.py がそのまま使う）
  stock … Amazon 本体が在庫ありか、新品の出品者が3人以上なら 99。0人なら 0。1〜2人ならその人数
  jpy   … Amazon 本体が在庫ありなら本体の価格。無ければ送料込みの新品最安（出品者発送＋送料・FBA の小さい方）
          送料込みの値が取れない時は「新品価格＋送料の見込み800円」（安全側）
"""
import sys, os, json, time, urllib.request, urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
CONF = os.path.join(os.environ.get("KIT_HOME", os.path.dirname(HERE)), "config", "keepa.json")
DOMAIN_JP = 5
API = "https://api.keepa.com"


def _key():
    k = os.environ.get("KEEPA_API_KEY")
    if k:
        return k
    try:
        return json.load(open(CONF))["key"]
    except (FileNotFoundError, KeyError, ValueError):
        sys.exit("Keepa の鍵がありません（環境変数 KEEPA_API_KEY か config/keepa.json に置く）")


def _get(path, **params):
    params["key"] = _key()
    url = f"{API}/{path}?" + urllib.parse.urlencode(params)
    for i in range(3):
        try:
            with urllib.request.urlopen(url, timeout=60) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 429 and i < 2:      # トークン切れ … 回復を待って1回だけ引き直す
                time.sleep(60); continue
            raise RuntimeError(f"Keepa {path} {e.code}") from None   # 鍵を含む URL を表に出さない


def tokens():
    return _get("token").get("tokensLeft", 0)


def _cur(p, pos):
    cur = (p.get("stats") or {}).get("current") or []
    return lambda k: cur[k] if len(cur) > k and cur[k] is not None and (cur[k] > 0 if pos else cur[k] >= 0) else None


def details(asins):
    out = {}
    for i in range(0, len(asins), 100):
        r = _get("product", domain=DOMAIN_JP, asin=",".join(asins[i:i + 100]), stats=30)
        for p in r.get("products") or []:
            g = _cur(p, False)
            amz, offers = g(0), g(11) or 0
            cands = [x for x in (g(7), g(10)) if x]     # 7=出品者発送（送料込み）・10=FBA
            new = min(cands) if cands else (g(1) + 800 if g(1) is not None else None)
            honntai = p.get("availabilityAmazon") == 0 and amz is not None
            out[p["asin"]] = {"asin": p["asin"], "amazon_honntai": honntai, "seller": "Amazon.co.jp" if honntai else "",
                              "stock": 99 if honntai or offers >= 3 else offers, "jpy": amz if honntai else new,
                              "weight_g": p.get("packageWeight") or p.get("itemWeight") or None, "offers": offers,
                              "title": p.get("title") or "", "brand": p.get("brand") or ""}
    return out


def detail(asin):
    return details([asin]).get(asin, {"asin": asin, "stock": 0, "jpy": None, "weight_g": None, "amazon_honntai": False, "seller": ""})


def search(term, page=0):
    """言葉で探す … 1回10トークン・最大20件。足りなければ回復を待つ"""
    while tokens() < 11:
        time.sleep(60)
    r = _get("search", domain=DOMAIN_JP, type="product", term=term, page=page, stats=30)
    out = []
    for p in r.get("products") or []:
        g = _cur(p, True)
        out.append({"asin": p["asin"], "title": p.get("title") or "", "jpy": g(0) or g(1), "prime": g(0) is not None,
                    "_detail": {"asin": p["asin"], "amazon_honntai": g(0) is not None, "seller": "Amazon.co.jp" if g(0) else "",
                                "stock": 99 if g(0) or (g(11) or 0) >= 3 else (g(11) or 0), "jpy": g(0) or g(1),
                                "weight_g": p.get("packageWeight") or p.get("itemWeight")}})
    return out


if __name__ == "__main__":
    if "--tokens" in sys.argv:
        print("残りトークン", tokens())
    else:
        for a, d in details(sys.argv[1:]).items():
            print(d)
