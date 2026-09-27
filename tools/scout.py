#!/usr/bin/env python3
"""韓国で「日本から代行販売」されている品を起点に、Amazon 本体で仕入れて利益が出るかを数える

  python3 scout.py 마키타:マキタ                 … 1ブランド
  python3 scout.py 마키타:マキタ 시마노:シマノ --max 20

流れ
  ① ダナワで「[해외] ブランド」を引く … 韓国で日本から代行販売されている品と、その最安値（＝同業者の売値）
  ② 商品名から型番を抜く
  ③ Amazon.co.jp で「ブランド 型番」を引き、題名に型番を含む最初の品
  ④ 商品ページで 販売元が Amazon 本体か（クーパンの正規品確認に通る条件・語り手2人）・重さ
  ⑤ rieki.calc で1件の利益（手数料・HANIRO 船便・為替・還付）
出力 … scout_out.jsonl に全件（落ちた理由つき）を追記し、画面には利益順の上位を出す
売値は「同業者の最安値」をそのまま使う（こちらが最安に並べて売る前提・安全側）
"""
import sys, re, json, time, argparse, datetime
import paths
import kr_price, kp as jp_price, rieki, kc

MODEL = re.compile(r"\b([A-Z]{1,5}-?\d{2,5}[A-Z0-9]{0,4})\b")
OUT = paths.data("scout_out.jsonl")


def run(pairs, mx, rate, usd):
    rows = []
    for pair in pairs:
        kr, jp = pair.split(":")
        items, _ = kr_price.search(f"[해외] {kr}")
        seen = set()
        for it in items:
            if len(seen) >= mx:
                break
            m = MODEL.search(it["name"])
            krw = it["min_krw"]
            if not m or not krw or krw < 50000:
                continue
            model = m.group(1)
            if model in seen:
                continue
            seen.add(model)
            row = {"brand": jp, "model": model, "kr_name": it["name"], "krw": krw}
            try:
                res = [r for r in jp_price.search(f"{jp} {model}") if not r["sponsored"] and r["jpy"]
                       and model.replace("-", "") in r["title"].upper().replace("-", "")]
            except Exception as e:
                row["drop"] = f"Amazon検索失敗 {e}"; rows.append(row); continue
            if not res:
                row["drop"] = "Amazonに同じ型番なし"; rows.append(row); continue
            a = res[0]
            d = a.get("_detail") or jp_price.detail(a["asin"])
            time.sleep(1.0)
            row.update(asin=a["asin"], title=a["title"][:60], jpy=d["jpy"] or a["jpy"],
                       seller=d["seller"], honntai=d["amazon_honntai"], weight_g=d["weight_g"])
            kg = (d["weight_g"] or 1500) / 1000 * 1.3  # 梱包で3割増し（見込み1,000円が実際1,300円の実例）・重さ不明は1.5kg仮置き
            kikaku = bool(re.search(r"腕時計|時計|カメラ|レンズ|楽器|ゴルフクラブ|ドライバー|アイアン|釣り?竿|ロッド", a["title"]))  # HANIRO の規格外（精密機器・ゴルフクラブ・釣り竿）
            fee = rieki.FEE["golf"] if re.search(r"ゴルフ|golf|Golf", a["title"]) else 0.109
            row["calc"] = rieki.calc(krw, row["jpy"], kg, fee=fee, rate=rate, usd=usd, kikakugai=kikaku)
            ratio = row["calc"]["売値_円"] / row["jpy"] if row["jpy"] else 0
            j, why = kc.judge(a["title"])
            # 取り違えの門（2026-09-27 実測で見つけた2つ）
            #  ① リールの「C3000SDH」などはサイズの記号で、シリーズ（ステラ／セフィア）をまたいで同じ → 型番として使わない
            #  ② 韓国側の枝番（NB1050-59H）と日本側（NB1050-59A）が違えば別の品（文字盤の色違い）
            size_code = bool(re.fullmatch(r"C?\d{4}[A-Z]*", model))
            kr_full = re.search(re.escape(model) + r"-([0-9A-Z]{1,4})", (row.get("kr_name") or "").upper())
            jp_full = re.search(re.escape(model) + r"-([0-9A-Z]{1,4})", a["title"].upper())
            ke, je = (kr_full.group(1) if kr_full else ""), (jp_full.group(1) if jp_full else "")
            eda_chigai = bool(ke and je and not (ke.startswith(je) or je.startswith(ke)))   # 片方が短いだけなら同じとみる
            pre = lambda t: (re.search(r"([A-Z]{2,4})-" + re.escape(model), (t or "").upper()) or [None, ""])[1]
            kp_, jp_ = pre(row.get("kr_name")), pre(a["title"])
            if kp_ and jp_ and kp_ != jp_:
                j, why = "止める", f"頭の記号が違う（韓国 {kp_}- ／ 日本 {jp_}-・例 GGC＝キャディバッグ／GGB＝ボストン）"
            elif size_code:
                j, why = "止める", "サイズの記号で型番ではない（シリーズの取り違えの恐れ）"
            elif eda_chigai:
                j, why = "止める", f"枝番が違う（韓国 {kr_full.group(1)} ／ 日本 {jp_full.group(1)}）"
            if j == "止める":
                row["drop"] = why
            elif krw < 50000:
                row["drop"] = "売値5万ウォン未満（返品希望で自動返金）"
            elif not (0.8 <= ratio <= 3.0):
                row["drop"] = f"売値/仕入れが{ratio:.1f}倍 … 別の品を取り違えている恐れ（要目視）"
            rows.append(row)
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pairs", nargs="+")
    ap.add_argument("--max", type=int, default=15)
    a = ap.parse_args()
    rate, usd, when = rieki.fx_krw_jpy()
    rows = run(a.pairs, a.max, rate, usd)
    now = datetime.datetime.now().isoformat(timespec="seconds")
    with open(OUT, "a") as f:
        for r in rows:
            r["at"] = now
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    ok = [r for r in rows if "calc" in r]
    good = [r for r in ok if "drop" not in r]
    print(f"候補 {len(rows)} ／ Amazonで見つかった {len(ok)} ／ 倍率が正常 {len(good)}（うち本体 {sum(1 for r in good if r.get("honntai"))}） ／ 為替 1ウォン={rate}円（{when}）")
    for r in sorted(ok, key=lambda r: -r["calc"]["利益_円"]):
        c = r["calc"]
        mark = "✅" if "drop" not in r and c["利益_円"] > 0 else "✕"
        print(f"{mark}{'本' if r.get('honntai') else ' '} {c['利益_円']:>7,}円 売{c['売値_円']:>7,} 仕{r['jpy']:>7,} 送{c['送料_円']:>5} {r['brand']} {r['model']:<10} {r['seller'][:14]}")
    for r in rows:
        if "calc" not in r:
            print(f"・ {r['brand']} {r['model']} … {r['drop']}")


if __name__ == "__main__":
    main()
