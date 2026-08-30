# 米国市場ダッシュボード ── 引き継ぎ

`/us-market/` に、今日の米国市場を一面で見るページを追加するための一式です。
**まだ `main` には入れていません。このブランチのままでは公開されません。**

データ取得の仕組みと、動く参考実装まで用意してあります。
サイトへの馴染ませ方（デザイン・スラッグ・登録）は、そちらで判断してください。

---

## 1. まず決めてほしいこと ── チャートライブラリ

参考実装は **Plotly.js を CDN から読んでいます**。動きますが、このサイトには重すぎます。

| | サイズ（min） |
|---|---|
| `js/vendor/chart.umd.min.js`（既存） | 208 KB |
| `js/vendor/encoding-japanese.min.js`（既存） | 228 KB |
| Plotly.js 3.6.0（参考実装が使用） | 約 3.5 MB |
| plotly-basic 3.6.0（散布図のみの部分バンドル） | 約 1 MB |

このサイトの他のツールは最大でも 228 KB です。AdSense を載せた公開ページに
3.5 MB の JS を足すのは、表示速度の面でも割に合わないと思います。

**推奨は、既に vendor 済みの Chart.js で描き直すことです。** 対応は次のとおりで、
Plotly 固有の機能には依存していません。

| 描くもの | Chart.js での実装 |
|---|---|
| 日中足8枚（タイル） | `type: "line"`、`fill` で前日終値との差を塗る。軸は `display: false` |
| 基準価額の年初来 | `type: "line"`、`fill: "origin"` |
| 年初来ドローダウン（2本） | `type: "line"` ×2。片方 `borderDash` |
| Fear & Greed（120度メーター） | `type: "doughnut"` に `rotation: -60, circumference: 120, cutout: "78%"`。針は小さいプラグインを1つ書く |
| VIX（縦メーター） | `type: "bar"`（`indexAxis` 既定）を積み上げ、しきい値は `annotation` か描画プラグイン |

必要な数値・系列は全部 `market.json` に入っているので、
`figures` を無視して生データから描き直せます（→ 4章）。

Plotly のまま行くなら、`plotly-basic.min.js` を `js/vendor/` に置いて
`index.html` の `<script src>` をそちらに向けてください。参考実装が使っているのは
Scatter・shapes・annotations だけなので、basic バンドルで足ります。

---

## 2. 置いたもの

```
market/                          ← 公開されない。データ取得とビルド
├── build_static.py              ビルド本体
├── collect_us_market.py         データ取得（Yahoo / MUFG / CNN）
├── db.py                        SQLite接続
├── requirements.txt             requests, plotly のみ
├── utils/
│   ├── us_market.py             DBから表示用の値を組み立てる
│   └── us_market_figures.py     Plotlyの図（Chart.jsに移すなら不要になる）
├── web/                         公開ファイルの元。ここを直してビルドする
│   ├── index.html
│   ├── board.css
│   ├── board.js
│   └── README.md                market.json の全構造とスタイル変更手順
├── data/
│   └── fund_nav.csv             基準価額の履歴433件（2025-01-01〜）
└── HANDOFF.md                   これ

us-market/                       ← 公開候補。参考実装をビルドしたもの
├── index.html
├── board.css
├── board.js
└── market.json

.github/workflows/
└── update-market.yml            平日 07:00(JST) に自動更新
```

既存ファイルには触っていません。`.gitignore` にビルド中間物の2行だけ足してあります。

---

## 3. サイトに馴染ませるとき

参考実装は単体で完結していて、このサイトの共通パーツを使っていません。
統合するなら次が必要です。

- **`/us-market/index.html` を他のツールと同じ体裁にする**
  `CURRENT_TOOL` → `/js/tool-data.js` → `/js/head.js` → `/js/analytics.js`、
  AdSense、末尾の `#related-tools` + `/js/related.js`。
  静的な `<title>` / `<meta name="description">` / `<link rel="canonical">` も。
