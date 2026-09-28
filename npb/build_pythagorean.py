"""プロ野球 ピタゴラス勝率ランキング（/pythagorean/）を作る。

得点と失点から「実力どおりなら何勝か」（ピタゴラス勝率 × 勝敗の数）を計算し、
実際の勝ち数との差を「運」として球団ごとに並べる。

球団の成績は npb/data/season_<年>.json（個人成績）を球団ごとに足して出す。
  得点 = 打者の得点の合計、失点 = 投手の失点の合計、
  勝敗 = 投手の勝利・敗戦の合計（勝ち負けは必ずどれか1人の投手に付く）、
  引き分け = 試合数 − 勝 − 敗
これで順位表の勝敗と一致する（2025年 ソフトバンク87勝52敗4分 など）。

    python npb/build_pythagorean.py --data npb/data --out pythagorean
"""

from __future__ import annotations

import argparse
import html
import json
import math
import statistics
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

JST = timezone(timedelta(hours=9))

# ピタゴラス勝率の指数。2005〜2025年のNPBで、指数2（ビル・ジェームズの元の式）より実際の勝ち数に近い。
# 年ごとに指数を変える PythagenPat ともほぼ同じ精度（ずれの大きさ：2→4.3勝、1.83→4.0勝、PythagenPat→4.0勝）
EXP = 1.83

# グラフの目盛り（勝）。年どうしで比べられるよう、どの年も同じ幅にする
SCALE = 12

LEAGUES = [("central", "セ・リーグ"), ("pacific", "パ・リーグ")]
TEAM_ORDER = ["巨人", "阪神", "DeNA", "横浜", "広島", "中日", "ヤクルト",
              "ソフトバンク", "日本ハム", "ロッテ", "西武", "楽天", "オリックス"]


def esc(s):
    return html.escape(str(s), quote=True)


def pyth(rs, ra, exp=EXP):
    if rs + ra == 0:
        return 0.5
    return rs ** exp / (rs ** exp + ra ** exp)


def team_season(st):
    """season_<年>.json → [{name, lg, g, w, l, t, rs, ra, pct, pyth, exp_w, luck}]"""
    bc = {c: i for i, c in enumerate(st["bat_cols"])}
    pc = {c: i for i, c in enumerate(st["pit_cols"])}
    tm = defaultdict(lambda: {"rs": 0, "ra": 0, "w": 0, "l": 0})
    for r in st["bat"]:
        tm[r[bc["team"]]]["rs"] += r[bc["得点"]]
    for r in st["pit"]:
        t = tm[r[pc["team"]]]
        t["ra"] += r[pc["失点"]]
        t["w"] += r[pc["勝利"]]
        t["l"] += r[pc["敗北"]]
    out = []
    for code, t in tm.items():
        info = st["teams"][code]
        n = t["w"] + t["l"]
        if n == 0:
            continue
        p = pyth(t["rs"], t["ra"])
        out.append({
            "name": info["name"], "lg": info["league"], "g": info["games"],
            "w": t["w"], "l": t["l"], "t": max(0, info["games"] - n),
            "rs": t["rs"], "ra": t["ra"], "pct": t["w"] / n, "pyth": p,
            "exp_w": p * n, "luck": t["w"] - p * n,
        })
    return out


def franchise(name):
    return "DeNA" if name in ("横浜", "DeNA") else name


def facts(seasons):
    """完了したシーズンから、運についての事実を計算する"""
    done = {y: s for y, s in seasons.items() if s["final"]}
    ys = sorted(done)
    luck_now, luck_next, pct_now, pyth_now, pct_next = [], [], [], [], []
    lucky, lucky_drop = 0, 0
    for y in ys:
        if y + 1 not in done:
            continue
        a = {franchise(t["name"]): t for t in done[y]["teams"]}
        b = {franchise(t["name"]): t for t in done[y + 1]["teams"]}
        for n in a:
            if n not in b:
                continue
            luck_now.append(a[n]["luck"])
            luck_next.append(b[n]["luck"])
            pct_now.append(a[n]["pct"])
            pyth_now.append(a[n]["pyth"])
            pct_next.append(b[n]["pct"])
            if a[n]["luck"] >= 4:
                lucky += 1
                lucky_drop += b[n]["pct"] < a[n]["pct"]
    errs = [t["luck"] for y in ys for t in done[y]["teams"]]
    return {
        "first": ys[0], "last": ys[-1],
        "rmse": math.sqrt(sum(e * e for e in errs) / len(errs)),
        "luck_corr": statistics.correlation(luck_now, luck_next),
        "pct_corr": statistics.correlation(pct_now, pct_next),
        "pyth_corr": statistics.correlation(pyth_now, pct_next),
        "lucky": lucky, "lucky_drop": lucky_drop,
    }


def signed(x, d=1):
    s = f"{x:+.{d}f}"
    if float(s) == 0:
        return "±" + s[1:]
    return s.replace("-", "−")


