#!/usr/bin/env python3
"""韓国無在庫輸出 1件の利益

  python3 rieki.py --krw 22390 --jpy 298 --kg 0.35
  python3 rieki.py --krw 22390 --jpy 298 --kg 0.35 --fee 0.089 --json

流れ … Amazon（本体・プライム）で仕入れ → HANIRO 福岡倉庫 → 船で釜山 → 韓国の客
式（円）
  入金      = 売値ウォン × 為替 × (1 − 販売手数料) × (1 − 送金手数料)
  差の利益  = 入金 − 仕入れ − 国際送料 − 取り置き（返品・キャンセルの引当）
  還付      = 仕入れ × 10/110（課税事業者・原則課税・インボイス登録が前提）
  利益      = 差の利益 + 還付

既定値の出どころ（どれも「安全側」＝利益を小さく見る向きに置いた）
  販売手数料 0.109 … クーパン 4〜10.9%（カテゴリで違う・語り手複数）の上端
  送金手数料 0.03  … Payoneer の引き出し 1〜2%（語り手）＋為替の上乗せ → 3%で見る（引きすぎて出さないのは損にならない）
  国際送料       … HANIRO 公式料金（下の haniro() の注記）。0.5kg 900円から0.5kg ごとに+100円・検品20円
                    国内送料（Amazon → HANIRO 倉庫）はプライムなら0円とみる。分からない費用は --handling で足す
  取り置き 0.03   … 返品・キャンセルの損を売値の3%で見込む（根拠なし・仮）
  為替           … open.er-api.com の当日値（取れなければ止まる）
関税 … 150ドル超は買い手に関税がかかりうる → 事前確認が要る品として印を付ける（買い手負担・利益には入れない）
"""
import sys, json, math, argparse, urllib.request


# クーパンのカテゴリ別手数料（cloud.mkt.coupang.com/Fee-Table・2019-11-25 版・2026-09-27 読んだ・税別）
# 古い版なので、出品時はクーパンのカテゴリ推薦で決まった分類の実際の率に置き換える。分からないときは 10.9%（上端）
FEE = {"golf": 0.076, "bicycle": 0.076, "sports": 0.108, "toy": 0.108, "drone": 0.078, "kitchen": 0.108,
       "living": 0.078, "digital": 0.078, "car": 0.10}


def fx_krw_jpy():
    with urllib.request.urlopen("https://open.er-api.com/v6/latest/KRW", timeout=15) as r:
        d = json.load(r)
    if d.get("result") != "success":
        raise RuntimeError("為替が取れない")
    return d["rates"]["JPY"], d["rates"]["USD"], d.get("time_last_update_utc")


# HANIRO 公式料金（haniro.jp/haniroNew/haniroRates・1P=100円・実重量のみ）
#   Economy（月1〜100件）0.5kg 9.00P から 0.5kg ごとに +1.00P ／ Premium（101〜200件）−0.50P ／ Business（201件〜）−1.00P
#   簡易検品 0.20P／商品（インボイス除去＝仕入れ元の納品書を抜くには簡易検品が要る）
#   規格外配送 11.00P（精密機器・楽器・PC・モニター・ゴルフクラブ・釣り竿・食品・生物など）… kikakugai=True で足す
#   大額通関 59.00P（商品価格 201,000円以上）
TIER = {"economy": 0, "premium": 50, "business": 100}


def haniro(kg, tier="economy", items=1, kikakugai=False, price_jpy=0):
    if kg > 70:
        raise ValueError(f"{kg}kg は想定外")
    steps = max(1, math.ceil(round(kg / 0.5, 6)))
    yen = 900 + 100 * (steps - 1) - TIER[tier]
    yen += 20 * items
    if kikakugai:
        yen += 1100
    if price_jpy >= 201000:
        yen += 5900
    # HANIRO 補償（公式 haniroInsurance）… 申請すると商品価格の3%（上限20万円分）で最大20万円まで補償。
    # 申請しないと韓国の配送会社の規定で50万ウォン（約5.8万円）まで → それを超える品だけ補償を付ける
    if price_jpy > 58000:
        yen += round(min(price_jpy, 200000) * 0.03)
    return yen


def calc(krw, jpy, kg, fee=0.109, remit=0.03, reserve=0.03, handling=0, rate=None, usd=None, tier="economy", kikakugai=False):
    if rate is None:
        rate, usd, _ = fx_krw_jpy()
    sell_jpy = krw * rate
    nyukin = sell_jpy * (1 - fee) * (1 - remit)
    ship = haniro(kg, tier, 1, kikakugai, jpy) + handling
    hiki = sell_jpy * reserve
    sa = nyukin - jpy - ship - hiki
    kanpu = jpy * 10 / 110
    rieki = sa + kanpu
    return {
        "売値_ウォン": krw, "売値_円": round(sell_jpy), "入金_円": round(nyukin),
        "仕入れ_円": jpy, "送料_円": ship, "引当_円": round(hiki),
        "差の利益_円": round(sa), "還付_円": round(kanpu), "利益_円": round(rieki),
        "利益率_売値比": round(rieki / sell_jpy, 3) if sell_jpy else None,
        # 課税の線（HANIRO 公式 haniroTaxes）… 「支払った総額（物件価格＋現地の送料）」が150ドル超で課税
        # 購買代行では韓国での売値ではなく、日本での仕入れ値が申告の価格になる（HANIRO の申請書に書く値）
        "関税の確認が要る": bool(usd and rate and jpy / rate * usd > 150),
        "為替_1ウォン円": rate,
    }


def floor_krw(jpy, kg, min_profit=500, rate=None, usd=None, **kw):
    """利益が min_profit を割らない最低の売値（ウォン・100ウォン単位で切り上げ）… クーパンの自動価格調整の下限に入れる"""
    if rate is None:
        rate, usd, _ = fx_krw_jpy()
    lo, hi = 0, 10_000_000
    while hi - lo > 100:
        mid = (lo + hi) // 2
        if calc(mid, jpy, kg, rate=rate, usd=usd, **kw)["利益_円"] >= min_profit:
            hi = mid
        else:
            lo = mid
    return -(-hi // 100) * 100


def max_cost(krw, kg, min_profit=500, rate=None, usd=None, **kw):
    """売値が決まっているとき、利益が min_profit を割らない仕入れ値の上限（円）"""
    if rate is None:
        rate, usd, _ = fx_krw_jpy()
    lo, hi = 0, 2_000_000
    if calc(krw, 0, kg, rate=rate, usd=usd, **kw)["利益_円"] < min_profit:
        return None
    while hi - lo > 1:
        mid = (lo + hi) // 2
        if calc(krw, mid, kg, rate=rate, usd=usd, **kw)["利益_円"] >= min_profit:
            lo = mid
        else:
            hi = mid
    return lo


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--krw", type=float, required=True)
    ap.add_argument("--jpy", type=float, required=True, help="仕入れ値（税込・円）")
    ap.add_argument("--kg", type=float, required=True, help="梱包後の重さ")
    ap.add_argument("--fee", type=float, default=0.109)
    ap.add_argument("--remit", type=float, default=0.03)
    ap.add_argument("--reserve", type=float, default=0.03)
    ap.add_argument("--handling", type=float, default=0)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    r = calc(a.krw, a.jpy, a.kg, a.fee, a.remit, a.reserve, a.handling)
    if a.json:
        print(json.dumps(r, ensure_ascii=False))
    else:
        for k, v in r.items():
            print(f"{k:>12}  {v}")


if __name__ == "__main__":
    main()
