# Compound Time Machine — メコン詐欺コンパウンド・タイムマシン

メコン地域(ミャンマー・カンボジア国境)のオンライン詐欺コンパウンド候補7地点を、
公開された衛星画像・制裁データ・地図・報道だけを使って「上空から、時間をさかのぼって」
巡る、OSINTベースの可視化ダッシュボードです。

ジャーナリストや調査機関でさえ生身では近づけない場所を、衛星のタイムマシン・
ガイドツアー・証言・現地の生活情報を通じて疑似的に「観光」できる試作です。

---

## 見る

`dashboard.html` をブラウザでダブルクリックするだけ。サーバーもインストールも不要。

- **インターネット接続が必要**です(衛星タイル・国境タイル・事件写真を外部から読み込む
  ため)。オフラインだと地図が表示されません。地図ライブラリ(Leaflet)は `vendor/` に
  同梱済みなので、CDN がブロックされても UI 自体は読み込めます。
- 共有する場合は **`dashboard.html` ・ `images/` ・ `vendor/`** をセットでコピーして
  ください(相対パス参照のため同階層に必要)。
- 文字コードはUTF-8。Windows / Mac / 主要ブラウザで閲覧できます。

操作: スプラッシュ画面で「ガイドツアー」または「自由に探索」を選択。ツアーでは各地点へ
カメラが降下し、衛星が自動再生されます。「◫ 比較」で2014年と現在を並べ、左に出来事、
右に証言、ツアーパネルに現地の生活カードが表示されます。

---

## データを再生成する

派生データ(衛星フレーム・POI・イベント・画像・証言・現地情報)とダッシュボードは、
ベースとなる `compounds.db` から再生成できます。Python 3 のみ(標準ライブラリだけ、
`pip install` 不要)。

```
python build_all.py          # 全フェーズを実行し dashboard.html を再生成
python build_all.py dash     # dashboard.html だけ再生成(再取得なし)
```

全実行は数分かかり、インターネット接続が必要です(公開APIへアクセス)。各フェーズは
冪等で、再実行すると自前の行を入れ替えます。

実行順(`build_all.py` が自動で処理):

| 順 | スクリプト | 内容 |
|---|---|---|
| 1 | `phase5_poi.py` | POI(建物密度クラスタ・OSM地物)/ ナレーション / 年代キャプション |
| 2 | `phase4_wayback.py` | Esri Wayback の履歴衛星フレーム |
| 3 | `phase6_events.py` | 報道ベースのイベント |
| 4 | `phase7_images.py` | Wikimedia Commons の地点画像(`images/` に保存) |
| 5 | `phase8_event_images.py` | 各イベントのプレビュー画像URL(og:image) |
| 6 | `phase9_testimony.py` | 救出者・被害者の証言 |
| 7 | `phase10_local_life.py` | 周辺の生活拠点 / 日常スニペット |
| 8 | `dash5.py` | `dashboard.html` を生成 |

---

## ファイル構成

```
dashboard.html      成果物(これを開く)
compounds.db        SQLite データベース(ベース + 派生データ)
images/             Commons の地点画像(ローカル保存)
vendor/leaflet/     地図ライブラリ Leaflet 1.9.4(同梱・CDN非依存)
build_all.py        一括再生成スクリプト
phase4〜10_*.py      派生データ生成スクリプト
dash5.py            ダッシュボード生成スクリプト
legacy/             初期のベースデータ構築スクリプト(下記参照)
```

`legacy/` には、`compounds.db` のベースデータ(候補・観測・OSM建物・OFAC制裁等)を
最初に構築したスクリプトを保管しています。サンドボックス専用パスがハードコードされて
おり**そのままでは動きません**。データ構築の記録として残しているもので、現行の
再生成パイプラインには不要です。

---

## データ層(主な収録内容)

- コンパウンド候補 **7地点**(KK Park / Jin Bei / Chinatown / Dara Sakor / O'Smach / Poipet / Bavet)
- 観測フットプリント(OSM建物 + MS Buildings)、OFAC SDN(法人・ウォレット)
- 履歴衛星フレーム(2014〜2026、Esri Wayback)
- イベント **100件**(2000〜2026、出典付き)
- 証言 **36件**(被害者は匿名化、出典付き)
- 地点画像 **8枚**(Commons・自由ライセンス)/ 周辺の生活拠点 **125件**(OSM)
- 日常スニペット **56件**(報道ベース)

---

## 出典・データソース

衛星: Esri World Imagery / Wayback ・ 地図/建物: OpenStreetMap, Microsoft Building
Footprints ・ 制裁: 米財務省 OFAC SDN ・ 地点画像: Wikimedia Commons ・
イベント/証言/日常情報: Reuters, Al Jazeera, Amnesty International, OCCRP, GI-TOC,
CamboJA, RFA, Bangkok Post, Khmer Times, VOD, Nikkei Asia ほか公開報道。
個々の出典URLはダッシュボード内およびDBの `source` テーブルに記録しています。

---

## 公開する

静的ファイルだけで動くので、どのホスティングでも置けば公開できます。

**最小セット**(これだけで公開可能、推奨):
```
dashboard.html
images/
vendor/
.nojekyll
LICENSE       (任意)
README.md     (任意)
```
`compounds.db` ・ `phase*.py` ・ `dash5.py` ・ `build_all.py` ・ `legacy/` は閲覧には不要
(手元での再生成用)。

### ホスティング例

- **Netlify Drop** — https://app.netlify.com/drop に上記フォルダをドラッグ → 即座にURL発行。
  サインアップ不要(永続化する場合はサインアップ)。
- **GitHub Pages** — 新規リポジトリにpush → Settings → Pages → Branch: `main` / root を選択。
  `.nojekyll` を含めてあるのでJekyll処理は無効化されます。
- **Cloudflare Pages / Vercel** — GitHub連携で同様。

### 公開後の仕上げ

`dash5.py` の `<meta property="og:url">` に公開URLを追記して `python build_all.py dash`
で再生成すると、SNSプレビューが完璧になります(現在は og:image だけ設定済み)。

---

## 注意・倫理

- 本プロジェクトは**防御・教育目的のOSINT可視化**であり、すべて公開情報のみを用います。
- 座標は報道エリア中心または観測建物クラスタ重心で、コンパウンド境界の確定ではありません。
- 衛星フレームは z15 タイルのハッシュ差分で抽出しており、雲・季節差も含まれ得ます。
- イベント・ナレーション・日常スニペットは公開報道に基づく編集テキストで、現地確認では
  ありません。一部の日付は月・年単位の精度です。
- 証言は実在の人身売買被害者の公開された証言です。被害者は国籍・年齢・役割のみで匿名化
  しています。
- イベントビューアの写真は出典記事の og:image をリンク表示するもので、著作権は各媒体に
  帰属します(ローカル閲覧用途を前提)。
