#!/usr/bin/env python3
"""せどりの1周（定期実行から呼ぶ本体）… 部品を全部つなぐ。外との出入りは client に集めてあるので、検体で丸ごと通せる

  python3 run.py --selftest   … 検体の client で1周を丸ごと通す（ネットに出ない・お金は動かない）
  python3 run.py --dry        … 段取りと全部品の検算だけ
  python3 run.py              … 本番（config/coupang.json と abiz.json が要る。無ければ止まる）

1周の順番（注文を先に回す＝出荷の期限と取消率に直結するから）
  ① 注文 … orders.plan → 関税（kanzei_ok）→ 仕入れ元（shiire）→ 発注の関門（abiz.gate）→ 発注 → 証拠（shoko）→ HANIRO の表（haniro）
  ② 追跡番号 … HANIRO の追跡が動いた荷物だけ coupang.invoice
  ③ 見張り … 出品中の品の仕入れ元を見て、止める／値を直す（watch.decide → coupang.act）
  ④ 問い合わせ … 定型は自動で答え、それ以外は AI の読む箱へ（cs.draft）
  ⑤ カード枠 … waku.judge（足りなければ⑥で新しい出品をしない）
  ⑥ 新しい出品 … kc → gazou（画像の出どころ）→ 利益と下限の売値 → 韓国語 → 関税の告知 → カテゴリ → pace → coupang.build/send
  ⑦ 記録 … 1周の件数を logs に残す（実績と売れ方は月次で jisseki・urekata）
"""
import sys, os, json, datetime
import paths
import kc, rieki, pace, coupang, orders, abiz, shoko, cs, waku, watch, gazou, kanzei_ok, shiire, haniro, title_ko

CONF = paths.CONF
LOG = paths.data("run.jsonl")