def fmt_pct(x):
    return f"{x:.3f}"[1:] if x < 1 else f"{x:.3f}"


def bar_chart(teams, lg_label, year):
    """運の横棒グラフ（中央が0、右が青＝運が良い、左が赤＝運が悪い）。値は棒の先に直接書く"""
    rows = []
    for t in sorted(teams, key=lambda t: -t["luck"]):
        v = max(-SCALE, min(SCALE, t["luck"]))
        w = abs(v) / SCALE * 50
        side = "pos" if t["luck"] >= 0 else "neg"
        tip = (f'{t["name"]}：実際 {t["w"]}勝{t["l"]}敗 ／ 得失点からの見込み {t["exp_w"]:.1f}勝 ／ '
               f'運 {signed(t["luck"])}勝')
        rows.append(
            f'<div class="bar-row" data-tip="{esc(tip)}" tabindex="0">'
            f'<span class="bar-name">{esc(t["name"])}</span>'
            f'<span class="bar-track"><span class="bar {side}" style="width:{w:.1f}%"></span></span>'
            f'<span class="bar-val">{signed(t["luck"])}</span></div>')
    return (f'<figure class="chart" aria-label="{year}年 {lg_label}の運（実際の勝ち数 − 得失点からの見込み）">'
            f'<div class="chart-axis"><span>運が悪い</span><span>0</span><span>運が良い</span></div>'
            + "".join(rows) +
            f'<figcaption>棒の長さ：実際の勝ち数 − 得失点から見込まれる勝ち数（目盛りは±{SCALE}勝）</figcaption></figure>')


def league_table(teams):
    teams = sorted(teams, key=lambda t: (-t["pct"], -t["w"]))
    rows = []
    for i, t in enumerate(teams, 1):
        rows.append(
            f'<tr><td class="rk">{i}</td><th class="tm">{esc(t["name"])}</th>'
            f'<td class="opt">{t["g"]}</td><td>{t["w"]}</td><td>{t["l"]}</td><td class="opt">{t["t"]}</td>'
            f'<td class="pct">{fmt_pct(t["pct"])}</td>'
            f'<td class="opt">{t["rs"]}</td><td class="opt">{t["ra"]}</td>'
            f'<td>{signed(t["rs"] - t["ra"], 0)}</td>'
            f'<td class="opt">{fmt_pct(t["pyth"])}</td><td>{t["exp_w"]:.1f}</td>'
            f'<td class="luck">{signed(t["luck"])}</td></tr>')
    return ('<div class="tbl-wrap"><table class="std"><thead><tr>'
            '<th>順位</th><th class="tm">球団</th><th class="opt">試合</th><th>勝</th><th>敗</th><th class="opt">分</th>'
            '<th>勝率</th><th class="opt">得点</th><th class="opt">失点</th><th>得失点差</th>'
            '<th class="opt">ピタゴラス<br>勝率</th><th>見込み<br>勝数</th><th>運<br>（勝）</th>'
            '</tr></thead><tbody>' + "".join(rows) + "</tbody></table></div>")


def headline(teams):
    best = max(teams, key=lambda t: t["luck"])
    worst = min(teams, key=lambda t: t["luck"])
    return (f'最も運が良いのは<strong>{esc(best["name"])}</strong>（{signed(best["luck"])}勝）、'
            f'最も運が悪いのは<strong>{esc(worst["name"])}</strong>（{signed(worst["luck"])}勝）')


def season_block(year, s, latest):
    parts = []
    status = "シーズン途中" if not s["final"] else "シーズン終了"
    for key, label in LEAGUES:
        teams = [t for t in s["teams"] if t["lg"] == key]
        if not teams:
            continue
        parts.append(
            f'<section class="league league-{key}"><h2>{year}年 {label}</h2>'
            f'<p class="hl">{headline(teams)}</p>'
            f'{bar_chart(teams, label, year)}{league_table(teams)}</section>')
    hidden = "" if year == latest else " hidden"
    return (f'<div class="season" data-year="{year}"{hidden}>'
            f'<p class="stamp"><span>{year}年：<strong>{status}</strong>'
            + (f'（{esc(s["as_of_text"])}時点）' if not s["final"] else "") +
            '</span></p>' + "".join(parts) + "</div>")


