#!/usr/bin/env python3
"""韓国語の商品名を作る（決まった部分は機械・意味の訳は AI エージェント）

  python3 title_ko.py --selftest

決まり（SCHEME.md「まだ決まっていない土台」）
  ① 頭に [해외]（韓国の代行品の慣例）
  ② ブランドは韓国で実際に使われている綴り（gap.KR_BRAND・ダナワの表記）
  ③ 型番・サイズ・数量は原文のまま（別の品と取り違えない・容量は完全一致の決まり）
  ④ 残りの意味（品名）は AI エージェントが訳して ko_body に入れる
  ⑤ 100字まで（クーパンの sellerProductName の上限）
"""
import re, sys
from brands import KR_BRAND

KEEP = re.compile(r"[A-Za-z]{1,6}-?\d[\w./-]*|\d+(?:\.\d+)?\s?(?:ml|mL|L|g|kg|cm|mm|個|本|枚|セット|m)", re.I)
UNIT = {"個": "개", "本": "개", "枚": "매", "セット": "세트"}


PLATFORM = {"Switch 2": "닌텐도 스위치2", "Switch": "닌텐도 스위치", "PS5": "PS5", "PS4": "PS4", "3DS": "3DS"}
REGION_NOTE = "· 일본판(일본어) 상품입니다. 구형 기기(3DS 등)는 한국판 본체에서 실행되지 않을 수 있습니다.\n"


def make(title_ja, brand_ja, ko_body):
    br = next((v for k, v in KR_BRAND.items() if k.lower() in (brand_ja or "").lower() or k in title_ja[:30]), None)
    if br is None:
        if brand_ja and re.search(r"[ぁ-んァ-ン一-龥]", brand_ja):
            raise ValueError(f"ブランド「{brand_ja}」の韓国語表記が未登録 → AI がダナワで綴りを確かめて KR_BRAND に足す")
        br = brand_ja or ""
    keep = []
    for m in KEEP.findall(title_ja):
        for j, k in UNIT.items():
            m = m.replace(j, k)
        if m not in keep:
            keep.append(m)
    # ゲーム・映像は機種と「日本版」を必ず入れる（8OGvTc9AxYs 韓国人講師「機種と言語を書かないと買い間違い・返品になる」）
    plat = next((v for k, v in PLATFORM.items() if k in title_ja), None)
    if plat:
        keep = [plat, "일본판", *keep]
    t = " ".join(x for x in ["[해외]", br, ko_body, *keep[:5]] if x)
    return re.sub(r"\s+", " ", t)[:100]


NOTICE = (
    "【해외구매대행 안내】\n"
    "· 본 상품은 일본에서 주문 후 매입하여 발송하는 해외구매대행 상품입니다.\n"
    "· 판매가에는 상품가·국제배송비·대행수수료가 포함되어 있습니다. 관세·부가세는 미화 150달러 초과 시 구매자님 부담입니다.\n"
    "· 공급시기: 결제 후 일본 현지에서 즉시 매입하며, 결제일로부터 5영업일 이내 일본에서 발송, 보통 7~14일 이내 도착합니다 (통관 상황에 따라 달라질 수 있습니다).\n"
    "· 개인통관고유부호가 필요합니다.\n"
    "· 취소: 일본 현지 매입 전까지 가능합니다.\n"
    "· 반품: 단순 변심은 수령 후 7일 이내(왕복 국제배송비 구매자 부담), 상품 불량·오배송은 수령 후 3개월 이내 판매자 부담으로 처리합니다.\n"
)
DENKI_NOTE = "· 일본 내수용(100V) 제품입니다. 한국(220V)에서 사용 시 변압기가 필요합니다.\n"


def desc_ko(ko_body, denki=False, region=False):
    """商品説明（標準約款の告知＋品の説明）… 値段の内訳・関税・日数・取り消しと返品の条件を必ず入れる
    region … ゲーム等で日本版であること・旧機種は韓国版本体で動かないことを書く"""
    return NOTICE + (DENKI_NOTE if denki else "") + (REGION_NOTE if region else "") + "\n" + ko_body


def selftest():
    bad = 0
    t = make("シマノ スピニングリール 23 セドナ C3000 (2個セット)", "シマノ", "스피닝 릴 세도나")
    for ok, name in [(t.startswith("[해외] 시마노"), "頭とブランド"), ("C3000" in t, "型番を残す"),
                     ("2개" in t or "2세트" in t, "数量を韓国語の単位に"), (len(t) <= 100, "100字以内")]:
        bad += not ok
        print("✅" if ok else "🔴", name, "｜", t)
    t3 = make("ゼルダの伝説 ティアーズ オブ ザ キングダム -Switch", "任天堂", "젤다의 전설 티어스 오브 더 킹덤")
    ok = "닌텐도 스위치" in t3 and "일본판" in t3
    bad += not ok
    print("✅" if ok else "🔴", "ゲームは機種と「日本版」を入れる ｜", t3)
    t2 = make("ウタマロ キッチン 詰替 250ml × 4個", "Utamaro", "주방세제 리필")
    ok = "250ml" in t2 and "4개" in t2
    bad += not ok
    print("✅" if ok else "🔴", "容量と入り数を残す｜", t2)
    try:
        make("ウタマロ キッチン 詰替", "東邦", "주방세제"); print("🔴 日本語のブランドが商品名に残った"); bad += 1
    except ValueError as e:
        print("✅ 未登録の日本語ブランドは止まる｜", e)
    d = desc_ko("시마노 스피닝 릴", denki=True)
    for ok, name in [("150달러" in d, "関税の告知"), ("3개월" in d, "不良は3ヶ月"), ("220V" in d, "電圧の告知"),
                     ("해외구매대행" in d, "購買代行と明記")]:
        bad += not ok
        print("✅" if ok else "🔴", "説明文：", name)
    print("不一致", bad, "件")
    return bad


if __name__ == "__main__":
    sys.exit(1 if selftest() else 0)
