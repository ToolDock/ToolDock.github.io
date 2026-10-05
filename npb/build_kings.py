"""プロ野球 いろんな「王」ランキング（/kings/ と /kings/<年>/）を作る。

タイトルになる部門（首位打者・本塁打王…）だけでなく、得点・二塁打・三振・併殺打・犠打・死球・失策・
守備機会など、ふだん順位が出ない部門も含めて、年ごと・リーグごとに上位5人を並べる。

- 成績は npb/data/season_<年>.json（NPB公式の個人成績）。リーグの中で移籍した選手は合計する
- 盗塁阻止率はNPB公式の守備部門のページの上位3人（season_<年>.json の leaders）
- 選手名は、選手ページ（/player/）がある選手だけリンクにする

    python npb/build_kings.py --data npb/data --out kings
"""

from __future__ import annotations

import argparse
import html
import json
import math
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_saber import season_rows  # noqa: E402
from people import People  # noqa: E402

JST = timezone(timedelta(hours=9))
SITE = "https://tooldock.github.io"
TOP = 5               # 各部門で出す人数（同じ値で並んだ人は含める）
MAX_ROWS = 8          # 同じ値が多くても、ここまでで打ち切って「ほか○人」とする
LEAGUES = [("central", "セ・リーグ"), ("pacific", "パ・リーグ")]
FULL_SEASON = 143

# (キー, 部門名, 単位, 表示の形 "int"/"ip")
BAT = [
    ("試合", "出場試合数", "試合", "int"), ("打席", "打席数", "打席", "int"), ("得点", "得点王", "得点", "int"),
    ("安打", "最多安打", "本", "int"), ("二塁打", "二塁打王", "本", "int"), ("三塁打", "三塁打王", "本", "int"),
    ("本塁打", "本塁打王", "本", "int"), ("塁打", "塁打王", "塁打", "int"), ("打点", "打点王", "打点", "int"),
    ("盗塁", "盗塁王", "盗塁", "int"), ("盗塁刺", "盗塁死王（盗塁失敗）", "回", "int"), ("犠打", "犠打王", "犠打", "int"),
    ("犠飛", "犠飛王", "犠飛", "int"), ("四球", "四球王", "個", "int"), ("故意四", "敬遠王（故意四球）", "個", "int"),
    ("死球", "死球王", "個", "int"), ("三振", "三振王", "三振", "int"), ("併殺打", "併殺打王", "本", "int"),
]
BAT_RATES = [("打率", "首位打者（打率）"), ("出塁率", "最高出塁率"), ("長打率", "長打率"), ("OPS", "OPS")]
PIT = [
    ("登板", "登板王", "登板", "int"), ("勝利", "最多勝利", "勝", "int"), ("敗北", "敗戦王", "敗", "int"),
    ("セーブ", "最多セーブ", "S", "int"), ("ホールド", "ホールド王", "H", "int"), ("完投", "完投王", "完投", "int"),
    ("完封勝", "完封王", "完封", "int"), ("無四球", "無四球王", "試合", "int"), ("outs", "投球回", "回", "ip"),
    ("三振", "最多奪三振", "個", "int"), ("四球", "与四球王", "個", "int"), ("死球", "与死球王", "個", "int"),
    ("本塁打", "被本塁打王", "本", "int"), ("安打", "被安打王", "本", "int"), ("暴投", "暴投王", "個", "int"),
    ("ボーク", "ボーク王", "個", "int"), ("失点", "失点王", "点", "int"), ("自責点", "自責点王", "点", "int"),
]
PIT_RATES = [("防御率", "最優秀防御率", "asc"), ("WHIP", "WHIP", "asc"), ("K9", "奪三振率", "desc"), ("勝率", "最高勝率", "desc")]
FLD = [  # (守備位置, 項目, 部門名)
    ("一塁手", "機会", "守備機会王（一塁手）"), ("二塁手", "機会", "守備機会王（二塁手）"), ("三塁手", "機会", "守備機会王（三塁手）"),
    ("遊撃手", "機会", "守備機会王（遊撃手）"), ("外野手", "機会", "守備機会王（外野手）"), ("捕手", "機会", "守備機会王（捕手）"),
    ("外野手", "刺殺", "刺殺王（外野手）"), ("外野手", "補殺", "補殺王（外野手）"),
    ("二塁手", "併殺", "併殺王（二塁手）"), ("遊撃手", "併殺", "併殺王（遊撃手）"),
    (None, "失策", "失策王（全守備位置）"), ("捕手", "捕逸", "捕逸王"),
]


