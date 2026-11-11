#!/usr/bin/env python3
"""仕入れの証拠を1件ずつ台帳に残す（正規品の確認・消費税の還付・返品のため）

  python3 shoko.py --selftest

なぜ … クーパン公式「유통경로 인증」で購買代行が出せる証拠は「購入先・日付・品目」が載った領収書かインボイス（有効1年）。
       Amazon の注文番号は「時に注文番号だけで解決する」ほど強い。還付には適格請求書と HANIRO の輸出許可書
台帳 … shoko.jsonl（1行1件・消さない・上書きしない）
  必ず入れる … 購入先 ／ 購入日 ／ 品目（ASIN・題名）／ 数量 ／ 金額 ／ Amazon の注文番号 ／ クーパンの注文番号
  後から足す … 請求書 PDF の置き場 ／ HANIRO の出庫番号 ／ 輸出許可書の番号
"""
import sys, json, datetime
import paths

LEDGER = paths.data("shoko.jsonl")
MUST = ["kounyusaki", "date", "asin", "title", "qty", "jpy", "amazon_order", "coupang_order"]


def check(rec):
    miss = [k for k in MUST if not rec.get(k)]
    return (not miss), miss


def add(rec, path=LEDGER):
    ok, miss = check(rec)
    if not ok:
        raise ValueError(f"証拠に欠け: {miss}")
    rec = {**rec, "saved_at": datetime.datetime.now().isoformat(timespec="seconds")}
    with open(path, "a") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return rec


def expiring(path=LEDGER, days=180):
    """クーパンのブランド品の書類は発行から6ヶ月以内 → 期限の近い証拠を出す（取り直し・出品の見直し用）"""
    import datetime as dt
    out = []
    try:
        for l in open(path):
            r = json.loads(l)
            age = (dt.date.today() - dt.date.fromisoformat(r["date"])).days
            if age >= days - 14:
                out.append((age, r["asin"], r["coupang_order"]))
    except FileNotFoundError:
        pass
    return out


def find(coupang_order, path=LEDGER):
    """クーパンから確認が来たとき、その注文の証拠をすぐ出す"""
    try:
        return [json.loads(l) for l in open(path) if json.loads(l).get("coupang_order") == coupang_order]
    except FileNotFoundError:
        return []


def selftest():
    import tempfile, os
    fd, p = tempfile.mkstemp()
    os.close(fd)
    good = {"kounyusaki": "Amazon.co.jp", "date": "2026-10-01", "asin": "B0088B5FTE", "title": "ウタマロキッチン 詰替",
            "qty": 1, "jpy": 253, "amazon_order": "250-0000000-0000000", "coupang_order": "C1"}
    bad = 0
    add(good, p)
    r = find("C1", p)
    bad += not (len(r) == 1 and r[0]["amazon_order"] == good["amazon_order"])
    print("✅" if len(r) == 1 else "🔴", "注文番号から証拠がすぐ出る")
    try:
        add({**good, "kounyusaki": ""}, p); print("🔴 購入先が空でも入った"); bad += 1
    except ValueError as e:
        print("✅ 購入先が空なら止まる", e)
    bad += find("C9", p) != []
    print("✅ 無い注文は空で返る")
    os.remove(p)
    print("不一致", bad, "件")
    return bad


if __name__ == "__main__":
    sys.exit(1 if selftest() else 0)
