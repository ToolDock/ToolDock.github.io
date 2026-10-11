"""プロ野球 順位推移グラフ（/standings/ と /standings/<年>/）を作る。

セ・パそれぞれ、6球団の貯金（勝ち数−負け数）の推移を日付ごとに線で描く。
ページを開いたときは最終日（今季は最新の日）までを描いた静止画で、▶を押すと開幕から動き出し、
右の順位表に、その日の順位・成績と「〇連勝」「〇連敗」を出す。

- 試合の結果は npb/data/games_<年>.json（npb/standings_data.py が集める）
- /standings/ は最新の年、/standings/<年>/ はそれより前の年
- 線を描くのは standings/chart.js（このスクリプトが書き出す）。ページにはその年の試合結果を日ごとに埋め込む

    python npb/build_standings.py --data npb/data --out standings
    python npb/build_standings.py --data npb/data --out standings --no-fetch   # 保存済みのデータだけで作る
"""

from __future__ import annotations

import argparse
import html
import json
import sys
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_magic import JST  # noqa: E402
from standings_data import league_of, update  # noqa: E402
from team_colors import CHART_COLORS  # noqa: E402

SITE = "https://tooldock.github.io"
LEAGUES = [("central", "セ・リーグ"), ("pacific", "パ・リーグ")]


def esc(s):
    return html.escape(str(s), quote=True)


# ---------------------------------------------------------------- 集計

def by_day(games):
    """試合 → (日付の一覧, {球団: [その日の結果 "W"/"L"/"T" を並べた文字列, ...]})"""
    days = sorted({g[0] for g in games})
    idx = {d: i for i, d in enumerate(days)}
    res = {}
    for d, home, away, hs, as_ in games:
        for team, mine, theirs in ((home, hs, as_), (away, as_, hs)):
            row = res.setdefault(team, [""] * len(days))
            row[idx[d]] += "W" if mine > theirs else "L" if mine < theirs else "T"
    return days, res


def walk(results):
    """1球団の日ごとの結果 → 日ごとの (勝, 敗, 分, 連勝(+)/連敗(-))。引き分けは連勝・連敗を止めない"""
    w = l = t = streak = 0
    out = []
    for day in results:
        for r in day:
            if r == "W":
                w += 1
                streak = streak + 1 if streak > 0 else 1
            elif r == "L":
                l += 1
                streak = streak - 1 if streak < 0 else -1
            else:
                t += 1
        out.append((w, l, t, streak))
    return out


def pct(w, l):
    return w / (w + l) if w + l else 0.0


def rank_order(rows):
    """[(球団, 勝, 敗, 分)] を順位の順に。勝率、同じなら勝ち数の多い順"""
    return sorted(rows, key=lambda r: (-pct(r[1], r[2]), -r[1]))


def league_table(teams, res, days):
    """リーグの最終順位表と、首位にいた日数・最大連勝・最大連敗"""
    walks = {t: walk(res[t]) for t in teams}
    first_days = {t: 0 for t in teams}
    for i in range(len(days)):
        rows = [(t, *walks[t][i][:3]) for t in teams]
        if any(r[1] + r[2] == 0 for r in rows):
            continue        # まだ全球団がそろって試合をしていない日は数えない
        best = rank_order(rows)[0]
        for t, w, l, _ in rows:
            if pct(w, l) == pct(best[1], best[2]):
                first_days[t] += 1
    table = []
    for t, w, l, tie in rank_order([(t, *walks[t][-1][:3]) for t in teams]):
        streaks = [s[3] for s in walks[t]]
        table.append({"team": t, "w": w, "l": l, "t": tie, "g": w + l + tie,
                      "best": max([0] + streaks), "worst": -min([0] + streaks),
                      "first": first_days[t], "now": walks[t][-1][3]})
    lw, ll = table[0]["w"], table[0]["l"]
    for r in table:
        r["gb"] = ((lw - ll) - (r["w"] - r["l"])) / 2
    return table


# ---------------------------------------------------------------- 表示

def fmt_pct(w, l):
    p = pct(w, l)
    return f"{p:.3f}".lstrip("0") if p < 1 else "1.000"