# なんJで昔から「ネタだが優秀」と言われてきた指標
# (部門名, 打撃/投手, 計算, 表示の形, 単位, 規定打席の条件を付けるか, 説明)
NETA = [
    ("小松式ドネーション", "pit", lambda e: e["outs"] + 10 * (e["勝利"] + e["ホールド"] + e["セーブ"]), "int", "", False,
     "投球回×3＋（勝利＋ホールド＋セーブ）×10。先発・中継ぎ・抑えを問わない、投手のチームへの貢献度"),
    ("アダム・ダン率", "bat", lambda e: (e["本塁打"] + e["四球"] + e["三振"]) / e["打席"] if e["打席"] else None, "rate3", "",
     True, "（本塁打＋四球＋三振）÷打席・規定打席以上。高いほど良いのではなく「アダム・ダンらしさ」（本家の通算は約5割）"),
    ("赤星式盗塁", "bat", lambda e: e["盗塁"] - 2 * e["盗塁刺"], "int", "", False,
     "盗塁−盗塁死×2。盗塁死の痛さを成功の2倍とみた、盗塁によるチームへの貢献度"),
]


def esc(s):
    return html.escape(str(s), quote=True)


def disp(name):
    return name.replace("　", " ")


def fmt(v, kind):
    if kind == "int":
        return f"{v}"
    if kind == "ip":
        return f"{v // 3}" + (f" {v % 3}/3" if v % 3 else "")
    if kind == "rate3":
        s = f"{v:.3f}"
        return s[1:] if s.startswith("0") else s
    return f"{v:.2f}"


def season_players(st, links):
    """→ {リーグ: {"bat": {名前: 合計}, "pit": {...}, "fld": {...}}}。リーグの中の移籍は合計する"""
    teams = st["teams"]
    bc = {c: i for i, c in enumerate(st["bat_cols"])}
    pc = {c: i for i, c in enumerate(st["pit_cols"])}
    fc = {c: i for i, c in enumerate(st.get("fld_cols", ["team", "name", "pos", "試合"]))}
    out = {lg: {"bat": {}, "pit": {}, "fld": {}} for lg, _ in LEAGUES}

    def ent(lg, kind, name, code):
        e = out[lg][kind].setdefault(name, {"name": name, "teams": [], "pid": None, "games": 0})
        tname = teams[code]["name"]
        if tname not in e["teams"]:
            e["teams"].append(tname)
            e["games"] = max(e["games"], teams[code].get("games") or FULL_SEASON)
        e["pid"] = e["pid"] or links.get((name, tname))
        return e

    for r in st["bat"]:
        code = r[bc["team"]]
        e = ent(teams[code]["league"], "bat", r[bc["name"]], code)
        for k in st["bat_cols"][3:]:
            e[k] = e.get(k, 0) + r[bc[k]]
    for r in st["pit"]:
        code = r[pc["team"]]
        e = ent(teams[code]["league"], "pit", r[pc["name"]], code)
        for k in st["pit_cols"][3:]:
            e[k] = e.get(k, 0) + r[pc[k]]
    for r in st["fld"]:
        code = r[fc["team"]]
        e = ent(teams[code]["league"], "fld", r[fc["name"]], code)
        pos = r[fc["pos"]]
        for k in ("試合", "刺殺", "補殺", "失策", "併殺", "捕逸"):
            if k in fc:
                e[(pos, k)] = e.get((pos, k), 0) + r[fc[k]]
                e[(None, k)] = e.get((None, k), 0) + r[fc[k]]
        if "刺殺" in fc:
            e[(pos, "機会")] = e.get((pos, "機会"), 0) + r[fc["刺殺"]] + r[fc["補殺"]] + r[fc["失策"]]
    # 率の計算
    for lg in out:
        for e in out[lg]["bat"].values():
            ab, h = e["打数"], e["安打"]
            s1 = h - e["二塁打"] - e["三塁打"] - e["本塁打"]
            e["塁打"] = s1 + 2 * e["二塁打"] + 3 * e["三塁打"] + 4 * e["本塁打"]
            den = ab + e["四球"] + e["死球"] + e["犠飛"]
            e["打率"] = h / ab if ab else None
            e["出塁率"] = (h + e["四球"] + e["死球"]) / den if den else None
            e["長打率"] = e["塁打"] / ab if ab else None
            e["OPS"] = e["出塁率"] + e["長打率"] if ab and den else None
        for e in out[lg]["pit"].values():
            ip = e["outs"] / 3
            e["防御率"] = 9 * e["自責点"] / ip if ip else None
            e["WHIP"] = (e["安打"] + e["四球"]) / ip if ip else None
            e["K9"] = 9 * e["三振"] / ip if ip else None
            n = e["勝利"] + e["敗北"]
            e["勝率"] = e["勝利"] / n if n else None
    return out