def cycle(cl, st, today="2026-10-01"):
    """cl … 外との出入り（本番はクーパン／Amazon ビジネス／Keepa／HANIRO／ブラウザ）・st … 前回までの状態"""
    R = cl.rates()
    rep = {"注文": 0, "仕入れ": 0, "取消候補": 0, "保留": 0, "追跡": 0, "止めた": 0, "値直し": 0,
           "自動回答": 0, "AIへ": 0, "出品": 0, "出品止め": [], "枠": ""}
    buy_rows = []
    # ① 注文
    for o in cl.orders():
        rep["注文"] += 1
        for p in orders.plan(o, cl.detail, R["rate"], R["usd"], cl.krw_of_item):
            if p["act"] == "保留" and "関税" in p.get("why", ""):
                act, why = kanzei_ok.on_order(p, st["marked"].get(p["asin"], False))
                if act != "仕入れる":
                    rep["取消候補"] += 1; cl.cancel_candidate(p, why); continue
                p = orders.plan(o, cl.detail, R["rate"], R["usd"], cl.krw_of_item, customs_ok=True)[0]
            if p["act"] == "取り消し候補":
                rep["取消候補"] += 1; cl.cancel_candidate(p, p["why"]); continue
            if p["act"] == "保留":
                rep["保留"] += 1; continue
            src = shiire.choose(cl.offers(p["asin"]))
            if not src:
                rep["取消候補"] += 1; cl.cancel_candidate(p, "どの仕入れ元にも在庫なし"); continue
            go, why = abiz.gate(p, st["ledger"], st["today_total"], len(st["ledger"]))
            if not go:
                rep["保留"] += 1; continue
            cl.accept([o.get("shipmentBoxId")])
            amz_no = cl.buy(src, abiz.build(p["orderId"], p["asin"], p["qty"]))
            st["ledger"].append({"key": f"{p['orderId']}-{p['asin']}"}); st["today_total"] += src["total"]
            shoko.add({"kounyusaki": "Amazon.co.jp" if src["src"] == "amazon" else src["src"], "date": today, "asin": p["asin"],
                       "title": p.get("haniro", {}).get("item", p["asin"]), "qty": p["qty"], "jpy": src["total"],
                       "amazon_order": amz_no, "coupang_order": str(p["orderId"])}, st["shoko_path"])
            buy_rows.append(p); rep["仕入れ"] += 1
    rows, ng = haniro.rows_from(buy_rows)
    if rows:
        cl.haniro_upload(haniro.write(rows, st["haniro_csv"]))
    for ref, miss in ng:
        cl.to_ai(f"HANIRO の表に入らない注文 {ref}（欠け {miss}）")
    # ② 追跡番号
    tr = cl.tracking()
    if tr:
        moved = [t for t in tr if t.get("moved")]
        if moved:
            cl.invoice(tr); rep["追跡"] = len(moved)
    # ③ 見張り
    for it in cl.listed():
        a, why = watch.decide(it, cl.detail(it["asin"]), R["rate"], R["usd"])
        if a == "止める":
            cl.act("止める", it["vid"], None); rep["止めた"] += 1
        elif a == "値を直す":
            cl.act("値を直す", it["vid"], rieki.floor_krw(cl.detail(it["asin"])["jpy"], it.get("kg", 1.5), 500, **R)); rep["値直し"] += 1
    # ④ 問い合わせ
    for q in cl.questions():
        kind, body = cs.draft(q["text"])
        if body:
            cl.answer(q["id"], body); rep["自動回答"] += 1
        else:
            cl.to_ai(f"問い合わせ {q['id']}: {q['text']}"); rep["AIへ"] += 1
    # ⑤ カード枠
    wj, left, need = waku.judge(cl.card_used(), len(cl.listed()), st.get("sell_rate", 0.005), st.get("avg_cost", 15000))
    rep["枠"] = wj
    # ⑥ 新しい出品
    ok = []
    for c in cl.candidates():
        j, why = kc.judge(c["title"])
        if j == "止める":
            rep["出品止め"].append((c["asin"], why)); continue
        imgs = gazou.pick(c["images"])
        if not imgs:
            rep["出品止め"].append((c["asin"], "使ってよい画像が無い")); continue
        pr = rieki.calc(c["krw"], c["jpy"], c["kg"] * 1.3, **R)["利益_円"]
        if c["krw"] < coupang.MIN_KRW or pr < 500:
            rep["出品止め"].append((c["asin"], f"売値{c['krw']}ウォン・利益{pr}円")); continue
        ok.append({**c, "profit": pr, "images_ok": imgs})
    for c in pace.pick(ok, st.get("week", 0), len(cl.listed()), waku_judge=wj):
        t = title_ko.make(c["title"], c["brand"], c["ko_body"])
        d = title_ko.desc_ko(c["ko_body"], denki=kc.judge(c["title"])[0] == "確かめる")
        t, d, marked = kanzei_ok.mark(t, d, c["jpy"], R["usd"] / R["rate"], 1 / R["rate"])   # 円→ドル＝usd÷rate
        cat = cl.category(t, c["brand"])
        if not cat:
            rep["出品止め"].append((c["asin"], "カテゴリ推薦が SUCCESS でない")); continue
        cl.send(coupang.build({"asin": c["asin"], "title_ko": t, "desc_ko": d, "krw": c["krw"], "category": cat,
                               "images": c["images_ok"], "brand": c["brand"]}, cl.conf))
        st["marked"][c["asin"]] = marked
        rep["出品"] += 1
    return rep


