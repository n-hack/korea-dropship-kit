# 本番に必要な登録と鍵（オーナーがやる事務）

エージェントはここに書いた鍵が揃うまで、お金が動く操作とモールへの送信をしません。
鍵は `config/` に置きます（`config.example/` に見本あり・リポジトリには入りません）。

| # | 登録 | 何に使うか | 置く鍵 |
|---|---|---|---|
| 1 | 開業届・インボイス登録（個人事業主で可） | クーパンの販売者登録に必要／消費税の還付 | ― |
| 2 | Payoneer | クーパンの売上の受け取り | ― |
| 3 | クーパン販売者登録（Wing・海外販売者） | 売り場 | config/coupang.json |
| 4 | Keepa（有料プラン） | Amazon の値段・在庫・重さを見る | config/keepa.json |
| 5 | Amazon ビジネス＋Ordering API | 仕入れ（機械で発注・請求書が真贋の証拠） | config/abiz.json |
| 6 | HANIRO（発送代行） | 日本→韓国の発送 | config/haniro_cols.json（申請表の列名） |
| 7 | カード（仕入れ用） | 仕入れの支払い | tools/waku.py の LIMIT に実際の枠 |
| 8 | 画像の方針 | Amazon の画像を使うか | config/gazou_policy.json |
| 9 | （任意）NETSEA 等の卸 | 安い仕入れ元 | config/oroshi.json |

## クーパン販売者登録で用意するもの（個人事業主の場合）
- パスポート（有効期限が3か月以上）
- マイナンバーカードか通知カード
- Payoneer の英文の口座証明書
- 開業届の控え（日本語で可）
- インボイスの登録番号
審査は1週間前後。登録後、Wing で Open API の鍵（vendorId・accessKey・secretKey）を発行する。
返品先と出荷地の番号（returnCenterCode・outboundShippingPlaceCode）も Wing で登録して config に入れる。

## 画像の方針（config/gazou_policy.json）
```
{"policy": "strict"}      Amazon の画像を使わない（安全・出せる品が減る）
{"policy": "maker_img"}   メーカー本体の出品の画像だけ使う
{"policy": "loose"}       使う（韓国の購買代行で広く行われている形・権利者の指摘が来たら即取り下げ）
```

## 始め方の順番
1. `bash tools/kensa_all.sh` で道具が動くことを確かめる（鍵は要らない）
2. 1〜6の登録を済ませ、鍵を config/ に置く
3. エージェントが本番用の client を作る（run.py の FakeClient と同じ口）
4. 最初の数件は出品・発注をオーナーが目で確かめる → 問題なければ自動に切り替える
5. 以後は1日数回 run.py を定期実行し、週に1回 urekata.py で売れ方を見て入れ替える