def ranked(entries, getv, order="desc", qualify=lambda e: True):
    """上位TOP人（同じ値で並んだ人は含める）→ [(順位, 値, entry)], 打ち切った人数"""
    es = [(getv(e), e) for e in entries if qualify(e)]
    es = [(v, e) for v, e in es if v is not None and (v > 0 or order == "asc")]
    es.sort(key=lambda x: (x[0] if order == "asc" else -x[0], x[1]["name"]))
    out, rank = [], 0
    for i, (v, e) in enumerate(es):
        if i == 0 or v != es[i - 1][0]:
            rank = i + 1
        if rank > TOP:
            break
        out.append((rank, v, e))
    return out[:MAX_ROWS], max(0, len(out) - MAX_ROWS)


def name_cell(e, has_page):
    n = esc(disp(e["name"]))
    if e["pid"] in has_page:
        n = f'<a href="/player/{e["pid"]}/">{n}</a>'
    return f'{n}<span class="tm">{esc("・".join(e["teams"]))}</span>'


# NPBの表彰のタイトル（各分類の先頭に、この順で並べて「タイトル」の印を付ける）。
# 最優秀中継ぎはホールドポイント（救援勝利＋ホールド）で決まり、救援勝利の数が無いので入れない
TITLES = ["首位打者（打率）", "本塁打王", "打点王", "最多安打", "盗塁王", "最高出塁率",
          "最多勝利", "最優秀防御率", "最多奪三振", "最高勝率", "最多セーブ"]


def title_first(cards):
    return sorted(cards, key=lambda c: (TITLES.index(c[0]) if c[0] in TITLES else len(TITLES)))


def card(title, per_league, kind, unit, note, has_page):
    cols = []
    for lg, label in LEAGUES:
        rows, more = per_league.get(lg, ([], 0))
        if rows:
            body = "".join(f'<li><span class="rk">{r}</span><span class="nm">{name_cell(e, has_page)}</span>'
                           f'<span class="v">{fmt(v, kind)}<small>{esc(unit)}</small></span></li>' for r, v, e in rows)
            if more:
                body += f'<li class="more">ほか{more}人</li>'
        else:
            body = '<li class="none">該当なし</li>'
        cols.append(f'<div class="lg lg-{lg}"><h4>{label}</h4><ol>{body}</ol></div>')
    badge = '<span class="title-badge">タイトル</span>' if title in TITLES else ""
    return (f'<section class="card{" title" if badge else ""}"><h3>{esc(title)}{badge}</h3>' + (f'<p class="q">{esc(note)}</p>' if note else "")
            + f'<div class="two">{"".join(cols)}</div></section>')


