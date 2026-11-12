/** @OnlyCurrentDoc */
/*
 * タイピング練習（/typing-game/）のランキング。Google Apps Script で動かす。
 *
 * 置き方は scripts/gas/README.md。
 * 同じプロジェクトに「engine.gs」として typing-game/engine.js の中身を貼っておくこと
 * （問題とローマ字の判定・スコアの計算を、ページと同じもので確かめるため）。
 *
 * ■ 安全のための決まり
 * - 上の @OnlyCurrentDoc で、このスクリプトが触れるのは、入れ物のスプレッドシート1枚だけ
 * - 外からできるのは「札をもらう」「上位を見る」「スコアを登録する」の3つだけ
 * - スコアはページから送られた数字を使わず、打鍵の記録を打ち直して計算し直す
 * - 問題の順番は、サーバーが渡す札（seed）で決まる。札には署名を付け、1回しか使えない
 */

const SHEET_NAME = "scores";
const HEAD = ["mode", "sec", "pid", "name", "score", "kpm", "rkpm", "acc", "lat", "ok", "miss", "at"];
const SECS = [30, 60, 120];
const TOP_N = 100;
const NG = ["死ね", "しね", "シネ", "殺す", "ころす", "コロス", "ちんこ", "チンコ", "ちんぽ", "チンポ", "まんこ", "マンコ",
  "せっくす", "セックス", "sex", "fuck", "shit", "bitch", "porn", "http", "www", ".com"];

function doGet(e) {
  try {
    const p = (e && e.parameter) || {};
    if (p.a === "token") return out_(issueToken_(p));
    if (p.a === "top") return out_(top_(p));
    return out_({ ok: false, msg: "不明な要求です" });
  } catch (err) {
    console.error(err);
    return out_({ ok: false, msg: "サーバーでエラーが起きました" });
  }
}

function doPost(e) {
  try {
    const body = e && e.postData && e.postData.contents;
    if (!body || body.length > 60000) return out_({ ok: false, msg: "記録が大きすぎます" });
    const b = JSON.parse(body);
    if (b && b.a === "submit") return out_(submit_(b));
    return out_({ ok: false, msg: "不明な要求です" });
  } catch (err) {
    console.error(err);
    return out_({ ok: false, msg: "サーバーでエラーが起きました" });
  }
}

function out_(o) {
  return ContentService.createTextOutput(JSON.stringify(o)).setMimeType(ContentService.MimeType.JSON);
}

/* ---------- 札（問題の順番を決める seed）---------- */
function secret_() {
  const pr = PropertiesService.getScriptProperties();
  let s = pr.getProperty("SECRET");
  if (!s) { s = Utilities.getUuid() + Utilities.getUuid(); pr.setProperty("SECRET", s); }
  return s;
}
function sign_(str) {
  return Utilities.base64EncodeWebSafe(Utilities.computeHmacSha256Signature(str, secret_()));
}
function issueToken_(p) {
  if (Number(p.v) !== TDT.VERSION) return { ok: false, msg: "ランキングは更新中です" };
  if (!rate_("tok", 300)) return { ok: false, msg: "混み合っています" };
  const seed = Math.floor(Math.random() * 4294967296);
  const iat = Date.now();
  return { ok: true, token: { seed: seed, iat: iat, sig: sign_(seed + "." + iat) } };
}

/* 1分あたりの受付数（全体）に上限を付ける */
function rate_(kind, perMin) {
  const c = CacheService.getScriptCache();
  const k = "rl_" + kind + "_" + Math.floor(Date.now() / 60000);
  const n = Number(c.get(k) || 0) + 1;
  c.put(k, String(n), 120);
  return n <= perMin;
}

/* ---------- 名前 ---------- */
function cleanName_(n) {
  if (typeof n !== "string") return null;
  n = n.normalize("NFKC").replace(/\s+/g, " ").trim();
  if (!n || Array.from(n).length > 12) return null;
  // 1文字目は文字か数字（= + - @ で始まる数式を入れさせない）
  if (!/^[\p{L}\p{N}][\p{L}\p{N}\p{M} _・ー\-]*$/u.test(n)) return null;
  const low = n.toLowerCase();
  if (NG.some(w => low.indexOf(w.toLowerCase()) >= 0)) return null;
  return n;
}

/* ---------- 人間らしい記録か ---------- */
function plausible_(times, ev) {
  if (ev.ok + ev.miss < 20) return "打鍵が少なすぎます";
  if (ev.kpm > 1500) return "記録を確かめられませんでした";
  const iv = [];
  for (let i = 1; i < times.length; i++) iv.push(times[i] - times[i - 1]);
  if (iv.length && iv.filter(x => x < 10).length / iv.length > 0.3) return "記録を確かめられませんでした";
  const use = iv.filter(x => x <= 3000);
  if (use.length >= 100) {
    const mean = use.reduce((a, b) => a + b, 0) / use.length;
    const sd = Math.sqrt(use.reduce((a, b) => a + (b - mean) * (b - mean), 0) / use.length);
    if (mean > 0 && sd / mean < 0.12) return "記録を確かめられませんでした";
  }
  return null;
}

