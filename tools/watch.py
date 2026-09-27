#!/usr/bin/env python3
"""見張り … 出品中の品の仕入れ元（Amazon）を見て、出品を「続ける／値を直す／止める」を決める

  python3 watch.py listings.json            … 全件を見て判断を出す（出品の操作はまだしない）
  python3 watch.py --selftest               … 判断の分岐だけを検体で確かめる（ネットに出ない）

listings.json … [{"asin": "...", "krw": 34480, "kg": 1.3, "min_profit": 500}, ...]
判断
  止める … 在庫 0 ／ 残り2点以下（売れた時に取れない恐れ）／ 今の仕入れ値で利益が min_profit 未満
  値を直す … 利益は出るが、仕入れ値が出品時から動いた（新しい売値＝min_profit を守る値の候補を出す）
  続ける … それ以外
なぜ … 無在庫のいちばんの弱点は「売れたのに仕入れられない／赤字」→ キャンセル → 評価低下
出品の操作（クーパン API）は販売者登録のあとに繋ぐ。いまは判断までを機械で出す。
"""
import sys, json, time
import rieki


def decide(item, d, rate, usd):
    if d["stock"] == 0:
        return "止める", "仕入れ元が在庫切れ"
    if d["stock"] <= item.get("min_stock", 5):  # 最初の数か月は厳しく（注文が少ないほど1件の取消が重い）
        return "止める", f"仕入れ元の残り{d['stock']}点"
    if not d["jpy"]:
        return "止める", "仕入れ値が読めない"
    c = rieki.calc(item["krw"], d["jpy"], item.get("kg", 1.5), rate=rate, usd=usd)
    if c["利益_円"] < item.get("min_profit", 500):
        return "止める", f"利益 {c['利益_円']}円 < 下限 {item.get('min_profit', 500)}円（仕入れ {d['jpy']}円）"
    if item.get("jpy") and d["jpy"] != item["jpy"]:
        return "値を直す", f"仕入れ {item['jpy']}→{d['jpy']}円・利益 {c['利益_円']}円"
    return "続ける", f"利益 {c['利益_円']}円"


def selftest():
    base = {"asin": "X", "krw": 34480, "kg": 1.3, "min_profit": 500, "jpy": 1329}
    rate, usd = 0.116015, 0.000737
    cases = [
        ({"stock": 0, "jpy": 1329}, "止める"),
        ({"stock": 2, "jpy": 1329}, "止める"),
        ({"stock": 3, "jpy": 1329}, "止める"),
        ({"stock": 6, "jpy": 1329}, "続ける"),
        ({"stock": 99, "jpy": None}, "止める"),
        ({"stock": 99, "jpy": 2600}, "止める"),   # 値上がりで利益が下限を割る
        ({"stock": 99, "jpy": 1500}, "値を直す"),
        ({"stock": 99, "jpy": 1329}, "続ける"),
    ]
    bad = 0
    for d, want in cases:
        got, why = decide(base, d, rate, usd)
        ok = got == want
        bad += not ok
        print(("✅" if ok else "🔴"), d, "→", got, "／", why)
    print("不一致", bad, "件")
    return bad


def main():
    if "--selftest" in sys.argv:
        sys.exit(1 if selftest() else 0)
    import kp
    items = json.load(open(sys.argv[1]))
    rate, usd, _ = rieki.fx_krw_jpy()
    for it in items:
        d = kp.detail(it["asin"])
        act, why = decide(it, d, rate, usd)
        print(f"{act}\t{it['asin']}\t{why}")
        time.sleep(1.0)


if __name__ == "__main__":
    main()