def year_cards(st, links, has_page):
    P = season_players(st, links)
    final = bool(st.get("final"))
    groups = []

    def qual_pa(e):
        return e["打席"] >= round(e["games"] * 3.1)

    def qual_ip(e):
        return e["outs"] >= e["games"] * 3

    def qual_win(e):
        need = 13 if final else math.ceil(13 * e["games"] / FULL_SEASON)
        return e["勝利"] >= need

    cards = []
    for k, title, unit, kind in BAT:
        per = {lg: ranked(P[lg]["bat"].values(), lambda e, k=k: e.get(k)) for lg, _ in LEAGUES}
        cards.append((title, card(title, per, kind, unit, "", has_page), per))
    for k, title in BAT_RATES:
        per = {lg: ranked(P[lg]["bat"].values(), lambda e, k=k: e.get(k), qualify=qual_pa) for lg, _ in LEAGUES}
        cards.append((title, card(title, per, "rate3", "", "規定打席以上", has_page), per))
    groups.append(("打撃", "bat", title_first(cards)))

    cards = []
    for k, title, unit, kind in PIT:
        per = {lg: ranked(P[lg]["pit"].values(), lambda e, k=k: e.get(k)) for lg, _ in LEAGUES}
        cards.append((title, card(title, per, kind, unit, "", has_page), per))
    for k, title, order in PIT_RATES:
        q = qual_win if k == "勝率" else qual_ip
        note = ("13勝以上" if final else "13勝相当以上（今季の試合数に応じて）") if k == "勝率" else "規定投球回以上"
        per = {lg: ranked(P[lg]["pit"].values(), lambda e, k=k: e.get(k), order=order, qualify=q) for lg, _ in LEAGUES}
        cards.append((title, card(title, per, "rate3" if k == "勝率" else "rate2", "", note, has_page), per))
    groups.append(("投手", "pit", title_first(cards)))

    cards = []
    if any((None, "刺殺") in e for lg, _ in LEAGUES for e in P[lg]["fld"].values()):
        for pos, k, title in FLD:
            per = {lg: ranked(P[lg]["fld"].values(), lambda e, pos=pos, k=k: e.get((pos, k))) for lg, _ in LEAGUES}
            note = "刺殺＋補殺＋失策" if k == "機会" else ""
            cards.append((title, card(title, per, "int", "", note, has_page), per))
    csp = st.get("leaders", {}).get("csp")
    if csp:
        per = {}
        for lg, _ in LEAGUES:
            rows = []
            for x in csp.get(lg, []):
                pid = links.get((x["name"], x["team"]))
                rows.append((x["rank"], x["value"], {"name": x["name"], "teams": [x["team"]], "pid": pid}))
            per[lg] = (rows, 0)
        cards.append(("盗塁阻止率", card("盗塁阻止率（捕手）", per, "rate3", "", "規定試合数以上（NPB公式の上位3人）", has_page), per))
    if cards:
        groups.append(("守備", "fld", cards))

    cards = []
    for title, kind_of, calc, kind, unit, need_pa, note in NETA:
        per = {lg: ranked(P[lg][kind_of].values(), calc, qualify=qual_pa if need_pa else (lambda e: True))
               for lg, _ in LEAGUES}
        cards.append((title, card(title, per, kind, unit, note, has_page), per))
    groups.append(("ネタ指標", "neta", cards))
    return groups


