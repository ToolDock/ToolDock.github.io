/**
 * 米国市場ダッシュボード（/us-market/）の更新を、朝のうちに確実に動かす。
 *
 * GitHub Actions の予約（cron）は混むと何時間も遅れ、06:47 の予約が昼の 11〜14時に動いていた（2026-11）。
 * Google Apps Script の時間主導トリガーは数分のずれで動くので、ここから GitHub の
 * 「workflow_dispatch」（手動実行と同じ）を呼んで、更新を始めさせる。
 *
 * 置き方は scripts/gas/README.md の「米国市場ダッシュボードの更新」。
 *
 * スクリプトのプロパティ：
 *   GH_TOKEN … GitHub の fine-grained personal access token
 *              （リポジトリ ToolDock/ToolDock.github.io だけ、権限は Actions: Read and write だけ）
 */

const REPO = "ToolDock/ToolDock.github.io";
const WORKFLOW = "update-market.yml";
const SITE_JSON = "https://tooldock.github.io/us-market/market.json";

/* 10分おきに呼ばれる。日本時間の火〜土の 6:10〜9:59 だけ動き、
   今日の朝の分がまだサイトに載っていなければ、更新を始めさせる */
function tick() {
  const now = new Date();
  const jst = new Date(now.getTime() + 9 * 3600 * 1000);
  const day = jst.getUTCDay();          /* 0=日 … 6=土。米国の月〜金の取引のあと＝日本の火〜土の朝 */
  const hm = jst.getUTCHours() * 60 + jst.getUTCMinutes();
  if (day < 2 || day > 6) return;
  if (hm < 6 * 60 + 10 || hm >= 10 * 60) return;

  if (alreadyUpdatedToday(jst)) return;
  if (recentlyDispatched()) return;

  const res = UrlFetchApp.fetch(
    "https://api.github.com/repos/" + REPO + "/actions/workflows/" + WORKFLOW + "/dispatches",
    {
      method: "post",
      contentType: "application/json",
      headers: {
        Authorization: "Bearer " + PropertiesService.getScriptProperties().getProperty("GH_TOKEN"),
        Accept: "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28"
      },
      payload: JSON.stringify({ ref: "main", inputs: { force: "false" } }),
      muteHttpExceptions: true
    }
  );
  const code = res.getResponseCode();
  if (code === 204) {
    PropertiesService.getScriptProperties().setProperty("LAST_DISPATCH", String(now.getTime()));
  } else {
    console.error("GitHub に断られました: " + code + " " + res.getContentText());
  }
}

/* サイトの market.json が、今日（日本時間）作られたものなら true */
function alreadyUpdatedToday(jst) {
  try {
    const res = UrlFetchApp.fetch(SITE_JSON + "?t=" + Date.now(), { muteHttpExceptions: true });
    if (res.getResponseCode() !== 200) return false;
    const gen = JSON.parse(res.getContentText()).generated_at || "";   /* 例: 2026-11-26T06:21:03+09:00 */
    const today = Utilities.formatDate(jst, "UTC", "yyyy-MM-dd");
    return gen.slice(0, 10) === today;
  } catch (e) {
    return false;
  }
}

/* 更新には5分ほどかかり、サイトに載るまでさらに1〜2分かかる。そのあいだに重ねて呼ばない */
function recentlyDispatched() {
  const last = Number(PropertiesService.getScriptProperties().getProperty("LAST_DISPATCH") || 0);
  return Date.now() - last < 25 * 60 * 1000;
}

/* はじめに1回だけ手で実行する。10分おきのトリガーを作る（前のものは消してから） */
function setup() {
  ScriptApp.getProjectTriggers().forEach(function (t) { ScriptApp.deleteTrigger(t); });
  ScriptApp.newTrigger("tick").timeBased().everyMinutes(10).create();
}

/* 動くか試す。時間に関係なく、すぐ GitHub に更新を頼む */
function testDispatch() {
  PropertiesService.getScriptProperties().deleteProperty("LAST_DISPATCH");
  const res = UrlFetchApp.fetch(
    "https://api.github.com/repos/" + REPO + "/actions/workflows/" + WORKFLOW + "/dispatches",
    {
      method: "post",
      contentType: "application/json",
      headers: {
        Authorization: "Bearer " + PropertiesService.getScriptProperties().getProperty("GH_TOKEN"),
        Accept: "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28"
      },
      payload: JSON.stringify({ ref: "main", inputs: { force: "false" } }),
      muteHttpExceptions: true
    }
  );
  console.log(res.getResponseCode() === 204 ? "OK（GitHub の Actions の画面で動き出したか見てください）" : res.getResponseCode() + " " + res.getContentText());
}
