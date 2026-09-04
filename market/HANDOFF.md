# 米国市場ダッシュボード ── 引き継ぎ

`/us-market/` に、今日の米国市場を一面で見るページを置いています。

**公開はまだです。** AdSense の審査中なので、審査結果が出るまでマージを待っています。
それ以外の作業（チャートの載せ替え・サイトへの統合）は済んでいます。

---

## 1. チャートライブラリ ── Chart.js に載せ替え済み

参考実装は Plotly.js を CDN から読んでいましたが、サイトに置いてある
Chart.js に描き直しました。

| | サイズ（min） |
|---|---|
| `js/vendor/chart.umd.min.js`（採用） | 204 KB |
| `js/vendor/encoding-japanese.min.js`（サイト内で最大） | 223 KB |
| Plotly.js 3.6.0（元の参考実装） | 4,730 KB |

あわせて `market.json` から `figures`（Plotly の図の定義）を外しました。
これが全体の 93.3% を占めていたので、**201 KB → 40 KB** になっています。
日次でコミットするファイルなので、リポジトリの膨らみ方にも効きます。

描画は `web/board.js` に集約しました。

| 描くもの | どこで |
|---|---|
| タイルの日中足（8枚） | `tileChart()` … Chart.js の折れ線 |
| 円建てS&P500の年初来 | `yenSpxChart()` … Chart.js の折れ線 |
| 年初来ドローダウン | `drawdownChart()` … Chart.js の折れ線2本 |
| Fear & Greed のメーター | `fgGauge()` … 素のSVG |
| VIX のメーター | `vixMeter()` … 素のSVG |

メーター2つは図というより図形なので、SVGを直接書いています。
元の実装が Plotly の図形で描いていたのは Streamlit のサニタイズ対策で、
自前の静的ページではその制約がありません。

`utils/us_market_figures.py` は不要になったので削除しました。
`requirements.txt` に残るのは `requests` だけです。

---

## 2. 置いたもの

```
market/                          <- 公開されない。データ取得とビルド
|-- build_static.py              ビルド本体
|-- collect_us_market.py         データ取得（Yahoo / CNN）
|-- db.py                        SQLite接続
|-- requirements.txt             requests のみ
|-- utils/
|   `-- us_market.py             DBから表示用の値を組み立てる
|-- web/                         公開ファイルの元。ここを直してビルドする
|   |-- index.html
|   |-- board.css
|   |-- board.js
|   `-- README.md                market.json の全構造とスタイル変更手順
|-- data/
`-- HANDOFF.md                   これ

us-market/                       <- 公開候補。ビルドしたもの
|-- index.html
|-- board.css
|-- board.js
`-- market.json

.github/workflows/
`-- update-market.yml            平日 07:00(JST) に自動更新
```

---

## 3. サイトへの統合 ── 済み

- **スラッグは `us-market` で確定。** サイトには英語のスラッグ
  （`roulette` `timer` `matrix` `radix` `counter` `dino` `crystal`）が
  既に多数あるので、ローマ字にそろえる必要はないと判断しました。
  後から変えると canonical と被リンクが動くので、これで固定します。
- `index.html` を他のツールと同じ体裁にしました。
  `CURRENT_TOOL` -> `/js/tool-data.js` -> `/js/head.js` -> `/js/analytics.js`、
  AdSense、末尾の `#related-tools` + `/js/related.js`。
  静的な `<title>` / `<meta name="description">` / `<link rel="canonical">` も
  置いてあります（`head.js` は「既に無ければ補う」作りなので、順序が重要）。
- `js/tool-data.js` に登録（カテゴリは `finance`）
- `/ogp/us-market.png` を既存のテンプレートに合わせて作成
- トップページの一覧は `python3 scripts/build_index.py` で生成する
  （サイトマップは2026-09に廃止しました）
- `board.css` の配色・書体・角丸を `/crystal/` `/kintoku/` にそろえました。
  意味のある色（上げ／下げ、区分の色）だけは残しています。
- **ダークテーマは外しました。** サイトの他のページが持っていないため、
  共通ヘッダーとフッターだけ明るいまま残って浮いてしまいます。

### ヒートマップについて

S&P500の主要86銘柄を、セクターごとに面積と色で出しています。

- 銘柄・セクター・ウェイトの表は `data/sp500_members.json`。
  ウェイトはタイルの面積を決めるためだけの概算値で、画面には出しません。
  **銘柄の入れ替えは年に数回あるので、この表はときどき見直してください。**