CSS = """*{ box-sizing:border-box; }
:root{ --ink:#1f2937; --ink-strong:#111827; --ink-sub:#4b5563; --ink-mute:#6b7280; --line:#d1d5db; --line-soft:#e5e7eb;
       --head-bg:#f3f4f6; --tint:#f9fafb; --accent:#2563eb; --ce:#0f766e; --pa:#1d4ed8; --gold:#b45309; }
body{ margin:0; padding:0 0 48px; font-family:"Noto Sans JP","Hiragino Kaku Gothic ProN","Hiragino Sans",Meiryo,sans-serif;
      color:var(--ink); line-height:1.7; background:#f5f5f5; }
/* ほかのページ（金特ツールなど）と同じく左に寄せ、左右に20pxの余白を取る。
   サイト共通の style.css は body を幅900pxに絞るので外し、表の広さに合わせた幅にする。
   下に付く「人気のページ」なども本文と同じ幅・余白にそろえる */
body{ max-width:none; }
.page-wrapper{ max-width:1100px; margin:0; padding:0 20px; }
body .td-rail-inline{ max-width:1100px; margin:40px 0 0; padding:0 20px; }
header{ background:var(--ink-strong); color:#fff; padding:20px 16px; margin-bottom:18px; }
h1{ margin:0; font-size:1.35rem; line-height:1.5; }
header p{ margin:6px 0 0; font-size:0.9rem; color:#cbd5e1; }
h2{ margin:30px 0 12px; padding-bottom:6px; font-size:1.15rem; color:var(--ink-strong); border-bottom:2px solid var(--line); scroll-margin-top:10px; }
p{ margin:0 0 12px; }
a{ color:var(--accent); }
.stamp{ font-size:0.88rem; color:var(--ink-sub); }
.lead{ font-size:0.95rem; }
ul.years{ list-style:none; display:flex; flex-wrap:wrap; gap:6px; margin:0 0 12px; padding:0; }
ul.years a, ul.years span{ display:inline-block; padding:4px 12px; border:1px solid var(--line); border-radius:999px; background:#fff;
    text-decoration:none; font-size:0.9rem; color:var(--ink); }
ul.years span{ background:var(--ink-strong); color:#fff; border-color:var(--ink-strong); }
.jump{ display:flex; flex-wrap:wrap; gap:6px; margin:0 0 6px; }
.jump a{ padding:4px 12px; border:1px solid var(--line); border-radius:999px; background:#fff; text-decoration:none; font-size:0.9rem; }
.cards{ display:grid; grid-template-columns:repeat(auto-fill, minmax(330px, 1fr)); gap:12px; }
.card{ background:#fff; border:1px solid var(--line); border-radius:12px; padding:8px 12px 10px; }
.card h3{ margin:2px 0 4px; font-size:1rem; color:var(--ink-strong); display:flex; align-items:center; gap:8px; }
.card.title{ border-color:#e7c77a; }
.title-badge{ font-size:0.68rem; font-weight:700; color:var(--gold); background:#fef3c7; border-radius:999px; padding:1px 8px; }
.card .q{ margin:0 0 4px; font-size:0.74rem; color:var(--ink-mute); }
.two{ display:grid; grid-template-columns:1fr 1fr; gap:10px; }
.lg h4{ margin:0 0 2px; font-size:0.76rem; color:var(--lgc); border-bottom:2px solid var(--lgc); }
.lg-central{ --lgc:var(--ce); } .lg-pacific{ --lgc:var(--pa); }
.lg ol{ list-style:none; margin:0; padding:0; }
.lg li{ display:grid; grid-template-columns:1.3em 1fr auto; gap:4px; align-items:baseline; padding:3px 0; border-bottom:1px solid var(--line-soft); font-size:0.84rem; }
.lg li:first-child .nm{ font-weight:800; }
.lg li:first-child .rk{ color:var(--gold); }
.lg .rk{ font-weight:700; color:var(--ink-mute); font-variant-numeric:tabular-nums; }
.lg .nm{ min-width:0; overflow-wrap:anywhere; line-height:1.35; }
.lg .nm a{ color:inherit; text-decoration:none; border-bottom:1px dotted var(--ink-mute); }
.lg .nm a:hover{ color:var(--accent); border-bottom-color:var(--accent); }
.lg .tm{ display:block; font-size:0.7rem; color:var(--ink-mute); font-weight:400; }
.lg .v{ font-weight:700; font-variant-numeric:tabular-nums; white-space:nowrap; }
.lg .v small{ font-size:0.7rem; font-weight:400; color:var(--ink-mute); margin-left:1px; }
.lg li.more, .lg li.none{ display:block; font-size:0.76rem; color:var(--ink-mute); }
table.kings{ border-collapse:collapse; width:100%; font-size:0.88rem; background:#fff; }
table.kings th, table.kings td{ border-bottom:1px solid var(--line-soft); padding:6px 8px; text-align:left; }
table.kings thead th{ background:var(--head-bg); font-size:0.78rem; color:var(--ink-sub); }
table.kings td.v{ text-align:right; font-weight:700; font-variant-numeric:tabular-nums; white-space:nowrap; }
.tbl-wrap{ overflow-x:auto; border:1px solid var(--line); border-radius:12px; }
.note{ font-size:0.84rem; color:var(--ink-mute); }
footer.disclaimer{ margin-top:22px; font-size:0.82rem; color:var(--ink-mute); }
@media (max-width:600px){ .cards{ grid-template-columns:1fr; } }
"""


