#!/usr/bin/env python3
"""画像の門 … 出品に使う画像の「出どころ」を見て、使ってよい画像だけを出品に渡す（土台①）

  python3 gazou.py --selftest

なぜ … 無在庫では手元に品が無いので他人の画像を使うことになる。画像には撮った人・メーカーの権利がある
  （fdNS84hftu4「無在庫では商品画像の使用を許可されていない場合がある」・クーパンは知財の指摘3回で1ヶ月停止＝-qKCZEtBkZg）
  → 出どころの分からない画像は出品に通さない。どの出どころを通すかは policy（config/gazou_policy.json）で決める

出どころの種類（src）
  wholesale_ok … 卸が画像の転載を認めている（NETSEA の画像転載可・トップセラー等）      → 常に通す
  maker_ok     … メーカーが販売店向けに素材を公開し、使用を認めている（MAKER_OK に登録したブランド） → 通す
  own          … 自分で撮った画像                                                          → 通す
  amazon       … Amazon の商品ページの画像（メーカー提供か出品者撮影かは区別できない）    → policy で決める
  unknown      … 出どころ不明                                                              → 常に止める

policy（オーナーが1つ選ぶ・既定は strict）
  strict    … amazon を止める（安全・ただし出せる品が大きく減る）
  maker_img … amazon のうち、ブランドがメーカー本体の出品（Amazon 本体か公式ストア）の画像だけ通す
  loose     … amazon を通す（韓国の購買代行で広く行われている形・権利者から指摘が来たら即取り下げ）
"""
import json, os, sys
import paths

POLICY_FILE = paths.conf("gazou_policy.json")
MAKER_OK = set()   # 販売店向けに画像の使用を明示的に認めているブランド（確かめたものだけ足す）


def policy():
    try:
        return json.load(open(POLICY_FILE)).get("policy", "strict")
    except (FileNotFoundError, ValueError):
        return "strict"


def judge(img, pol=None):
    """img … {url, src, brand, seller_is_maker(bool)} → (通す?, 理由)"""
    pol = pol or policy()
    src = img.get("src", "unknown")
    if src in ("wholesale_ok", "own"):
        return True, src
    if src == "maker_ok":
        return (img.get("brand") in MAKER_OK), ("maker_ok" if img.get("brand") in MAKER_OK else "メーカーの許可が未登録")
    if src == "amazon":
        if pol == "loose":
            return True, "amazon（loose）"
        if pol == "maker_img" and img.get("seller_is_maker"):
            return True, "amazon・メーカー本体の出品の画像"
        return False, f"amazon の画像は policy={pol} で使わない"
    return False, "出どころ不明"


def pick(imgs, pol=None):
    """出品に使える画像だけ返す。1枚も無ければ出品しない（空リスト）"""
    return [i["url"] for i in imgs if judge(i, pol)[0]]


def selftest():
    bad = 0
    cases = [
        ({"url": "a", "src": "wholesale_ok"}, "strict", True),
        ({"url": "b", "src": "amazon"}, "strict", False),
        ({"url": "c", "src": "amazon", "seller_is_maker": True}, "maker_img", True),
        ({"url": "d", "src": "amazon", "seller_is_maker": False}, "maker_img", False),
        ({"url": "e", "src": "amazon"}, "loose", True),
        ({"url": "f", "src": "unknown"}, "loose", False),
        ({"url": "g", "src": "maker_ok", "brand": "X"}, "strict", False),
    ]
    for img, pol, want in cases:
        got = judge(img, pol)[0]
        bad += got != want
        print("✅" if got == want else "🔴", pol, img["src"], "→", got, judge(img, pol)[1])
    ok = pick([{"url": "x", "src": "amazon"}, {"url": "y", "src": "unknown"}], "strict") == []
    bad += not ok
    print("✅" if ok else "🔴", "使える画像が0枚なら空（出品しない）")
    print("不一致", bad, "件")
    return bad


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        sys.exit(1 if selftest() else 0)
    print("policy =", policy())