def fmt_gb(x):
    if x == 0:
        return "-"
    return f"{x:.1f}".rstrip("0").rstrip(".")


def signed(n):
    return f"+{n}" if n > 0 else str(n) if n < 0 else "0"


def streak_text(s):
    return f"{s}連勝" if s >= 2 else f"{-s}連敗" if s <= -2 else ""


def jdate(d):
    y, m, dd = d.split("-")
    return f"{int(m)}月{int(dd)}日"


def panel(table, label):
    """▶を押す前の右の順位表（最終日）。動かしている間は chart.js が書き換える"""
    rows = "".join(
        f'<li><span class="rk">{i}</span><span class="nm"><i style="background:{CHART_COLORS.get(r["team"], ("#888",))[0]}"></i>'
        f'{esc(r["team"])}</span><span class="rec">{r["w"]}勝{r["l"]}敗{r["t"]}分</span>'
        f'<span class="sv">{signed(r["w"] - r["l"])}</span><span class="st">{streak_text(r["now"])}</span></li>'
        for i, r in enumerate(table, 1))
    return f'<ol class="board" aria-label="{esc(label)}の順位">{rows}</ol>'


def final_table(table):
    head = ("<tr><th>順位</th><th class=\"tm\">球団</th><th>試合</th><th>勝</th><th>敗</th><th>分</th><th>勝率</th>"
            "<th>差</th><th>貯金</th><th>最大連勝</th><th>最大連敗</th><th>首位の日数</th></tr>")
    body = "".join(
        f'<tr><td>{i}</td><td class="tm">{esc(r["team"])}</td><td>{r["g"]}</td><td>{r["w"]}</td><td>{r["l"]}</td>'
        f'<td>{r["t"]}</td><td>{fmt_pct(r["w"], r["l"])}</td><td>{fmt_gb(r["gb"])}</td>'
        f'<td>{signed(r["w"] - r["l"])}</td><td>{r["best"]}</td><td>{r["worst"]}</td><td>{r["first"]}日</td></tr>'
        for i, r in enumerate(table, 1))
    return f'<div class="tbl-wrap"><table class="final"><thead>{head}</thead><tbody>{body}</tbody></table></div>'


def years_nav(years, current, latest):
    def href(y):
        return "/standings/" if y == latest else f"/standings/{y}/"
    return '<ul class="years">' + "".join(
        f'<li><span>{y}</span></li>' if y == current else f'<li><a href="{href(y)}">{y}</a></li>'
        for y in sorted(years, reverse=True)) + "</ul>"


