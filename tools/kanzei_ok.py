#!/usr/bin/env python3
"""関税がかかる品の「買い手の了承」（土台②）

  python3 kanzei_ok.py --selftest

なぜ … 韓国は仕入れ値が150ドル（米国発は200ドル）を超えると、受け取るときに買い手へ関税・付加価値税がかかる。
  知らずに買った人が受け取りを拒む・返品する・クレームを入れる（講師 -qKCZEtBkZg「仕入れる前に確認すれば4〜5年トラブル0件」）

決めたこと
  ① 注文のあとに買い手へ連絡して了承を取る形は採らない
     … クーパンは販売者から買い手へ連絡する口が無い（講師はカカオトークを手で使っている＝AIだけでは回らない）
  ② その代わり【出品の時点】で了承を取る … 150ドル超になる品は
     ・商品名の頭に「관세별도」を入れる（一覧で目に入る）
     ・説明の先頭に関税の目安（仕入れ値×約20%）を具体の金額で書く
     → 買い手は了承の上で注文する。注文が来たらそのまま仕入れる（保留にしない）
  ③ 印の無い出品（古い出品など）に150ドル超の注文が来たら「取り消し候補」（買い手に負担を強いない）
  ④ 関税込みの見込みで売れ方が鈍るかは urekata.py で分類ごとに測り、鈍ければ150ドル超を出さない
"""
import sys

USD_LINE = 150          # 日本発の目録通関の上限（米国発は200・日本発は150）
DUTY_RATE = 0.20        # 買い手負担の目安（関税8%前後＋付加価値税10%＝約20%・品目で変わるので「目安」と書く）


def needs(jpy, usd):
    """仕入れ値（円）が150ドルを超えるか"""
    return jpy * usd > USD_LINE if usd else False


def mark(title_ko, desc_ko, jpy, usd, krw_per_jpy):
    """150ドル超の品に、商品名の印と説明の先頭の告知を付ける。超えない品はそのまま返す"""
    if not needs(jpy, usd):
        return title_ko, desc_ko, False
    duty = -(-int(jpy * krw_per_jpy * DUTY_RATE) // 1000) * 1000   # 千ウォン単位で切り上げ（少なめに書かない）
    head = ("【관세 안내】 이 상품은 미화 150달러를 초과하여 수령 시 관세·부가세가 부과됩니다 "
            f"(예상 약 {duty:,}원, 품목에 따라 다름). 구매 전 확인 부탁드립니다.\n\n")
    return ("[관세별도] " + title_ko)[:100], head + desc_ko, True


def on_order(plan_row, listing_marked):
    """orders.plan が「保留（関税）」にした注文をどうするか
    listing_marked … その出品に関税の印を付けて出していたか"""
    if listing_marked:
        return "仕入れる", "出品で関税を告知済み（買い手は了承して注文）"
    return "取り消し候補", "関税の告知なしの出品に150ドル超の注文（買い手に負担を強いない）"


def selftest():
    bad = 0
    usd, kpj = 0.00667, 9.3   # 1円≒0.00667ドル・1円≒9.3ウォン（検体用）
    t, d, m = mark("시티즌 아테사", "설명", 30000, usd, kpj)
    ok = m and t.startswith("[관세별도]") and d.startswith("【관세 안내】") and "56,000원" in d
    bad += not ok
    print("✅" if ok else "🔴", "150ドル超（3万円）は印と告知を付ける ｜", t, "｜", d[:60])
    t, d, m = mark("세이코 시계", "설명", 15000, usd, kpj)
    ok = (not m) and t == "세이코 시계" and d == "설명"
    bad += not ok
    print("✅" if ok else "🔴", "150ドル以下（1.5万円）はそのまま")
    ok = on_order({}, True)[0] == "仕入れる" and on_order({}, False)[0] == "取り消し候補"
    bad += not ok
    print("✅" if ok else "🔴", "告知済みなら仕入れる・告知なしなら取り消し候補")
    print("不一致", bad, "件")
    return bad


if __name__ == "__main__":
    sys.exit(1 if selftest() else 0)
