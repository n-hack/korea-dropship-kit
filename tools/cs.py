#!/usr/bin/env python3
"""お客様の問い合わせ（クーパン商品Q&A）に24時間以内に答える部品

  python3 cs.py --selftest     … 分類と下書きを検体で確かめる（ネットに出ない）

なぜ … クーパンの販売者点数に「24時間内の回答」がある（公式ブログ・点数の項目）
正本 … developers.coupang.com（2026-09-27 取得）
  問い合わせの取得 GET /v2/providers/openapi/apis/api/v5/vendors/{vendorId}/onlineInquiries
                   inquiryStartAt / inquiryEndAt（yyyy-MM-dd・7日以内）/ answeredType=NOANSWER
  回答           POST /v2/providers/openapi/apis/api/v4/vendors/{vendorId}/onlineInquiries/{inquiryId}/replies
                   body … {"content": 本文（改行は\\n）, "vendorId": …, "replyBy": WING のID}
                   同じ問い合わせに2回答えるとエラー
流れ
  ① 未回答を取る → ② 分類（配送日数・関税・返品・在庫・その他）
  ③ 定型の4種は韓国語の下書きで自動回答 → ④「その他」は答えず、AIエージェントが中身を読んで回答（自動では送らない）
"""
import sys, re

# 定型の回答（事実だけ・約束しない言い方）
T = {
    "配送": "안녕하세요. 문의 주셔서 감사합니다.\n본 상품은 일본에서 해외구매대행으로 발송되는 상품입니다.\n주문 후 일본에서 매입하여 선박으로 발송되며, 통관 후 국내 택배로 전달됩니다.\n보통 주문일로부터 7~14일 정도 소요됩니다(주말·공휴일·통관 상황에 따라 달라질 수 있습니다).\n감사합니다.",
    "関税": "안녕하세요. 문의 주셔서 감사합니다.\n해외구매대행 상품으로 개인통관고유부호가 필요합니다.\n상품 가격이 150달러를 초과하는 경우 관세·부가세가 부과될 수 있으며, 이는 구매자님 부담입니다.\n같은 날 여러 건을 주문하시면 합산 과세될 수 있으니 참고 부탁드립니다.\n감사합니다.",
    "返品": "안녕하세요. 문의 주셔서 감사합니다.\n해외구매대행 상품 특성상, 발송 전 취소는 가능하나 발송 후에는 일본으로의 반송이 필요합니다.\n단순 변심에 의한 반품의 경우 왕복 국제배송비는 구매자님 부담입니다.\n상품 불량·오배송의 경우 사진과 함께 알려주시면 확인 후 처리해 드리겠습니다.\n감사합니다.",
    "在庫": "안녕하세요. 문의 주셔서 감사합니다.\n현재 판매 중인 상품은 주문 가능합니다.\n주문 후 일본 현지에서 매입하여 발송하는 방식으로, 드물게 현지 품절 시에는 바로 연락드리고 전액 환불해 드립니다.\n감사합니다.",
}
K = [
    ("関税", r"관세|통관|개인통관|세금|부가세"),
    ("返品", r"반품|환불|교환|취소|불량|파손|오배송"),
    ("配送", r"배송|언제|도착|발송|며칠|기간|출고"),
    ("在庫", r"재고|품절|구매\s*가능|주문\s*가능|입고"),
]


def classify(text):
    hit = [k for k, p in K if re.search(p, text)]
    if len(hit) == 1:
        return hit[0]
    return "その他"  # 当たりなし、または2つ以上（混ざった問いは機械で答えない）


def draft(text):
    c = classify(text)
    return c, T.get(c)


def selftest():
    cases = [
        ("언제 도착하나요?", "配送"),
        ("관세 나오나요?", "関税"),
        ("반품 가능한가요?", "返品"),
        ("재고 있나요?", "在庫"),
        ("이 제품 220V에서 쓸 수 있나요?", "その他"),        # 電圧 → 人（AI）が読む
        ("배송 늦으면 환불되나요?", "その他"),               # 2つ混ざる → 機械では答えない
        ("색상 차이가 있나요?", "その他"),
    ]
    bad = 0
    for q, want in cases:
        got, body = draft(q)
        ok = got == want and ((body is None) == (want == "その他"))
        bad += not ok
        print("✅" if ok else "🔴", q, "→", got)
    for k, v in T.items():
        if len(v) > 1000 or "\\n" in v:
            print("🔴 本文の形", k); bad += 1
    print("不一致", bad, "件")
    return bad


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        sys.exit(1 if selftest() else 0)
    print(__doc__)