def history(seasons, n=10):
    rows = [(y, t) for y, s in seasons.items() if s["final"] for t in s["teams"]]

    def table(items):
        body = "".join(
            f'<tr><td class="rk">{i}</td><td>{y}</td><th class="tm">{esc(t["name"])}</th>'
            f'<td>{t["w"]}勝{t["l"]}敗{t["t"]}分</td><td>{fmt_pct(t["pct"])}</td>'
            f'<td>{signed(t["rs"] - t["ra"], 0)}</td><td>{t["exp_w"]:.1f}</td>'
            f'<td class="luck">{signed(t["luck"])}</td></tr>'
            for i, (y, t) in enumerate(items, 1))
        return ('<div class="box"><div class="tbl-wrap"><table class="std"><thead><tr><th>順位</th><th>年</th><th class="tm">球団</th>'
                '<th>成績</th><th>勝率</th><th>得失点差</th><th>見込み<br>勝数</th><th>運<br>（勝）</th>'
                '</tr></thead><tbody>' + body + "</tbody></table></div></div>")

    lucky = sorted(rows, key=lambda x: -x[1]["luck"])[:n]
    unlucky = sorted(rows, key=lambda x: x[1]["luck"])[:n]
    return lucky, unlucky, table(lucky), table(unlucky)


def render(seasons, latest, template):
    f = facts(seasons)
    lucky, unlucky, lucky_tbl, unlucky_tbl = history(seasons)
    s = seasons[latest]
    lines = []
    for key, label in LEAGUES:
        teams = [t for t in s["teams"] if t["lg"] == key]
        best = max(teams, key=lambda t: t["luck"])
        worst = min(teams, key=lambda t: t["luck"])
        lines.append(f'{label}は{best["name"]}（{signed(best["luck"])}勝）が最も運が良く、'
                     f'{worst["name"]}（{signed(worst["luck"])}勝）が最も運が悪い')
    ly, lt = lucky[0]
    uy, ut = unlucky[0]
    desc = (f"得点と失点から計算するピタゴラス勝率で、プロ野球12球団の「実力どおりなら何勝か」と実際の勝ち数の差（運）を"
            f"毎日更新。{latest}年は" + "。".join(lines) + "。"
            f"{f['first']}年以降の歴代の運ランキングと、ピタゴラス勝率の計算機もあります。")
    options = "".join(f'<option value="{y}"{" selected" if y == latest else ""}>{y}年{"（途中）" if not seasons[y]["final"] else ""}</option>'
                      for y in sorted(seasons, reverse=True))
    blocks = "".join(season_block(y, seasons[y], latest) for y in sorted(seasons, reverse=True))
    now = datetime.now(JST)
    rep = {
        "{{DESCRIPTION}}": esc(desc),
        "{{YEAR}}": str(latest),
        "{{AS_OF}}": esc(s["as_of_text"] + ("（シーズン終了）" if s["final"] else "終了時点")),
        "{{UPDATED}}": f"{now.year}年{now.month}月{now.day}日 {now.hour}:{now.minute:02d}",
        "{{OPTIONS}}": options,
        "{{SEASONS}}": blocks,
        "{{LUCKY}}": lucky_tbl,
        "{{UNLUCKY}}": unlucky_tbl,
        "{{LUCKIEST}}": f'{ly}年の{esc(lt["name"])}（{lt["w"]}勝{lt["l"]}敗{lt["t"]}分、運 {signed(lt["luck"])}勝）',
        "{{UNLUCKIEST}}": f'{uy}年の{esc(ut["name"])}（{ut["w"]}勝{ut["l"]}敗{ut["t"]}分、運 {signed(ut["luck"])}勝）',
        "{{FIRST}}": str(f["first"]),
        "{{LAST}}": str(f["last"]),
        "{{RMSE}}": f"{f['rmse']:.1f}",
        "{{LUCK_CORR}}": f"{f['luck_corr']:.2f}",
        "{{PCT_CORR}}": f"{f['pct_corr']:.2f}",
        "{{PYTH_CORR}}": f"{f['pyth_corr']:.2f}",
        "{{LUCKY_N}}": str(f["lucky"]),
        "{{LUCKY_DROP}}": str(f["lucky_drop"]),
        "{{LUCKY_DROP_PCT}}": str(round(f["lucky_drop"] * 100 / max(1, f["lucky"]))),
        "{{EXP}}": str(EXP),
    }
    page = template
    for k, v in rep.items():
        page = page.replace(k, v)
    return page


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args(argv)

    seasons = {}
    for f in sorted(Path(args.data).glob("season_*.json")):
        st = json.loads(f.read_text(encoding="utf-8"))
        teams = team_season(st)
        if len(teams) < 12:
            continue
        as_of = st.get("as_of") or ""
        try:
            d = datetime.strptime(as_of, "%Y-%m-%d")
            as_of_text = f"{d.year}年{d.month}月{d.day}日"
        except ValueError:
            as_of_text = f"{st['year']}年"
        seasons[st["year"]] = {"teams": teams, "final": bool(st.get("final")), "as_of_text": as_of_text}
    latest = max(seasons)

    template = (Path(__file__).resolve().parent / "template_pythagorean.html").read_text(encoding="utf-8")
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "index.html").write_text(render(seasons, latest, template), encoding="utf-8")
    print(f"pythagorean: {min(seasons)}〜{latest}年")
    return 0


if __name__ == "__main__":
    sys.exit(main())
