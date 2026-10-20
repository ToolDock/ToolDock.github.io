# ToolDock：作業メモ（Claude 向け）

## Google のインデックス（2026-10 時点）

持ち主がすでに試したこと。もう一度すすめない。

- Search Console へのサイトマップ送信（`sitemap.xml?v=2` のような付け替えも3回）。表示は「取得できませんでした」のまま
- URL検査で `sitemap.xml` の公開URLテスト
- 選手一覧 `/player/` のインデックス登録リクエスト
- 主な選手ページの個別リクエスト（日本シリーズ出場選手など）

サイト側で確認済みのこと：サイトマップは正しいXML（約3,000件）、robots.txt は全許可でサイトマップを記載、noindex は無し、
`/player/` から全選手ページへ普通のリンクがある。

**「様子見しましょう」で話を締めない。** 設定や申請で打てる手は打ち終えている。
提案するときは、こちらで実装できる具体的な手（内部リンク・サイトマップの中身など）にする。
関係のない外部サイトにリンクを置く案は、持ち主が好まない。

## Bing

- Bing Webmaster Tools 登録済み（Search Console から取り込み、2026-10-19）。サイトマップは受理済み
- IndexNow は `.github/workflows/indexnow.yml` で、main への push とプロ野球データ更新のたびに送っている

## ツールを足す・名前や説明を変えたとき

SNSとGoogleが最初に読むHTMLに、OGP・パンくず・「同じカテゴリのツール」のリンクを書き込んでおく
（head.js・related.js はJSで書くため、それだけでは読まれない）。

    python3 scripts/static_html.py

## お知らせ（最近の更新）

ツールを公開したり、目に見えるアップデート・不具合の修正をしたりしたら、`js/tool-data.js` の
`window.UPDATES` の先頭に1行足し、`python3 scripts/build_index.py` を実行する
（トップの「最近の更新」はHTMLに書き込み、各ページの右レールは sidebar.js が同じ一覧から出す）。