- 騰落率は Yahoo から1銘柄1リクエストで取ります。**86リクエストあり、
  他の取得よりずっと重い。** Yahoo は非公式APIなので、まとめて叩くと
  429 を返すことがあります。
- そのため、**ヒートマップが取れなくてもビルドは止めません**。
  `--strict` の判定にも含めていないので、失敗した日はこの節が出ないだけです。
  他の部分は普段どおり更新されます。
- 連続して失敗するようなら、`refresh_heatmap(limit=...)` で銘柄数を減らすか、
  キーのあるAPI（FMP / Finnhub）に差し替えてください。

VIX と S&P500 の1年チャートは日足で、こちらは2リクエストしか増えません。

### 段組みについて1つ注意

サイトは本文が900px、右レールが280pxです。**画面が広いと本文は580pxまで狭まります。**
そのため画面幅のメディアクエリではタイルが4列のまま潰れます。
`repeat(auto-fit, minmax(190px, 1fr))` にして、器の幅で4列と2列を
行き来するようにしてあります（3列にはならない値にしてあります）。

---

## 4. market.json の構造

全項目の説明は `market/web/README.md` にあります。要点だけ:

- `rows[].tiles[]` … 8枚のタイル。`price` / `change_pct` などの生値と、
  `price_text` / `change_text` の整形済みテキストの両方が入っています。
  日中足そのものも `digits` / `times` / `values` として同じ場所にあります
- `yenspx` … 円建てS&P500の年初来騰落、年初来高値からの位置、内訳（米国株ぶんと為替ぶん）
- `yenspx_series` … 年初からの騰落率。`dates` / `values`
- `drawdown.years["2026"|"2025"]` … `dates` / `values`（下落率%）/ `max` / `max_date`
- `fear_greed` / `vix` … 値・区分ラベル・区分色
- `bands` … メーターの区分と色。境目や色を変えるときは Python 側の
  `utils/us_market.py` の `FG_BANDS` / `VIX_BANDS` を直します

`generated_at` はビルド時刻で、市場の最終更新時刻ではありません。
各タイルの `session` が、その値がどの取引日のものかを表します。

---

## 5. データについて

| 項目 | 出典 | 備考 |
|---|---|---|
| S&P500 / NASDAQ100 / NYSE FANG+ / ドル円 / ゴールド / 米国債10年 / BTC / SOX / VIX | Yahoo Finance chart API | 5分足。キー不要だが非公式 |
| 円建てS&P500 | 上記のS&P500（配当込み）とドル円から当方で計算 | 参考値。実際の基準価額ではない |
| Fear & Greed Index | CNN Business | |

- 週末・米国休場日は直近営業日の値になります。BTC だけ24時間動くので日付が
  ずれることがあり、各タイルにセッション日を出しています。
- 円建てS&P500は参考値です。信託報酬も、株価と為替を反映する時刻の違いも入っていません。

### Yahoo Finance について（自動更新を有効にする前に）

非公式APIで、レート制限も公表されていません。**GitHub Actions の IP からだと
429 で弾かれる可能性があります。** 収集側で 0.8 秒間隔＋指数バックオフを
入れていますが、確実ではありません。

`build_static.py --strict` を付けてあるので、データが1つでも欠けたらビルドを
中止して終了コード1を返します。コミットが走らないので、**公開中のページが
壊れることはありません**。

連続して失敗するようなら、ワークフローを止めて手元ビルドに切り替えるか、
キーのあるAPI（FMP / Finnhub）に `collect_us_market.py` を差し替えてください。
CNN は CI からでも問題なく取れます。

なお三菱UFJのファンド情報API（`developer.am.mufg.jp`）は、
2026-08-31 からドメイン全体が403を返すようになり、使うのをやめました。
GitHub Actions の出口が米国のデータセンターで、そこが弾かれています。
ブラウザ相当のヘッダーを全部つけても変わりません。日本から叩けば通ります。

---

## 6. ビルド方法

```bash
cd market
pip install -r requirements.txt

# データを取得して /us-market/ に書き出す
python build_static.py --refresh --out ../us-market
```

`--strict` を足すと、データが欠けているときに書き出さず終了します（自動更新向け）。
`--refresh` なしなら、取得済みの `market/investment_ai.db` から書き出すだけです。

`market/investment_ai.db` と `__pycache__/` はビルド中間物です。`.gitignore` 済み。

---

## 7. 表記について

フッターの免責文（`market.json` の `disclaimer`）は消さないでください。
市況の情報提供であって投資助言ではない、という位置づけで作っています。
`build_static.py` の `DISCLAIMER` が元です。