/* ---------- 登録 ---------- */
function submit_(b) {
  if (Number(b.v) !== TDT.VERSION) return { ok: false, msg: "ランキングは更新中です。ページを読み込み直してから、もう一度遊んでください" };
  if (!rate_("sub", 60)) return { ok: false, msg: "混み合っています。少し待ってから、もう一度押してください" };

  const t = b.tok || {};
  if (!Number.isInteger(t.seed) || !Number.isInteger(t.iat) || typeof t.sig !== "string" || t.sig !== sign_(t.seed + "." + t.iat))
    return { ok: false, msg: "記録を確かめられませんでした" };
  const mode = String(b.mode), sec = Number(b.sec);
  if (!TDT.POOL[mode] || SECS.indexOf(sec) < 0) return { ok: false, msg: "設定が正しくありません" };
  const age = Date.now() - t.iat;
  if (age < sec * 1000 - 1000 || age > 6 * 3600 * 1000) return { ok: false, msg: "記録を確かめられませんでした（時間切れ）" };

  const pid = String(b.pid || "");
  if (!/^[0-9a-f]{16}$/.test(pid)) return { ok: false, msg: "記録を確かめられませんでした" };
  const name = cleanName_(b.name);
  if (!name) return { ok: false, msg: "名前に使えない文字か言葉が入っています（12文字まで。記号は _ ・ ー - だけ）" };
  if (typeof b.keys !== "string" || b.keys.length > 5000 || !Array.isArray(b.times)) return { ok: false, msg: "記録が壊れています" };

  // 打鍵の記録を打ち直して、スコアを計算し直す
  const ev = TDT.evaluate(mode, sec, TDT.sequence(mode, t.seed), b.keys, b.times);
  if (ev.err) return { ok: false, msg: ev.err };
  const why = plausible_(b.times, ev);
  if (why) return { ok: false, msg: why };

  const cache = CacheService.getScriptCache();
  const lock = LockService.getScriptLock();
  lock.waitLock(10000);
  try {
    const usedKey = "used_" + t.seed + "_" + t.iat;
    if (cache.get(usedKey)) return { ok: false, msg: "この回はもう登録されています" };
    cache.put(usedKey, "1", 21600);

    const sh = sheet_();
    const data = sh.getDataRange().getValues();
    let row = -1;
    for (let i = 1; i < data.length; i++) {
      if (data[i][0] === mode && Number(data[i][1]) === sec && data[i][2] === pid) { row = i; break; }
    }
    const rec = [mode, sec, pid, name, ev.score, Math.round(ev.kpm), Math.round(ev.rkpm),
      Math.round(ev.acc * 1000) / 10, Math.round(ev.lat), ev.ok, ev.miss, new Date()];
    let best = ev.score, improved = true;
    if (row > 0) {
      const old = Number(data[row][4]);
      if (ev.score > old) sh.getRange(row + 1, 1, 1, HEAD.length).setValues([rec]);
      else { improved = false; best = old; sh.getRange(row + 1, 4).setValue(name); }
    } else {
      sh.appendRow(rec);
    }
    cache.remove("top_" + mode + "_" + sec);

    const rows = board_(mode, sec);
    const rank = 1 + rows.filter(r => r.s > best).length;
    return { ok: true, score: ev.score, best: best, improved: improved, rank: rank, total: rows.length };
  } finally {
    lock.releaseLock();
  }
}

/* ---------- 表示 ---------- */
function sheet_() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  let sh = ss.getSheetByName(SHEET_NAME);
  if (!sh) {
    sh = ss.insertSheet(SHEET_NAME);
    sh.getRange(1, 1, 1, HEAD.length).setValues([HEAD]);
    sh.getRange("D:D").setNumberFormat("@");   // 名前はただの文字として扱う
    sh.setFrozenRows(1);
  }
  return sh;
}
function board_(mode, sec) {
  return sheet_().getDataRange().getValues().slice(1)
    .filter(r => r[0] === mode && Number(r[1]) === sec)
    .map(r => ({ p: String(r[2]), n: String(r[3]), s: Number(r[4]), k: Number(r[5]), a: Number(r[7]),
      d: r[11] instanceof Date ? Utilities.formatDate(r[11], "Asia/Tokyo", "yyyy/MM/dd") : "" }))
    .sort((a, b) => b.s - a.s);
}
function top_(p) {
  const mode = String(p.mode), sec = Number(p.sec);
  if (!TDT.POOL[mode] || SECS.indexOf(sec) < 0) return { ok: false, msg: "設定が正しくありません" };
  if (!rate_("top", 600)) return { ok: false, msg: "混み合っています" };
  const cache = CacheService.getScriptCache();
  const ck = "top_" + mode + "_" + sec;
  let rows = null;
  const hit = cache.get(ck);
  if (hit) rows = JSON.parse(hit);
  else {
    rows = board_(mode, sec);
    const js = JSON.stringify(rows);
    if (js.length < 90000) cache.put(ck, js, 60);
  }
  const pid = String(p.pid || "");
  const rankOf = s => 1 + rows.filter(r => r.s > s).length;
  const list = rows.slice(0, TOP_N).map(r => ({ r: rankOf(r.s), n: r.n, s: r.s, k: r.k, a: r.a, d: r.d, me: !!pid && r.p === pid }));
  const mine = pid ? rows.find(r => r.p === pid) : null;
  return { ok: true, list: list, total: rows.length, me: mine ? { r: rankOf(mine.s), s: mine.s } : null };
}
