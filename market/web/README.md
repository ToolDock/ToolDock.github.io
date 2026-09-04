# 昨日の米国株 ── GitHub Pages 用の静的ダッシュボード

`build_static.py` が出力する `dist/` を、そのまま GitHub Pages に置けば動きます。
サーバー処理はなく、ブラウザが `market.json` を読んで描画するだけです。

```
dist/
  index.html    骨組み（このフォルダの index.html のコピー）
  board.css     見た目（同 board.css のコピー）
  board.js      market.json を読んで描画（同 board.js のコピー）
  market.json   数値と系列（ビルド時に生成）
```

`index.html` / `board.css` / `board.js` の編集は、この `web/` の方を直してください。
`dist/` はビルドのたびに上書きされます。

## ビルド

```bash
python build_static.py --refresh
```

`--refresh` を付けると先に最新データを取得します。付けなければ DB のキャッシュから
書き出すだけです。出力先を変えるときは `--out docs` のように指定します。

## 設置

`dist/` の中身を Pages リポジトリの公開ディレクトリ（`/` か `/docs`）に置くだけです。
サブディレクトリに置いても、参照はすべて相対パス（`./board.css` など）なので動きます。

外部リソースはありません。チャートはサイトに置いてある Chart.js
（`/js/vendor/chart.umd.min.js`、204KB）を読みます。ここだけ絶対パスなので、
別のサイトに置くときは `index.html` の `<script src>` を直してください。

## デザインを変えるとき

### 色・余白・角丸

`board.css` の `:root` にまとめてあります。ダークテーマは
`@media (prefers-color-scheme: dark)` のブロックです。

チャートの目盛りの文字色は、CSS変数 `--chart-font-color` を `board.js` の
`fontColor()` が読んで Chart.js に渡しています。`:root` の値を変えれば
目盛りとメーターの文字色も一緒に変わります。OSのテーマが切り替わったときは
`board.js` の末尾が拾って描き直します。

### レイアウト

`index.html` はほぼ空の骨組みで、中身は `board.js` が `market.json` から流し込みます。
タイル1枚の構造は `<template id="tpl-tile">` にあるので、そこを書き換えれば
8枚すべてに反映されます。クラス名を変えた場合は `board.js` の
`setText(node, ".tile__label", ...)` のセレクタも合わせてください。

### 段組み

- 1・2段目のタイル … `.row__tiles`（`grid-template-columns: repeat(4, 1fr)`）
- 3段目の円建てS&P500 … `.yenspx`（数値 : チャート ＝ `1fr : 2.4fr`）
- 5段目のセンチメント … `.sentiment`（左右2分割）

`@media (max-width: 1000px)` で2列、`560px` で1列に落としています。

### チャートそのもの

`market.json` が持つのは数値と系列だけで、図の定義は入っていません。
描画は全部 `board.js` の中にあります。

| 描くもの | どこで |
|---|---|
| タイルの日中足（8枚） | `tileChart()` … Chart.js の折れ線。前日終値の線との差を塗る |
| 円建てS&P500の年初来 | `yenSpxChart()` … Chart.js の折れ線 |
| 年初来ドローダウン | `drawdownChart()` … Chart.js の折れ線2本 |
| Fear & Greed のメーター | `fgGauge()` … 素のSVG |
| VIX のメーター | `vixMeter()` … 素のSVG |

メーター2つは図というより図形なので、Chart.js を曲げるよりSVGを直接書くほうが
短く正確になります。色は `market.json` の `bands` が持っているので、
区分の境目や色を変えるときは Python 側（`utils/us_market.py` の
`FG_BANDS` / `VIX_BANDS`）を直してください。

## market.json の構造