def page(title, desc, canonical, h1, sub, body, crumb=None):
    extra = (f'<script> const BREADCRUMB_EXTRA = {{ name: "{esc(crumb)}", url: "{canonical}" }}; </script>\n'
             if crumb else "")
    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">

<!-- npb/build_kings.py が生成する。直接書き換えても、次の自動更新で消える -->
<title>{esc(title)}</title>
<meta name="description" content="{esc(desc)}">
<link rel="canonical" href="{SITE}{canonical}">

<script> const CURRENT_TOOL = "kings"; </script>
{extra}<script src="/js/tool-data.js"></script>
<script src="/js/head.js"></script>
<script src="/js/analytics.js"></script>

<!-- Google AdSense -->
<script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-8349615939902537" crossorigin="anonymous"></script>

<link rel="stylesheet" href="/kings/kings.css">
</head>

<body>
<div class="page-wrapper">
<header><h1>{esc(h1)}</h1><p>{esc(sub)}</p></header>
<div class="container">
{body}
<footer class="disclaimer">
成績はNPB（日本野球機構）公式サイトの個人成績・守備成績をもとに、当サイトが独自に集計したものです。
</footer>
</div>
</div>
</body>
</html>
"""


def years_nav(years, current=None):
    return '<ul class="years">' + "".join(
        f'<li><span>{y}</span></li>' if y == current else f'<li><a href="/kings/{y}/">{y}</a></li>'
        for y in sorted(years, reverse=True)) + "</ul>"


def top1(per):
    """各リーグの1位の名前（説明文用）"""
    out = []
    for lg, _ in LEAGUES:
        rows, _ = per.get(lg, ([], 0))
        if rows:
            out.append(disp(rows[0][2]["name"]))
    return "・".join(out)


def year_page(y, st, groups, years, as_of_text, final):
    n = sum(len(c) for _, _, c in groups)
    jump = "".join(f'<a href="#{slug}">{label}（{len(c)}部門）</a>' for label, slug, c in groups)
    parts = []
    for label, slug, cards in groups:
        parts.append(f'<h2 id="{slug}">{y}年 {label}部門</h2><div class="cards">{"".join(c for _, c, _ in cards)}</div>')
    pick = {t: per for label, slug, cards in groups for t, _, per in cards}
    hl = []
    for t in ("三振王", "併殺打王", "犠打王", "死球王"):  # 説明文にはタイトルにならない部門を
        if t in pick and top1(pick[t]):
            hl.append(f"{t}は{top1(pick[t])}")
    status = "シーズン終了" if final else f"{as_of_text}時点"
    body = (years_nav(years, y)
            + f'<p class="stamp">成績：{esc(status)}</p>'
            + f'<p class="lead">{y}年のプロ野球で、打撃・投手・守備の{n}部門について、セ・パそれぞれの上位5人を並べています。'
            '首位打者・本塁打王・最多勝利のようなタイトルの部門に加えて、三振・併殺打・犠打・死球・失策・守備機会など、'
            'ふだん順位が出ない部門も「王」として載せています。</p>'
            + f'<nav class="jump">{jump}</nav>' + "".join(parts)
            + '<p class="note">・「ネタ指標」は、なんJで昔から「ネタだが意外と優秀」と言われてきた小松式ドネーション・アダム・ダン率・赤星式盗塁です。<br>'
              '・同じ数で並んだ選手は同じ順位です。5位までに同じ数の選手が多いときは、8人まで出して残りを「ほか○人」としています。<br>'
              '・シーズン途中で同じリーグの中で移籍した選手は、両球団の成績を足しています。<br>'
              '・規定打席は所属球団の試合数×3.1、規定投球回は試合数×1.0です。得点圏打率はNPB公式の個人成績に無いため載せていません。</p>')
    title = f"{y}年 プロ野球 いろんな「王」ランキング｜三振王・併殺打王・犠打王・死球王・失策王など全{n}部門"
    desc = (f"{y}年のプロ野球（セ・パ）の打撃・投手・守備{n}部門の上位5人。" + ("、".join(hl) + "。" if hl else "")
            + "得点・二塁打・三塁打・盗塁死・四球・故意四球・暴投・ボーク・守備機会・外野手の補殺・盗塁阻止率など、"
            "タイトルにならない部門の「王」や、小松式ドネーション・アダム・ダン率・赤星式盗塁もまとめています。")
    return page(title, desc, f"/kings/{y}/", f"{y}年 プロ野球 いろんな「王」ランキング",
                "タイトルにならない部門も含めた、打撃・投手・守備の部門別の上位5人", body, crumb=f"{y}年")


def index_page(latest, groups, years, as_of_text, final):
    rows = []
    for label, slug, cards in groups:
        for t, _, per in cards:
            cells = []
            for lg, _ in LEAGUES:
                rs, _ = per.get(lg, ([], 0))
                firsts = [r for r in rs if r[0] == 1]
                if firsts:
                    names = "・".join(disp(e["name"]) for _, _, e in firsts[:3]) + ("ほか" if len(firsts) > 3 else "")
                    cells.append(f"<td>{esc(names)}</td>")
                else:
                    cells.append("<td>―</td>")
            rows.append(f'<tr><th>{esc(label)}</th><td><a href="/kings/{latest}/#{slug}">{esc(t)}</a></td>{"".join(cells)}</tr>')
    status = "シーズン終了" if final else f"{as_of_text}時点"
    body = (f'<p class="lead">プロ野球の、打撃・投手・守備の部門別ランキングです。首位打者や本塁打王のようなタイトルの部門だけでなく、'
            '三振王・併殺打王・犠打王・死球王・失策王・守備機会王のように、ふだん順位が出ない部門の「王」も年ごとに並べています。</p>'
            + '<h2>年を選ぶ</h2>' + years_nav(years)
            + f'<h2>{latest}年の各部門の1位（{esc(status)}）</h2>'
            + '<div class="tbl-wrap"><table class="kings"><thead><tr><th>分類</th><th>部門</th><th>セ・リーグ</th><th>パ・リーグ</th></tr></thead>'
            + f'<tbody>{"".join(rows)}</tbody></table></div>'
            + f'<p class="note">2位〜5位は<a href="/kings/{latest}/">{latest}年のページ</a>で見られます。</p>')
    n = sum(len(c) for _, _, c in groups)
    return page(f"プロ野球 いろんな「王」ランキング｜三振王・併殺打王・犠打王など部門別の1位【{min(years)}〜{latest}年】",
                f"プロ野球の打撃・投手・守備{n}部門の、年ごとの上位5人。三振王・併殺打王・犠打王・死球王・失策王・守備機会王など、"
                "タイトルにならない部門の「王」や、小松式ドネーション・アダム・ダン率・赤星式盗塁のランキングもまとめています。",
                "/kings/", "プロ野球 いろんな「王」ランキング", "タイトルにならない部門も含めた、部門別の1位と上位5人", body)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args(argv)
    data, out = Path(args.data), Path(args.out)

    stores = {}
    for f in sorted(data.glob("season_*.json")):
        st = json.loads(f.read_text(encoding="utf-8"))
        stores[st["year"]] = st
    people = People(data / "register.json")
    links = people.link_all({y: season_rows(st) for y, st in stores.items()})
    built = out.parent / "player" / "built.json"
    has_page = set(json.loads(built.read_text(encoding="utf-8"))["pids"]) if built.exists() else set()

    out.mkdir(parents=True, exist_ok=True)
    (out / "kings.css").write_text(CSS, encoding="utf-8")
    years = sorted(stores)
    latest = years[-1]
    latest_groups = None
    for y in years:
        st = stores[y]
        groups = year_cards(st, links.get(y, {}), has_page)
        d = datetime.strptime(st.get("as_of") or f"{y}-12-31", "%Y-%m-%d")
        as_of_text = f"{d.year}年{d.month}月{d.day}日"
        (out / str(y)).mkdir(exist_ok=True)
        (out / str(y) / "index.html").write_text(
            year_page(y, st, groups, years, as_of_text, bool(st.get("final"))), encoding="utf-8")
        if y == latest:
            latest_groups = (groups, as_of_text, bool(st.get("final")))
    (out / "index.html").write_text(index_page(latest, latest_groups[0], years, latest_groups[1], latest_groups[2]),
                                    encoding="utf-8")
    print(f"kings: {years[0]}〜{latest}年")
    return 0


if __name__ == "__main__":
    sys.exit(main())
