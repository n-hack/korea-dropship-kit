#!/usr/bin/env python3
"""カード枠の見張り … 残り枠が「売れたら仕入れる分」に足りなくなりそうなら、出品を増やさない／減らす

  python3 waku.py --selftest

既定 … カード枠 1,000万円（LIMIT を実際の枠に合わせて変える）
考え方… 枠切れで仕入れられない＝取り消し＝評価低下。だから先回りで止める
  要る枠 ＝ 出品数 × 1日の売れる割合 × 平均仕入れ × 入金までの日数（クーパンは月末締め翌月20〜25日＝最長55日）× 余裕 1.5
  残り枠 ＜ 要る枠 → 「増やさない」。残り枠 ＜ 要る枠の半分 → 「減らす」
"""
import sys

LIMIT = 10_000_000


def need(listed, sell_rate_month, avg_cost, days=55, margin=1.5):   # クーパンの入金は月末締め・翌月20〜25日（-qKCZEtBkZg）→ 売れてから入金まで最長55日
    per_day = listed * sell_rate_month / 30
    return round(per_day * avg_cost * days * margin)  # 円に丸める（小数の誤差で境目が揺れないように・検算で見つけた）


def judge(used, listed, sell_rate_month, avg_cost, limit=LIMIT):
    left = limit - used
    n = need(listed, sell_rate_month, avg_cost)
    if left < n / 2:
        return "減らす", left, n
    if left < n:
        return "増やさない", left, n
    return "増やしてよい", left, n


def selftest():
    bad = 0
    cases = [
        ((0, 10000, 0.01, 5000), "増やしてよい"),         # 要る枠 約100万・残り1,000万
        ((9_500_000, 10000, 0.01, 5000), "減らす"),        # 残り50万 ＜ 100万の半分… ではない→「増やさない」になるか確認
        ((9_960_000, 10000, 0.01, 5000), "減らす"),
        ((9_200_000, 10000, 0.01, 5000), "増やさない"),
    ]
    # 2件目は境目の確認（残り50万＝要る枠100万の半分ちょうど → 半分未満ではないので「増やさない」）
    cases[1] = ((10_000_000 - 687_500, 10000, 0.01, 5000), "増やさない")   # 55日で要る枠 137.5万の半分ちょうど → 半分未満ではない
    for args, want in cases:
        got, left, n = judge(*args)
        bad += got != want
        print("✅" if got == want else "🔴", f"残り {left:,.0f}円 ／ 要る {n:,.0f}円 → {got}")
    print("不一致", bad, "件")
    return bad


if __name__ == "__main__":
    sys.exit(1 if selftest() else 0)
