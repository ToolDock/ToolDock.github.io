# タイピング練習のランキング（Google Apps Script）

/typing-game/ のランキングを受け付けるサーバー。Google スプレッドシートに付けた Apps Script で動かす。

## 置き方（はじめの1回）

1. ランキング専用の Google アカウントを作る（メインのアカウントと切り離すため）
2. そのアカウントで、新しいスプレッドシートを作る（名前は何でもよい）
3. メニューの「拡張機能」→「Apps Script」
4. 最初からある `コード.gs` の中身を消し、`scripts/gas/typing-ranking.gs` の中身を貼る
5. 左の「ファイル」の＋ →「スクリプト」で `engine` というファイルを作り、`typing-game/engine.js` の中身を貼る
6. 保存（Ctrl+S）
7. 右上の「デプロイ」→「新しいデプロイ」→ 歯車で「ウェブアプリ」を選ぶ
   - 次のユーザーとして実行：**自分**
   - アクセスできるユーザー：**全員**
8. 「デプロイ」→ 権限の確認
   - 「Google はこのアプリを確認していません」と出たら「詳細」→「（安全ではないページ）に移動」
   - 許可する中身が「このアプリケーションが適用されるスプレッドシートの表示と管理」だけであることを確かめてから「許可」
     （Gmail やドライブ全体などが並んでいたら、許可せずに止める）
9. 表示された「ウェブアプリ」の URL（`https://script.google.com/macros/s/…/exec`）を、
   `typing-game/index.html` の `const RANK_URL = "";` に入れる

## 直したとき

`typing-game/engine.js` の `VERSION` を上げたら（問題を足した・判定を変えた）、
Apps Script の `engine` に貼り直し、「デプロイ」→「デプロイを管理」→ 鉛筆 →
バージョン「新バージョン」→「デプロイ」。URL は変わらない。
貼り直すまでのあいだ、ランキングは「更新中」になり、登録を受け付けない（遊ぶのはふつうにできる）。

## 記録を消すとき

スプレッドシートの `scores` シートで、その行を消す。1分ほどで表示に反映される。

## しくみ

- 札（`?a=token`）：問題の順番を決める seed と発行時刻に、署名（HMAC）を付けて渡す。署名の鍵はスクリプトのプロパティ `SECRET`（はじめて動いたときに自動で作る）
- 登録（POST `a=submit`）：署名・札の使い回し・経過時間を確かめ、打鍵の記録を engine で打ち直してスコアを計算し直す。
  速すぎる・間隔が機械的すぎる記録は受け付けない。1人（ブラウザごとの id）1つの区分につき、いちばん良い記録だけ残す
- 上位（`?a=top`）：上位100人と、自分の順位。60秒キャッシュ
- 名前：12文字まで、文字・数字と `_ ・ ー -` だけ、1文字目は文字か数字、NGワードは弾く

---

# 米国市場ダッシュボードの更新（Google Apps Script）

`/us-market/` は GitHub Actions（`.github/workflows/update-market.yml`）で毎朝作り直す。
ところが GitHub の予約（cron）は混むと5〜6時間遅れ、06:47 の予約が昼の11〜14時にしか動かなかった（2026-11）。
そこで、時間どおりに動く Apps Script から GitHub に「今すぐ動いて」と頼む（workflow_dispatch）。GitHub の予約は控えとして残す。

`scripts/gas/market-trigger.gs` は、日本時間の火〜土の 6:10〜9:59 に10分おきに目を覚まし、
サイトの `market.json` がまだ今日の分でなければ、GitHub に更新を頼む（頼んだあと25分は重ねて頼まない）。
米国の引け（日本時間の朝6時、夏は5時）のあと、まだ前の日の値しか取れないときは、GitHub 側が何もせずに終わり、次の回にまた頼む。

## 置き方（はじめの1回）

1. GitHub でトークンを作る：右上のアイコン →「Settings」→ 左下の「Developer settings」→「Personal access tokens」→「Fine-grained tokens」→「Generate new token」
   - Token name：`tooldock-market`（何でもよい）／ Expiration：1年など
   - Repository access：「Only select repositories」で **ToolDock/ToolDock.github.io** だけ
   - Permissions →「Repository permissions」の **Actions** を「Read and write」（ほかは触らない）
   - 「Generate token」→ 出てきた `github_pat_…` を控える（この画面を閉じると二度と見られない）
2. https://script.google.com で「新しいプロジェクト」（どのアカウントでもよい）
3. 最初からある `コード.gs` の中身を消し、`scripts/gas/market-trigger.gs` の中身を貼って保存
4. 左の歯車「プロジェクトの設定」→ 下の「スクリプト プロパティ」→「スクリプト プロパティを追加」
   - プロパティ：`GH_TOKEN` ／ 値：1で控えた `github_pat_…`
5. エディタに戻り、上の関数の選択で `testDispatch` を選んで「実行」→ 権限を許可
   - 許可する中身が「外部サービスへの接続」と「スクリプトがあなたが不在のときに実行されることを許可」だけであることを確かめる
   - 実行ログに「OK」と出て、GitHub の Actions の画面で「昨日の米国株を更新」が動き出せば成功
6. 関数の選択で `setup` を選んで「実行」（10分おきのトリガーができる。左の時計のアイコンで確かめられる）

## トークンの期限が切れたら

1 と同じ手順で作り直し、4 の `GH_TOKEN` の値を差し替える。切れているあいだは、GitHub の予約（遅いほう）だけで更新される。