class FakeClient:
    """検体の外界 … 本番の client と同じ口を持つ（本番は鍵が来てから同じ名前で作る）"""
    conf = coupang.DUMMY

    def __init__(s):
        s.log = []
        s.det = {"A1": {"stock": 9, "jpy": 6000, "weight_g": 400}, "W1": {"stock": 9, "jpy": 30000, "weight_g": 300},
                 "L1": {"stock": 0, "jpy": 5000, "weight_g": 300}}

    def rates(s): return {"rate": 0.116015, "usd": 0.000737}   # rate＝1ウォンの円・usd＝1ウォンのドル（rieki と同じ）
    def detail(s, a): return s.det.get(a, {"stock": 9, "jpy": 6000, "weight_g": 400})
    def krw_of_item(s, it): return {"A1": 90000, "W1": 480000}.get(it["externalVendorSkuCode"], 90000)
    def offers(s, a): d = s.detail(a); return [{"src": "amazon", "stock": d["stock"], "jpy": d["jpy"], "ship_jpy": 0}]
    def orders(s):
        return [{"orderId": 1, "shipmentBoxId": 11, "receiver": {"name": "김", "addr1": "서울", "postCode": "04524", "safeNumber": "050-1"},
                 "overseaShippingInfoDto": {"personalCustomsClearanceCode": "P1"},
                 "orderItems": [{"externalVendorSkuCode": "A1", "shippingCount": 1, "sellerProductName": "릴"}]},
                {"orderId": 2, "shipmentBoxId": 12, "receiver": {"name": "이", "addr1": "부산", "postCode": "1", "safeNumber": "050-2"},
                 "overseaShippingInfoDto": {"personalCustomsClearanceCode": "P2"},
                 "orderItems": [{"externalVendorSkuCode": "W1", "shippingCount": 1, "sellerProductName": "시계"}]}]
    def cancel_candidate(s, p, why): s.log.append(("取消候補", p["asin"], why))
    def accept(s, ids): s.log.append(("受付", ids))
    def buy(s, src, body): s.log.append(("発注", body)); return "250-" + str(len(s.log))
    def haniro_upload(s, path): s.log.append(("HANIRO", path))
    def to_ai(s, msg): s.log.append(("AIへ", msg))
    def tracking(s): return [{"shipmentBoxId": 11, "orderId": 1, "vendorItemId": 1, "invoiceNumber": "H1", "moved": True}]
    def invoice(s, rows): s.log.append(("追跡返し", len(rows)))
    def listed(s): return [{"asin": "L1", "vid": 9, "krw": 60000, "jpy": 5000}]
    def act(s, a, vid, krw): s.log.append((a, vid))
    def questions(s): return [{"id": 1, "text": "언제 도착하나요?"}, {"id": 2, "text": "색상 다른 것도 있나요?"}]
    def answer(s, qid, body): s.log.append(("回答", qid))
    def card_used(s): return 0
    def category(s, t, b): return 1
    def send(s, body): s.log.append(("出品", body["items"][0]["externalVendorSku"]))
    def candidates(s):
        return [{"asin": "C1", "title": "シチズン アテッサ CB0287-68L", "brand": "シチズン", "ko_body": "아테사 전파시계", "jpy": 30000,
                 "kg": 0.3, "krw": 480000, "images": [{"url": "u1", "src": "wholesale_ok"}]},
                {"asin": "C2", "title": "セイコー プレザージュ SARY238", "brand": "セイコー", "ko_body": "프레사쥬", "jpy": 20000,
                 "kg": 0.3, "krw": 300000, "images": [{"url": "u2", "src": "amazon"}]},
                {"asin": "C3", "title": "Anker USB急速充電器 20W", "brand": "Anker", "ko_body": "충전기", "jpy": 2000,
                 "kg": 0.2, "krw": 60000, "images": [{"url": "u3", "src": "wholesale_ok"}]}]


def selftest():
    import tempfile
    cl = FakeClient()
    st = {"ledger": [], "today_total": 0, "marked": {"W1": True}, "shoko_path": tempfile.mktemp(),
          "haniro_csv": tempfile.mktemp(suffix=".csv")}
    rep = cycle(cl, st)
    bad = 0
    checks = [
        (rep["注文"] == 2 and rep["仕入れ"] == 2, "注文2件とも仕入れ（W1 は関税の告知済みなので保留にしない）"),
        (any(x[0] == "HANIRO" for x in cl.log), "HANIRO の申請表を上げた"),
        (rep["追跡"] == 1, "動いた荷物の追跡番号を返した"),
        (rep["止めた"] == 1, "仕入れ元の在庫切れ（L1）を止めた"),
        (rep["自動回答"] == 1 and rep["AIへ"] == 1, "定型1件は自動回答・それ以外は AI へ"),
        (rep["出品"] == 1 and st["marked"].get("C1") is True, "C1 だけ出品し、150ドル超なので関税の印を付けた"),
        (any(a == "C2" and "画像" in w for a, w in rep["出品止め"]), "C2 は Amazon 画像のみ → policy=strict で止めた"),
        (any(a == "C3" for a, w in rep["出品止め"]), "C3（充電器）は kc で止めた"),
        (len(shoko.find("1", st["shoko_path"])) == 1, "証拠の台帳に注文1が入った"),
    ]
    for ok, name in checks:
        bad += not ok
        print("✅" if ok else "🔴", name)
    for p in (st["shoko_path"], st["haniro_csv"]):
        if os.path.exists(p):
            os.remove(p)
    print("報告", {k: v for k, v in rep.items() if k != "出品止め"})
    print("不一致", bad, "件")
    return bad


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        sys.exit(1 if selftest() else 0)
    if "--dry" in sys.argv:
        import subprocess
        r = subprocess.run(["bash", os.path.join(os.path.dirname(__file__), "kensa_all.sh")], capture_output=True, text=True)
        print(r.stdout.strip())
        sys.exit(r.returncode)
    if not (os.path.exists(f"{CONF}/coupang.json") and os.path.exists(f"{CONF}/abiz.json")):
        sys.exit("鍵が無いので止めます（クーパン・Amazon ビジネスの登録後に config/ へ置く）")
    sys.exit("本番の client（live.py）は鍵が来てから同じ口で作る")