def year_page(year, games, years, latest, final):
    days, res = by_day(games)
    data = {"days": days, "lg": {}}
    sections, summary = [], []
    for key, label in LEAGUES:
        teams = [t for t in res if league_of(t) == key]
        table = league_table(teams, res, days)
        data["lg"][key] = [{"n": t["team"], "c": CHART_COLORS.get(t["team"], ("#888", None))[0],
                            "k": CHART_COLORS.get(t["team"], ("#888", None))[1],
                            "r": res[t["team"]]} for t in table]
        summary.append(f"{label}は{table[0]['team']}")
        sections.append(
            f'<section class="lg" id="{key}"><h2>{label}</h2>'
            f'<div class="lg-body"><figure class="chart" data-lg="{key}" aria-label="{year}年 {label}の貯金の推移"></figure>'
            f'{panel(table, label)}</div>'
            f'<h3>{year}年 {label}の{"最終" if final else ""}順位</h3>{final_table(table)}</section>')
    last = jdate(days[-1])
    state = "シーズン終了" if final else f"{last}まで"
    lead = "が1位" if final else "が首位"
    body = (years_nav(years, year, latest)
            + '<div class="player" role="group" aria-label="再生">'
              '<button type="button" class="play" aria-label="開幕から再生">▶</button>'
              f'<output class="day">{esc(last)}</output>'
              f'<input type="range" class="seek" min="0" max="{len(days) - 1}" value="{len(days) - 1}" aria-label="日付">'
              '<span class="speed" role="group" aria-label="速さ">'
              '<button type="button" data-speed="1" aria-pressed="true">×1</button>'
              '<button type="button" data-speed="2">×2</button>'
              '<button type="button" data-speed="4">×4</button></span></div>'
            + "".join(sections)
            + f'<p class="note">・縦軸は貯金（勝ち数−負け数）です。順位は勝率の順で、勝率が同じときは勝ち数の多い順にしています。<br>'
              '・連勝・連敗は、引き分けを挟んでも続けて数えています。<br>'
              f'・{year}年の公式戦{len(games)}試合（{jdate(days[0])}〜{last}）。交流戦も含みます。</p>'
            + f'<script type="application/json" id="standings-data">{json.dumps(data, ensure_ascii=False, separators=(",", ":"))}</script>'
            + '<script src="/standings/chart.js" defer></script>')
    canonical = "/standings/" if year == latest else f"/standings/{year}/"
    title = f"{year}年 プロ野球 順位推移グラフ｜セ・パ12球団の貯金の推移と連勝・連敗"
    desc = (f"{year}年のプロ野球の順位の推移を、セ・パ12球団の貯金（勝ち数−負け数）のグラフで（{state}）。"
            + "、".join(summary) + f"{lead}。▶で開幕からの順位の入れ替わりを動かして見られ、"
            "その日の順位と連勝・連敗も出します。最大連勝・最大連敗・首位にいた日数も球団ごとにまとめています。")
    return page(title, desc, canonical, f"プロ野球 順位推移グラフ {year}",
                f"セ・パ12球団の貯金の推移（{state}）。▶を押すと開幕から動きます", body,
                crumb=None if year == latest else f"{year}年")


def page(title, desc, canonical, h1, sub, body, crumb=None):
    extra = (f'<script> const BREADCRUMB_EXTRA = {{ name: "{esc(crumb)}", url: "{canonical}" }}; </script>\n'
             if crumb else "")
    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">

<!-- npb/build_standings.py が生成する。直接書き換えても、次の自動更新で消える -->
<title>{esc(title)}</title>
<meta name="description" content="{esc(desc)}">
<link rel="canonical" href="{SITE}{canonical}">

<script> const CURRENT_TOOL = "standings"; </script>
{extra}<script src="/js/tool-data.js"></script>
<script src="/js/head.js"></script>
<script src="/js/analytics.js"></script>

<!-- Google AdSense -->
<script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-8349615939902537" crossorigin="anonymous"></script>

<link rel="stylesheet" href="/standings/standings.css">
</head>

<body>
<div class="page-wrapper">
<div class="td-banner"><h1>{esc(h1)}</h1><p>{esc(sub)}</p></div>
<div class="container">
{body}
<footer class="disclaimer">
試合の結果はNPB（日本野球機構）公式サイトの日程・結果をもとに、当サイトが独自に集計したものです。
</footer>
</div>
</div>
</body>
</html>
"""


CSS = """*{ box-sizing:border-box; }
/* 色・文字の大きさは style.css の決まりを使う */
body{ max-width:none; margin:0; padding:0 0 48px; background:var(--bg); color:var(--ink); line-height:1.7;
      font-family:"Noto Sans JP","Hiragino Kaku Gothic ProN","Hiragino Sans",Meiryo,sans-serif; }
.page-wrapper{ max-width:1100px; margin:0; padding:0 20px; }
body .td-rail-inline{ max-width:1100px; margin:40px 0 0; padding:0 20px; }
h2{ margin:34px 0 12px; padding-bottom:8px; font-size:var(--fs-h2); border-bottom:2px solid var(--c); }
h3{ margin:20px 0 8px; font-size:var(--fs-h3); }
ul.years{ list-style:none; display:flex; flex-wrap:wrap; gap:6px; margin:0 0 14px; padding:0; }
ul.years a, ul.years span{ display:inline-block; padding:4px 12px; border:1px solid var(--line); background:var(--surface);
    text-decoration:none; font-size:var(--fs-m); color:var(--ink); font-variant-numeric:tabular-nums; }
