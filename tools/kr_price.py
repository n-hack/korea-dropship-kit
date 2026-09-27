#!/usr/bin/env python3
"""韓国側の売値を取る（ダナワ＝韓国版の価格.com の検索結果から）

  python3 kr_price.py 우타마로          … 商品名と最安値（ウォン）を並べる
  python3 kr_price.py 우타마로 --json   … JSON で出す

なぜダナワか（2026-09-27 実測）
  クーパン検索 … 403（機械の取得を弾く）
  ネイバーショッピング … 418（同じ）
  ダナワ … 200・40件の商品と最安値が取れた
取れないとき（件数 0）は「0件」と「取得に失敗」を分けて出す。
"""
import sys, re, json, html, time, urllib.parse, urllib.request

# search.danawa.com/robots.txt（2026-09-27 読んだ）… dsearch.php は許可・Crawl-delay: 10 → 1回ごとに10秒空ける
_last = [0.0]
DELAY = 10

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131 Safari/537.36"


def search(q):
    wait = DELAY - (time.time() - _last[0])
    if wait > 0:
        time.sleep(wait)
    _last[0] = time.time()
    url = "https://search.danawa.com/dsearch.php?query=" + urllib.parse.quote(q)
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "ko-KR"})
    with urllib.request.urlopen(req, timeout=25) as r:
        s = r.read().decode("utf-8", "ignore")
    out = []
    for blk in s.split('class="prod_main_info"')[1:]:
        m = re.search(r'<p class="prod_name">\s*<a\s+href="([^"]+)"[^>]*>(.*?)</a>', blk, re.S)
        if not m:
            continue
        name = html.unescape(re.sub(r"\s+", " ", re.sub("<[^>]+>", "", m.group(2)))).strip()
        pc = re.search(r"pcode=(\d+)", m.group(1))
        prices = [int(p.replace(",", "")) for p in re.findall(r"<strong>([\d,]+)</strong>\s*원?", blk)]
        out.append({"name": name, "pcode": pc.group(1) if pc else None,
                    "min_krw": min(prices) if prices else None})
    return out, len(s)


def main():
    if len(sys.argv) < 2:
        print(__doc__); sys.exit(2)
    q = " ".join(a for a in sys.argv[1:] if not a.startswith("--"))
    try:
        items, size = search(q)
    except Exception as e:
        print(f"取得に失敗: {e}", file=sys.stderr); sys.exit(1)
    if "--json" in sys.argv:
        print(json.dumps(items, ensure_ascii=False, indent=1))
    else:
        print(f"検索語 {q} ／ 取れた {len(items)}件（ページ {size}バイト）")
        for it in items:
            p = f"{it['min_krw']:,}" if it["min_krw"] else "─"
            print(f"{p:>10} ウォン  {it['name'][:70]}")


if __name__ == "__main__":
    main()