- **`js/tool-data.js` の `TOOLS` に追加**（`id` / `title` / `desc` / `seoTitle` /
  `seoDesc` / `category` / `url`）。カテゴリは `life` あたりでしょうか。
- **`/ogp/<id>.png`** を用意
- **`sitemap.xml` / `sitemap-tools.xml`** に追加
- **スラッグ** … 仮に `us-market` にしてあります。`fukuri` や `hakohige` に
  合わせるなら `beikoku-shijo` などでしょうか。**公開前に決めてください。**
  後から変えると canonical と被リンクが動きます。
- **`board.css`** … 単体ページ用に書いてあります。`/style.css` と共通パーツに
  寄せるか、このまま残すかは判断にお任せします。色・余白は `:root` の
  CSS変数にまとめてあるので、値の差し替えだけで揃うようにはしてあります。

---

## 4. market.json の構造

全項目の説明は `market/web/README.md` にあります。要点だけ:

- `rows[].tiles[]` … 8枚のタイル。`price` / `change_pct` などの生値と、
  `price_text` / `change_text` の整形済みテキストの両方が入っています
- `fund` … 基準価額、前日比、年初来騰落、年初来高値からの位置
- `drawdown.years["2026"|"2025"]` … `dates` / `values`（下落率%）/ `max` / `max_date`
- `fear_greed` / `vix` … 値・区分ラベル・区分色
- `figures` … Plotly の `{data, layout}`。**Chart.js に移すならここは捨てて構いません。**
  各タイルの日中足の系列は `figures.tiles["^GSPC"].data[1].x / .y` にあります

`generated_at` はビルド時刻で、市場の最終更新時刻ではありません。
各タイルの `session` が、その値がどの取引日のものかを表します。

---

## 5. データについて

| 項目 | 出典 | 備考 |
|---|---|---|
| S&P500 / NASDAQ100 / NYSE FANG+ / ドル円 / ゴールド / 米国債10年 / BTC / SOX / VIX | Yahoo Finance chart API | 5分足。キー不要だが非公式 |
| eMAXIS Slim 米国株式（S&P500）基準価額 | 三菱UFJアセットマネジメント ファンド情報API | 公式。ファンドコード `253266` |
| Fear & Greed Index | CNN Business | |

- 週末・米国休場日は直近営業日の値になります。BTC だけ24時間動くので日付が
  ずれることがあり、各タイルにセッション日を出しています。
- 基準価額は営業日の夜に前営業日分が確定します。当日分はその日には出ません。

### Yahoo Finance について（自動更新を有効にする前に）

非公式APIで、レート制限も公表されていません。**GitHub Actions の IP からだと
429 で弾かれる可能性があります。** 収集側で 0.8 秒間隔＋指数バックオフを
入れていますが、確実ではありません。

`build_static.py --strict` を付けてあるので、データが1つでも欠けたらビルドを
中止して終了コード1を返します。コミットが走らないので、**公開中のページが
壊れることはありません**。

連続して失敗するようなら、ワークフローを止めて手元ビルドに切り替えるか、
キーのあるAPI（FMP / Finnhub）に `collect_us_market.py` を差し替えてください。
MUFG と CNN は CI からでも問題なく取れます。

---

## 6. ビルド方法

```bash
cd market
pip install -r requirements.txt

# データを取得して /us-market/ に書き出す
python build_static.py --refresh --nav-csv data/fund_nav.csv --out ../us-market
```

`--strict` を足すと、データが欠けているときに書き出さず終了します（自動更新向け）。
`--refresh` なしなら、取得済みの `market/investment_ai.db` から書き出すだけです。

`market/investment_ai.db` と `__pycache__/` はビルド中間物です。`.gitignore` 済み。

---

## 7. 表記について

フッターの免責文（`market.json` の `disclaimer`）は消さないでください。
市況の情報提供であって投資助言ではない、という位置づけで作っています。
`build_static.py` の `DISCLAIMER` が元です。
