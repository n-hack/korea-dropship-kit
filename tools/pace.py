#!/usr/bin/env python3
"""出品の速さを決める（いきなり大量に出さない・同じブランドを一気に出さない）

  python3 pace.py --selftest

決まり（docs/SCHEME.md・実務者の話から。クーパンで同じ検知があるかは未確認なので安全側）
  1日の上限 … 開始週 START 件、以後 週ごとに ×GROW（クーパンの1日上限5,000と出品枠を超えない）
  同じブランド … 1日 BRAND_MAX 件まで
  並べ順 … 利益の大きい順。ブランドが偏らないよう、上限に達したブランドは翌日に回す
"""
import sys, math
from collections import Counter

START, GROW, BRAND_MAX, DAY_CAP = 100, 1.5, 10, 5000


def daily_cap(week, slots_left):
    return max(0, min(DAY_CAP, int(START * GROW ** week), slots_left))


def pick(cands, week, listed_total, slots=10000, waku_judge="増やしてよい"):
    """cands … [{asin, brand, profit}] → 今日出す分"""
    cap = daily_cap(week, slots - listed_total)
    if waku_judge != "増やしてよい":   # カード枠が足りない日は新しい出品をしない（waku.py の判断・枠切れ＝仕入れ不能＝取消）
        cap = 0
    per = Counter()
    out = []
    for c in sorted(cands, key=lambda c: -c["profit"]):
        if len(out) >= cap:
            break
        b = (c.get("brand") or "?").lower()
        if per[b] >= BRAND_MAX:
            continue
        per[b] += 1
        out.append(c)
    return out


def selftest():
    bad = 0
    cands = [{"asin": f"A{i}", "brand": "makita" if i < 50 else f"b{i % 30}", "profit": 1000 - i} for i in range(400)]
    d0 = pick(cands, 0, 0)
    d2 = pick(cands, 2, 0)
    full = pick(cands, 0, 9990)
    checks = [
        (len(d0) == 100, f"開始週は100件（実際 {len(d0)}）"),
        (Counter(c["brand"] for c in d0)["makita"] == 10, "同じブランドは1日10件まで"),
        (len(d2) == 225, f"2週後は100×1.5²＝225件（実際 {len(d2)}）"),
        (len(full) == 10, f"出品枠の残り10なら10件（実際 {len(full)}）"),
        (daily_cap(20, 10**9) == DAY_CAP, "1日上限5,000を超えない"),
        (pick(cands, 0, 0, waku_judge="増やさない") == [], "カード枠が足りない日は0件"),
    ]
    for ok, name in checks:
        bad += not ok
        print("✅" if ok else "🔴", name)
    print("不一致", bad, "件")
    return bad


if __name__ == "__main__":
    sys.exit(1 if selftest() else 0)