ul.years span{ background:var(--ink); color:#fff; border-color:var(--ink); }

/* 再生の操作。動かしている間も手が届くよう、画面の上に貼りつける */
.player{ position:sticky; top:0; z-index:3; display:flex; align-items:center; gap:12px; flex-wrap:wrap;
    padding:10px 12px; background:var(--surface); border:1px solid var(--line); margin:0 0 4px; }
.player .play{ width:44px; height:44px; border:0; border-radius:var(--r-ctl); background:var(--ink); color:#fff;
    font-size:18px; line-height:1; cursor:pointer; }
.player .play:hover{ background:#000; }
.player .day{ min-width:6.5em; font-size:var(--fs-h3); font-weight:800; font-variant-numeric:tabular-nums; }
.player .seek{ flex:1 1 200px; accent-color:var(--ink); }
.player .speed{ display:flex; gap:4px; }
.player .speed button{ padding:4px 9px; border:1px solid var(--line-input); border-radius:var(--r-ctl); background:var(--surface);
    color:var(--ink); font:inherit; font-size:var(--fs-s); font-weight:700; cursor:pointer; }
.player .speed button[aria-pressed="true"]{ background:var(--ink); border-color:var(--ink); color:#fff; }

/* グラフと、右の順位表 */
.lg-body{ display:grid; grid-template-columns:minmax(0, 1fr) 260px; gap:8px; align-items:start; }
.chart{ margin:0; background:var(--surface); border:1px solid var(--line); aspect-ratio:5 / 3; overflow:hidden; }
.chart svg{ display:block; width:100%; height:auto; font-family:inherit; }
ol.board{ list-style:none; margin:0; padding:0; background:var(--surface); border:1px solid var(--line); }
ol.board li{ display:grid; grid-template-columns:1.4em 1fr auto; grid-template-areas:"rk nm sv" "rk rec st";
    column-gap:6px; padding:8px 10px; border-bottom:1px solid var(--line-soft); font-variant-numeric:tabular-nums; }
ol.board li:last-child{ border-bottom:0; }
ol.board .rk{ grid-area:rk; font-weight:800; font-size:var(--fs-b); }
ol.board .nm{ grid-area:nm; font-weight:800; display:flex; align-items:center; gap:6px; }
ol.board .nm i{ width:10px; height:10px; flex:none; }
ol.board .rec{ grid-area:rec; font-size:var(--fs-s); }
ol.board .sv{ grid-area:sv; font-weight:800; text-align:right; }
ol.board .st{ grid-area:st; font-size:var(--fs-s); font-weight:700; text-align:right; }
ol.board .st.hot{ color:#fff; background:var(--hot, var(--ink)); padding:0 6px; }

.tbl-wrap{ overflow-x:auto; -webkit-overflow-scrolling:touch; background:var(--surface); border:1px solid var(--line); }
table.final{ border-collapse:collapse; width:100%; font-size:var(--fs-s); font-variant-numeric:tabular-nums; }
table.final th, table.final td{ padding:7px 8px; border-bottom:1px solid var(--line-soft); text-align:right; white-space:nowrap; }
table.final thead th{ background:var(--surface-2); font-size:var(--fs-xs); }
table.final .tm{ text-align:left; font-weight:700; }
.note{ margin-top:18px; font-size:var(--fs-s); }
footer.disclaimer{ margin-top:22px; font-size:var(--fs-s); }
@media (max-width:760px){
    .lg-body{ grid-template-columns:1fr; }
    .chart{ aspect-ratio:1 / 0.95; }
    ol.board{ display:grid; grid-template-columns:1fr 1fr; }
    ol.board li{ border-right:1px solid var(--line-soft); }
    .player{ gap:8px; }
    .player .seek{ order:5; flex-basis:100%; }
}
"""


CHART_JS = r"""// 順位推移グラフ（npb/build_standings.py が書き出す）。
// ページに埋め込んだ日ごとの試合結果から、球団ごとの貯金の線を描き、▶で開幕から動かす
(function () {
  "use strict";
  var NS = "http://www.w3.org/2000/svg";
  var data = JSON.parse(document.getElementById("standings-data").textContent);
  var days = data.days, D = days.length;

  function el(tag, attrs, text) {
    var e = document.createElementNS(NS, tag);
    for (var k in attrs) e.setAttribute(k, attrs[k]);
    if (text != null) e.textContent = text;
    return e;
  }

  // 球団ごとに、日ごとの 勝・敗・分・連勝(+)/連敗(-) を積み上げる（引き分けは連勝・連敗を止めない）
  function walk(results) {
    var w = 0, l = 0, t = 0, s = 0, out = [];
    results.forEach(function (day) {
      for (var i = 0; i < day.length; i++) {
        var r = day[i];
        if (r === "W") { w++; s = s > 0 ? s + 1 : 1; }
        else if (r === "L") { l++; s = s < 0 ? s - 1 : -1; }
        else t++;
      }
      out.push([w, l, t, s]);
    });
    return out;
  }
  function pct(w, l) { return w + l ? w / (w + l) : 0; }
  function signed(n) { return n > 0 ? "+" + n : String(n); }
  function streakText(s) { return s >= 2 ? s + "連勝" : s <= -2 ? (-s) + "連敗" : ""; }
  function jdate(d) { var p = d.split("-"); return (+p[1]) + "月" + (+p[2]) + "日"; }

  // 描く大きさは、表示される幅に合わせる（1単位＝1px。スマホでも文字が小さくならない）。
  // 縦横の比は standings.css の .chart の aspect-ratio と同じにする
  var charts = [];
  var teamsByLg = {};
  Object.keys(data.lg).forEach(function (key) {
    teamsByLg[key] = data.lg[key].map(function (t) {
      var v = walk(t.r), first = 0;
      while (first < D - 1 && v[first][0] + v[first][1] + v[first][2] === 0) first++;
      // 線は開幕の前の日（貯金0）から引く。リーグによって開幕の日が違う年がある
      return { n: t.n, c: t.c, k: t.k, v: v, start: Math.max(0, first - 1) };
    });
  });

  function build() {
    charts = [];
    Object.keys(data.lg).forEach(function (key) {
      var fig = document.querySelector('.chart[data-lg="' + key + '"]');
      if (!fig) return;
      var board = fig.parentNode.querySelector("ol.board");
      var teams = teamsByLg[key];
      var W = Math.max(280, Math.round(fig.clientWidth || 720));
      var narrow = W < 560;
      var H = Math.round(W * (narrow ? 0.95 : 0.6));
      var fs = narrow ? 11 : 12;
      var L = 36, R = narrow ? 92 : 118, T = 12, B = 26;
      var lo = 0, hi = 0;
      teams.forEach(function (t) { t.v.forEach(function (x) { lo = Math.min(lo, x[0] - x[1]); hi = Math.max(hi, x[0] - x[1]); }); });
      var step = (hi - lo) > 40 ? 10 : 5;
      lo = Math.floor(lo / step) * step; hi = Math.ceil(hi / step) * step;
      if (hi === lo) hi = lo + step;
      function X(i) { return L + (D > 1 ? i / (D - 1) : 0) * (W - L - R); }
      function Y(v) { return T + (hi - v) / (hi - lo) * (H - T - B); }

      var svg = el("svg", { viewBox: "0 0 " + W + " " + H, width: W, height: H, role: "img", "aria-label": fig.getAttribute("aria-label") });
      // 目盛り：貯金と、月の頭（月の名前は、次の月と近すぎるときは出さない）
      for (var v = lo; v <= hi; v += step) {
        svg.appendChild(el("line", { x1: L, x2: W - R, y1: Y(v), y2: Y(v), stroke: v === 0 ? "#1c1d1f" : "#e6e4de", "stroke-width": v === 0 ? 1.2 : 1 }));
        svg.appendChild(el("text", { x: L - 5, y: Y(v) + 4, "text-anchor": "end", "font-size": fs - 1, fill: "#1c1d1f" }, v > 0 ? "+" + v : String(v)));
      }
      var months = [];
      days.forEach(function (d, i) { var m = d.slice(5, 7); if (!months.length || months[months.length - 1].m !== m) months.push({ m: m, i: i }); });
      months.forEach(function (mo, n) {
        svg.appendChild(el("line", { x1: X(mo.i), x2: X(mo.i), y1: T, y2: H - B, stroke: "#e6e4de" }));
        var next = months[n + 1];
        if (next && X(next.i) - X(mo.i) < (narrow ? 26 : 30)) return;
        svg.appendChild(el("text", { x: X(mo.i) + 3, y: H - B + 16, "font-size": fs - 1, fill: "#1c1d1f" }, (+mo.m) + "月"));
      });
      var lines = el("g", {}), labels = el("g", {});
      svg.appendChild(lines); svg.appendChild(labels);
      var parts = teams.map(function (t) {
        var p = { t: t };
        if (t.k) { p.casing = el("polyline", { fill: "none", stroke: t.k, "stroke-width": 4.6, "stroke-linejoin": "round", "stroke-linecap": "round" }); lines.appendChild(p.casing); }
        p.line = el("polyline", { fill: "none", stroke: t.c, "stroke-width": t.k ? 2.4 : 2.6, "stroke-linejoin": "round", "stroke-linecap": "round" });
        lines.appendChild(p.line);
        p.dot = el("circle", { r: 4, fill: t.c, stroke: t.k || "#fff", "stroke-width": 1.5 });
        p.label = el("text", { "font-size": fs, "font-weight": 700, fill: "#1c1d1f" });
        lines.appendChild(p.dot); labels.appendChild(p.label);
        return p;
      });
      fig.textContent = "";
      fig.appendChild(svg);
      charts.push({ parts: parts, teams: teams, board: board, X: X, Y: Y, gap: fs + 1 });
    });
  }

  // k（0〜D-1、小数もあり）の日までを描く
  function draw(k) {
    var i = Math.floor(k), f = k - i;
    charts.forEach(function (c) {
      var ends = [];
      c.parts.forEach(function (p) {
        var t = p.t, pts = [];
        var shown = i >= t.start;
        p.line.style.display = p.dot.style.display = p.label.style.display = shown ? "" : "none";
        if (p.casing) p.casing.style.display = shown ? "" : "none";
        for (var j = t.start; j <= i; j++) pts.push(c.X(j).toFixed(1) + "," + c.Y(t.v[j][0] - t.v[j][1]).toFixed(1));
        var ex = c.X(i), ey = c.Y(t.v[i][0] - t.v[i][1]);
        if (f > 0 && i + 1 < D) {
          var nv = t.v[i + 1][0] - t.v[i + 1][1], cv = t.v[i][0] - t.v[i][1];
          ex = c.X(i + f); ey = c.Y(cv + (nv - cv) * f);
          pts.push(ex.toFixed(1) + "," + ey.toFixed(1));
        }
        p.line.setAttribute("points", pts.join(" "));
        if (p.casing) p.casing.setAttribute("points", pts.join(" "));
        p.dot.setAttribute("cx", ex); p.dot.setAttribute("cy", ey);
        var cur = t.v[i];
        p.label.textContent = t.n + " " + signed(cur[0] - cur[1]);
        if (shown) ends.push({ p: p, x: ex, y: ey });
      });
      // 名前が重ならないよう、上から順に文字の高さぶんずつ離す
      ends.sort(function (a, b) { return a.y - b.y; });
      var prev = -1e9;
      ends.forEach(function (e) { var y = Math.max(e.y + 4, prev + c.gap); prev = y; e.p.label.setAttribute("x", e.x + 8); e.p.label.setAttribute("y", y); });
      drawBoard(c, i);
    });
    dayOut.textContent = jdate(days[i]);
    seek.value = i;
  }

  function drawBoard(c, i) {
    if (!c.board) return;
    var rows = c.teams.map(function (t) { var v = t.v[i]; return { t: t, w: v[0], l: v[1], d: v[2], s: v[3] }; });
    rows.sort(function (a, b) { return pct(b.w, b.l) - pct(a.w, a.l) || b.w - a.w; });
    c.board.textContent = "";
    rows.forEach(function (r, n) {
      var li = document.createElement("li");
      var st = streakText(r.s);
      li.innerHTML = '<span class="rk">' + (n + 1) + '</span><span class="nm"><i></i></span><span class="rec"></span>' +
        '<span class="sv"></span><span class="st"></span>';
      li.querySelector(".nm i").style.background = r.t.c;
      li.querySelector(".nm").appendChild(document.createTextNode(r.t.n));
      li.querySelector(".rec").textContent = r.w + "勝" + r.l + "敗" + r.d + "分";
      li.querySelector(".sv").textContent = signed(r.w - r.l);
      var stEl = li.querySelector(".st");
      stEl.textContent = st;
      // 5連勝・5連敗からは目立たせる
      if (Math.abs(r.s) >= 5) { stEl.classList.add("hot"); stEl.style.setProperty("--hot", r.s > 0 ? "#c62828" : "#1c1d1f"); }
      c.board.appendChild(li);
    });
  }

  // 再生
  var bar = document.querySelector(".player");
  var playBtn = bar.querySelector(".play"), dayOut = bar.querySelector(".day"), seek = bar.querySelector(".seek");
  var speed = 1, k = D - 1, playing = false, last = 0;
  var SECONDS = 30;     // ×1 で開幕から最終日まで30秒

  function tick(ts) {
    if (!playing) return;
    if (last) k = Math.min(D - 1, k + (ts - last) / 1000 * (D - 1) / SECONDS * speed);
    last = ts;
    draw(k);
    if (k >= D - 1) { stop(); return; }
    requestAnimationFrame(tick);
  }
  function play() {
    if (k >= D - 1) k = 0;
    playing = true; last = 0;
    playBtn.textContent = "❚❚"; playBtn.setAttribute("aria-label", "一時停止");
    requestAnimationFrame(tick);
  }
  function stop() {
    playing = false;
    playBtn.textContent = "▶"; playBtn.setAttribute("aria-label", "開幕から再生");
  }
  playBtn.addEventListener("click", function () { playing ? stop() : play(); });
  seek.addEventListener("input", function () { stop(); k = +seek.value; draw(k); });
  bar.querySelectorAll(".speed button").forEach(function (b) {
    b.addEventListener("click", function () {
      speed = +b.dataset.speed;
      bar.querySelectorAll(".speed button").forEach(function (x) { x.setAttribute("aria-pressed", x === b ? "true" : "false"); });
    });
  });

  build();
  draw(k);
  // 幅が変わったら描き直す（画面の回転など）
  var lastW = window.innerWidth, timer = null;
  window.addEventListener("resize", function () {
    if (window.innerWidth === lastW) return;
    lastW = window.innerWidth;
    clearTimeout(timer);
    timer = setTimeout(function () { build(); draw(k); }, 150);
  });
})();
"""


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--no-fetch", action="store_true")
    args = ap.parse_args(argv)

    data = Path(args.data)
    out = Path(args.out)
    seasons = sorted(int(p.stem.split("_")[1]) for p in data.glob("season_*.json"))
    current = seasons[-1] if seasons else datetime.now(JST).year
    games = update(data, current, fetch_ok=not args.no_fetch)
    years = sorted(y for y, g in games.items() if g)
    if not years:
        print("standings: 試合のデータが無い", file=sys.stderr)
        return 1
    latest = years[-1]
    out.mkdir(parents=True, exist_ok=True)
    (out / "standings.css").write_text(CSS, encoding="utf-8")
    (out / "chart.js").write_text(CHART_JS, encoding="utf-8")
    for y in years:
        st_path = data / f"season_{y}.json"
        final = bool(json.loads(st_path.read_text(encoding="utf-8")).get("final")) if st_path.exists() else True
        target = out / "index.html" if y == latest else out / str(y) / "index.html"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(year_page(y, games[y], years, latest, final), encoding="utf-8")
    stale = out / str(latest) / "index.html"     # 最新の年は /standings/ に出すので、年のページは作らない
    if stale.exists():
        stale.unlink()
        stale.parent.rmdir()
    print(f"standings: {years[0]}〜{latest}年")
    return 0


if __name__ == "__main__":
    sys.exit(main())