```jsonc
{
  // ページ全体がどの取引日のものか。米国株（^GSPC）の最終セッションに合わせる。
  // ドル円・BTCは24時間動いているので、この日にそろえて終値を出す
  "session": "2026-08-28",
  "session_text": "2026年8月28日",

  "generated_at": "2026-08-30T22:00:00+09:00",   // ISO8601
  "generated_at_text": "2026-08-30 22:00",

  "rows": [                                       // 1段目・2段目
    {
      "title": "主要指数・為替",
      "tiles": [
        {
          "symbol": "^GSPC",      // Yahoo Finance のシンボル
          "slug": "gspc",         // HTMLのid用
          "label": "S&P500",
          "session": "2026-08-28", // どのセッションの値か（取引所ローカル日付）
                                   // 通常は上の "session" と同じ。その市場だけ
                                   // 休場だった場合のみ、その前の営業日に落ちる
          "price": 7711.76,
          "price_text": "7,711.76",
          "prev_close": 7730.99,
          "change": -19.23,
          "change_pct": -0.25,
          "change_bp": -1923.0,    // 金利用（1bp = 0.01%）
          "change_mode": "pct",    // "pct" か "bp"
          "change_text": "-19.23（-0.25%）",
          "direction": -1,         // 1=上げ / -1=下げ / 0=変わらず
          "arrow": "▼",

          "digits": 2,             // 小数何桁で見せるか
          "times":  ["09:30", "09:35", "…"],  // 日中足。日付は session が持つ
          "values": [7738.98, "…"]
        }
      ]
    }
  ],

  "yenspx_chart_title": "円建てS&P500の2026年（年初からの騰落）",
  "yenspx": {                                     // 3段目。データがなければ null
    "title": "円建てS&P500（参考値）",
    "year": 2026,
    "source": "^SP500TR",                         // 実際に使えた指数
    "dividends": true,                            // 配当込みか。false なら ^GSPC に落ちた
    "date": "2026-09-03", "date_text": "2026年9月3日",
    "ytd_pct": 12.53, "ytd_text": "+12.53%",      // 年初来騰落率(%)
    "start_date": "2026-01-02", "start_date_text": "1月2日",
    "from_peak_pct": -2.66, "from_peak_text": "-2.66%",
    "parts": {                                    // 年初来の内訳。なければ null
      "stock_pct": 12.97, "fx_pct": -0.39,        // (1+株)×(1+為替)-1 = 年初来
      "stock_text": "米国株 +12.97%", "fx_text": "為替 -0.39%"
    },
    "note": "…"                                   // 参考値である旨。取得元で書き分ける
  },

  "drawdown": {                                   // 4段目
    "title": "年初来ドローダウンの推移（2026年 と 2025年）",
    "note": "…",
    "years": {
      "2026": {
        "dates":  ["2026-01-05", "…"],
        "values": [0.0, -0.31, "…"],              // 年初来高値からの下落率(%)、0以下
        "max": -8.35, "max_date": "2026-03-31"    // その年の最大ドローダウン
      },
      "2025": { "…": "同上" }
    }
  },

  "fear_greed": {                                 // 5段目左。なければ null
    "value": 54.4, "value_text": "54",
    "label_en": "Neutral", "label_ja": "中立", "color": "#fbc02d",
    "date": "2026-08-30",
    "history": [{ "label": "前営業日", "value": 54.4 }, "…"],
    "note": "…"
  },

  "vix": {                                        // 5段目右。なければ null
    "value": 14.43, "value_text": "14.43",
    "change_text": "-0.08（-0.55%）", "direction": -1,
    "session": "2026-08-28",
    "band_label": "落ち着き", "band_color": "#2e7d32",
    "note": "…"
  },

  "yenspx_series": {                              // 3段目のチャート用。なければ null
    "dates":  ["2026-01-02", "…"],
    "values": [0.0, 0.31, "…"]                    // 年初からの騰落率(%)。0が年初
  },

  "bands": {                                      // メーターの区分。色もここ
    "fear_greed": [[0, 25, "Extreme Fear", "極度の恐怖", "#b91c1c"], "…"],
    "vix":        [[0, 15, "落ち着き", "#15803d"], "…"]
  },

  "fg_chart": {                                   // Fear & Greed の1年。なければ null
    "dates":  ["2025-09-01", "…"],
    "values": [61.2, "…"]
  },

  "vix_chart": {                                  // VIXとS&P500の1年。なければ null
    "dates":  ["2025-09-01", "…"],
    "vix":    [16.4, "…"],
    "sp500":  [6421.5, "…"]                       // 日付はvixと共通のものだけ残してある
  },

  "heatmap": {                                    // 主要銘柄。なければ null（節ごと出ない）
    "session": "2026-08-28", "count": 86, "up": 35, "down": 51,
    "sectors": [{
      "name": "情報技術", "weight": 21.6,         // 面積の比。画面には出さない
      "items": [{ "symbol": "NVDA", "name": "NVIDIA", "weight": 7.0,
                  "change_pct": -1.23, "change_text": "-1.23%" }]
    }]
  },

  "sources": ["…"],
  "disclaimer": "…"
}
```

数値は生の値と整形済みテキストの両方を入れてあるので、書式を変えたい場合は
`price` / `change_pct` などから作り直せます。

## データについて

| 項目 | 出典 | 更新のタイミング |
|---|---|---|
| 指数・為替・金利・コモディティ・BTC | Yahoo Finance chart API | 5分足。米国株の最終セッションにそろえる |
| 円建てS&P500 | 上記のS&P500（配当込み）とドル円から当方で計算 | 参考値。実際の基準価額ではない |
| Fear & Greed | CNN Business | 1日1回 |

米国休場日・週末は、直近の営業日のデータが出ます。BTCだけは24時間動くので
別の日付になることがあり、各タイルにセッション日を明記しています。

`generated_at` はビルドを実行した時刻で、市場の最終更新時刻ではありません。

## 注意

- Yahoo Finance の API は公式のドキュメントがなく、連続アクセスすると 429 を返します。
  収集側で0.8秒間隔＋指数バックオフを入れていますが、頻繁なビルドは避けてください。
- 本ページは市況の把握を目的とした情報提供で、投資助言ではありません。
  フッターの `disclaimer` は消さないでください。
