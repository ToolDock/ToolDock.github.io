"""選手ページ（/player/<選手ID>/）と、その一覧（/player/）を作る。

2005年以降に一軍に出場した選手ごとに、年度別の成績とセイバー指標（wOBA・wRC+・FIP・簡易WAR）、
通算成績、ドラフトの指名、登録名の変遷、プロフィールを1ページにまとめる。

- 2005年以降の成績は npb/data/season_<年>.json から計算する（セイバーメトリクス ランキングと同じ計算）
- 2004年以前の成績・読み仮名・プロフィールは npb/data/player_profiles.json（NPB公式の選手ページから取得）
- 選手の照合は在籍者名簿（npb/people.py）

約2900ページあり、毎日作り直すとリポジトリの履歴が膨らむので、シーズン終了時にだけ作り直す。
どのシーズンまでで作ったかを player/built.json に残し、
「最新のシーズンが終了し、まだそのシーズンで作っていない」ときだけ作る（--force で常に作る）。

    python npb/build_players.py --data npb/data --league war/league.json --out player
"""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_draft as bd  # noqa: E402
import player_profile  # noqa: E402
from people import People, franchise, key  # noqa: E402

JST = timezone(timedelta(hours=9))
SITE = "https://tooldock.github.io"

# 50音の行（一覧ページの分け方）。読み仮名の1文字目で分ける
ROWS = [("a", "あ行", "あいうえおぁぃぅぇぉゔ"), ("ka", "か行", "かきくけこがぎぐげご"),
        ("sa", "さ行", "さしすせそざじずぜぞ"), ("ta", "た行", "たちつてとだぢづでどっ"),
        ("na", "な行", "なにぬねの"), ("ha", "は行", "はひふへほばびぶべぼぱぴぷぺぽ"),
        ("ma", "ま行", "まみむめも"), ("ya", "や行", "やゆよゃゅょ"),
        ("ra", "ら行", "らりるれろ"), ("wa", "わ行", "わをん")]


def esc(s):
    return html.escape(str(s), quote=True)


def disp(name):
    return name.replace("　", " ")


def f3(x):
    if x is None:
        return "―"
    s = f"{x:.3f}"
    return s[1:] if s.startswith("0") else s


def f2(x):
    return "―" if x is None else f"{x:.2f}"


def f1(x):
    return "―" if x is None else f"{x:.1f}"


def ip_text(outs):
    return f"{outs // 3}" + (f" {outs % 3}/3" if outs % 3 else "")


def hira(s):
    """カタカナ → ひらがな（読みの1文字目で行を決めるため）"""
    return "".join(chr(ord(c) - 0x60) if "ァ" <= c <= "ヶ" else c for c in s)


def clean_kana(kana):
    """「（ちぇん・うぇいん）」→「ちぇん・うぇいん」、「ルイス・クルーズ　(LUIS CRUZ)」→「ルイス・クルーズ」"""
    k = re.sub(r"[\s　]*\([A-Za-z .,'\-]+\)\s*$", "", kana or "")
    return k.strip("（）() 　")


def is_foreign_kana(kana):
    """読みがカタカナ（外国出身の選手は、名前・苗字の順のカタカナ）"""
    k = clean_kana(kana)
    return bool(k) and bool(re.match(r"[ァ-ヶー]", k)) or bool(re.match(r"[A-Za-zＡ-Ｚ]", k))


def sort_kana(kana):
    """並べ替えの鍵。外国出身の選手は苗字（最後の部分）から"""
    k = clean_kana(kana)
    if is_foreign_kana(kana):
        parts = re.split(r"[・･\s]", k)
        return hira(parts[-1] + "".join(parts[:-1]))
    return hira(k)


def row_of(kana):
    if is_foreign_kana(kana):
        return "foreign"
    k = hira(clean_kana(kana))[:1]
    for slug, label, chars in ROWS:
        if k and k in chars:
            return slug
    return None


# ---------------------------------------------------------------- データ

BAT_KEYS = ("g", "pa", "ab", "r", "h", "d2", "d3", "hr", "rbi", "sb", "cs", "sh", "sf", "bb", "ibb", "hbp", "so", "gdp")
PIT_KEYS = ("g", "w", "l", "sv", "hld", "cg", "bf", "outs", "ha", "hr", "bb", "hbp", "so", "ra", "er")

# 公式の選手ページ（2004年以前）の列名 → こちらの項目名
OFFICIAL_BAT = {"試合": "g", "打席": "pa", "打数": "ab", "得点": "r", "安打": "h", "二塁打": "d2", "三塁打": "d3",
                "本塁打": "hr", "打点": "rbi", "盗塁": "sb", "盗塁刺": "cs", "犠打": "sh", "犠飛": "sf",
                "四球": "bb", "死球": "hbp", "三振": "so", "併殺打": "gdp"}
OFFICIAL_PIT = {"登板": "g", "勝利": "w", "敗北": "l", "セーブ": "sv", "ホールド": "hld", "完投": "cg",
                "打者": "bf", "安打": "ha", "本塁打": "hr", "四球": "bb", "死球": "hbp", "三振": "so",
                "失点": "ra", "自責点": "er"}


def official_rows(profile, kind, before):
    """player_profiles.json の年度別成績から、before 年より前の行を取り出す"""
    out = []
    for r in (profile or {}).get(kind, []):
        if r["y"] < before:
            out.append(r)
    return out


def load(data_dir: Path, league):
    people = People(data_dir / "register.json")
    by_pid, by_name, last_season = bd.load_seasons_people(data_dir, league, people)
    drafts = bd.load_drafts(data_dir)
    bd.assign_people(drafts, people, by_pid, by_name)
    picks = defaultdict(list)
    for y, ps in drafts.items():
        for p in ps:
            if p["pid"]:
                picks[p["pid"]].append(p)
    prof_path = data_dir / "player_profiles.json"
    profiles = json.loads(prof_path.read_text(encoding="utf-8")) if prof_path.exists() else {}
    stores = {}
    for f in sorted(data_dir.glob("season_*.json")):
        st = json.loads(f.read_text(encoding="utf-8"))
        stores[st["year"]] = {"as_of": st.get("as_of"), "final": bool(st.get("final"))}
    return people, by_pid, picks, profiles, stores, last_season


def seasons_of(pid, by_pid, profile):
    """→ (打撃の年度別, 投球の年度別)。各行 {y, teams, ...数, (woba, wrcp, war / fip, war)}"""
    bat, pit = [], []
    first_ours = min((y for y, _, _ in by_pid.get(pid, [])), default=9999)
    # 2004年以前（公式）
    for r in official_rows(profile, "bat", min(2005, first_ours)):
        bat.append(dict(r, src="npb"))
    for r in official_rows(profile, "pit", min(2005, first_ours)):
        pit.append(dict(r, src="npb"))
    # 2005年以降（こちらで計算）
    for y, b, p in sorted(by_pid.get(pid, []), key=lambda s: s[0]):
        if b:
            row = {"y": y, "teams": b["teams"], "pos": b["pos"], "src": "calc",
                   "woba": b["woba"], "wrcp": b["wrcp"], "war": b["war"]}
            row.update({k: b.get(k) or 0 for k in BAT_KEYS})
            bat.append(row)
        if p:
            row = {"y": y, "teams": p["teams"], "role": p["role"], "src": "calc", "fip": p["fip"], "war": p["war"]}
            row.update({k: p.get(k) or 0 for k in PIT_KEYS})
            pit.append(row)
    return bat, pit


def totals(rows, keys):
    t = defaultdict(int)
    for r in rows:
        for k in keys:
            t[k] += r.get(k) or 0
    return t


def bat_rates(t):
    ab, h = t["ab"], t["h"]
    s1 = h - t["d2"] - t["d3"] - t["hr"]
    den = ab + t["bb"] + t["hbp"] + t["sf"]
    avg = h / ab if ab else None
    obp = (h + t["bb"] + t["hbp"]) / den if den else None
    slg = (s1 + 2 * t["d2"] + 3 * t["d3"] + 4 * t["hr"]) / ab if ab else None
    return avg, obp, slg, (obp + slg if obp is not None and slg is not None else None)


def pit_rates(t):
    ip = t["outs"] / 3
    era = 9 * t["er"] / ip if ip else None
    whip = (t["ha"] + t["bb"]) / ip if ip else None
    k9 = 9 * t["so"] / ip if ip else None
    return era, whip, k9


def kind_of(bat, pit):
    """投手か野手か（ページの主な表をどちらにするか）"""
    pa = sum(r["pa"] for r in bat)
    outs = sum(r["outs"] for r in pit)
    if outs and outs >= 3 * max(10, pa / 4):
        return "p"
    return "b" if pa else "p"


# ---------------------------------------------------------------- 表示

def team_text(teams):
    return "・".join(teams)


def bat_table(rows, show_saber=True):
    head = ("<tr><th>年度</th><th class='tm'>球団</th><th>守</th><th>試合</th><th>打席</th><th>打数</th><th>得点</th>"
            "<th>安打</th><th>二塁打</th><th>三塁打</th><th>本塁打</th><th>打点</th><th>盗塁</th><th>盗塁刺</th>"
            "<th>犠打</th><th>犠飛</th><th>四球</th><th>死球</th><th>三振</th><th>併殺打</th>"
            "<th>打率</th><th>出塁率</th><th>長打率</th><th>OPS</th>"
            + ("<th>wOBA</th><th>wRC+</th><th class='war'>WAR</th>" if show_saber else "") + "</tr>")
    body = []
    for r in rows:
        avg, obp, slg, ops = bat_rates(r)
        calc = r["src"] == "calc"
        body.append(
            f"<tr><td>{r['y']}</td><td class='tm'>{esc(team_text(r['teams']))}</td><td>{esc(r.get('pos') or '')}</td>"
            + "".join(f"<td>{r[k]}</td>" for k in ("g", "pa", "ab", "r", "h", "d2", "d3", "hr", "rbi", "sb", "cs",
                                                   "sh", "sf", "bb", "hbp", "so", "gdp"))
            + f"<td>{f3(avg)}</td><td>{f3(obp)}</td><td>{f3(slg)}</td><td>{f3(ops)}</td>"
            + ((f"<td>{f3(r['woba'])}</td><td>{r['wrcp'] if r['wrcp'] is not None else '―'}</td>"
                f"<td class='war'>{f1(r['war'])}</td>" if calc else "<td>―</td><td>―</td><td class='war'>―</td>")
               if show_saber else "") + "</tr>")
    t = totals(rows, BAT_KEYS)
    avg, obp, slg, ops = bat_rates(t)
    war = sum(r["war"] or 0 for r in rows if r["src"] == "calc")
    foot = (f"<tr class='total'><th colspan='3'>通算（{len(rows)}年）</th>"
            + "".join(f"<td>{t[k]}</td>" for k in ("g", "pa", "ab", "r", "h", "d2", "d3", "hr", "rbi", "sb", "cs",
                                                   "sh", "sf", "bb", "hbp", "so", "gdp"))
            + f"<td>{f3(avg)}</td><td>{f3(obp)}</td><td>{f3(slg)}</td><td>{f3(ops)}</td>"
            + (f"<td>―</td><td>―</td><td class='war'>{f1(war)}</td>" if show_saber else "") + "</tr>")
    return (f"<div class='tbl-wrap'><table class='stats'><thead>{head}</thead>"
            f"<tbody>{''.join(body)}</tbody><tfoot>{foot}</tfoot></table></div>")


def pit_table(rows):
    head = ("<tr><th>年度</th><th class='tm'>球団</th><th>登板</th><th>勝利</th><th>敗北</th><th>セーブ</th>"
            "<th>ホールド</th><th>完投</th><th>投球回</th><th>被安打</th><th>被本塁打</th><th>与四球</th>"
            "<th>与死球</th><th>奪三振</th><th>失点</th><th>自責点</th><th>防御率</th><th>WHIP</th><th>奪三振率</th>"
            "<th>FIP</th><th class='war'>WAR</th></tr>")
    body = []
    for r in rows:
        era, whip, k9 = pit_rates(r)
        calc = r["src"] == "calc"
        body.append(
            f"<tr><td>{r['y']}</td><td class='tm'>{esc(team_text(r['teams']))}</td>"
            + "".join(f"<td>{r[k]}</td>" for k in ("g", "w", "l", "sv", "hld", "cg"))
            + f"<td>{ip_text(r['outs'])}</td>"
            + "".join(f"<td>{r[k]}</td>" for k in ("ha", "hr", "bb", "hbp", "so", "ra", "er"))
            + f"<td>{f2(era)}</td><td>{f2(whip)}</td><td>{f2(k9)}</td>"
            + (f"<td>{f2(r['fip'])}</td><td class='war'>{f1(r['war'])}</td>" if calc else "<td>―</td><td class='war'>―</td>")
            + "</tr>")
    t = totals(rows, PIT_KEYS)
    era, whip, k9 = pit_rates(t)
    war = sum(r["war"] or 0 for r in rows if r["src"] == "calc")
    foot = (f"<tr class='total'><th colspan='2'>通算（{len(rows)}年）</th>"
            + "".join(f"<td>{t[k]}</td>" for k in ("g", "w", "l", "sv", "hld", "cg"))
            + f"<td>{ip_text(t['outs'])}</td>"
            + "".join(f"<td>{t[k]}</td>" for k in ("ha", "hr", "bb", "hbp", "so", "ra", "er"))
            + f"<td>{f2(era)}</td><td>{f2(whip)}</td><td>{f2(k9)}</td><td>―</td><td class='war'>{f1(war)}</td></tr>")
    return (f"<div class='tbl-wrap'><table class='stats'><thead>{head}</thead>"
            f"<tbody>{''.join(body)}</tbody><tfoot>{foot}</tfoot></table></div>")


def spans_text(person, current=None):
    """在籍の履歴を「2007〜2025 巨人」のように縮める（育成は（育成）と添える）。
    current=(年, 球団)：名簿にまだ無い今シーズンの在籍（成績から分かるもの）。
    続いている在籍は「2007〜 巨人」とする"""
    spans = list(person["spans"])
    if current and not any(y == current[0] for y, _, _ in spans):
        spans.append([current[0], current[1], ""])
    # [最初の年, 最後の年, 球団（横浜とDeNAは同じ）, 表示する球団名, 育成か]
    items = []
    for y, team, kind in sorted(spans, key=lambda s: (s[0], s[2] != "育")):
        ik = kind == "育"
        same = [it for it in items if it[2] == franchise(team) and it[4] == ik]
        if same and same[-1] is items[-1] and items[-1][1] >= y - 1:
            it = items[-1]
            it[1] = max(it[1], y)
            if team not in it[3]:
                it[3].append(team)
        elif not any(it[0] <= y <= it[1] for it in same):
            items.append([y, y, franchise(team), [team], ik])
    now = current[0] if current else None

    def one(a, b, names, ik):
        n = "・".join(names) + ("（育成）" if ik else "")
        if b == now:
            return f"{a}〜 {n}"
        return f"{a}〜{b} {n}" if a != b else f"{a} {n}"
    return "、".join(one(a, b, names, ik) for a, b, _, names, ik in items)


def pick_text(p):
    lab = bd.pick_label(p)
    return f"{p['year']}年 {p['team']} {'育成' if p['ikusei'] else ''}{lab}"


def render_player(pid, person, display_name, seen, bat, pit, picks, profile, as_of_text, final):
    name = disp(person["name"])
    kana = clean_kana((profile or {}).get("kana", ""))
    kind = kind_of(bat, pit)
    last_row = max(bat + pit, key=lambda r: r["y"])
    last_team = last_row["teams"][-1]
    t_bat = totals(bat, BAT_KEYS)
    t_pit = totals(pit, PIT_KEYS)
    show_bat = bool(bat) and (kind == "b" or t_bat["pa"] >= 100)
    war_rows = [r for r in (bat if show_bat else []) + pit if r["src"] == "calc"]
    war = sum(r["war"] or 0 for r in war_rows)
    years = sorted({r["y"] for r in bat + pit})
    first, last = years[0], years[-1]
    war_label = "簡易WAR（2005年〜）" if first < 2005 else "簡易WAR"

    # 見出しのカード
    if kind == "p":
        era, whip, _ = pit_rates(t_pit)
        sh = " ".join(x for x in (f"{t_pit['sv']}S" if t_pit["sv"] else "", f"{t_pit['hld']}H" if t_pit["hld"] else "") if x)
        cards = [("通算", f"{t_pit['w']}勝{t_pit['l']}敗" + (f" {sh}" if sh else "")),
                 ("防御率", f2(era)), ("奪三振", f"{t_pit['so']}"), (war_label, f1(war))]
        summary = (f"通算{t_pit['g']}登板{t_pit['w']}勝{t_pit['l']}敗{t_pit['sv']}セーブ{t_pit['hld']}ホールド、"
                   f"防御率{f2(era)}、{t_pit['so']}奪三振")
    else:
        avg, obp, slg, ops = bat_rates(t_bat)
        cards = [("通算", f"{t_bat['g']}試合 {t_bat['h']}安打"), ("本塁打", f"{t_bat['hr']}"),
                 ("打率 / OPS", f"{f3(avg)} / {f3(ops)}"), (war_label, f1(war))]
        summary = (f"通算{t_bat['g']}試合{t_bat['h']}安打{t_bat['hr']}本塁打{t_bat['rbi']}打点"
                   f"{t_bat['sb']}盗塁、打率{f3(avg)}、OPS{f3(ops)}")
    war_note = "2005年以降" if first < 2005 else ""

    prof = (profile or {}).get("profile", {})
    dl = []
    if kana:
        dl.append(("読み", kana))
    dl.append(("所属", f"{last_team}（{last}年）"))
    for k in ("投打", "身長／体重", "生年月日", "経歴"):
        if prof.get(k):
            dl.append((k, prof[k]))
    for p in sorted(picks, key=lambda p: p["year"]):
        state = "（入団せず）" if p["unsigned"] else ""
        dl.append(("ドラフト", f'<a href="/draft/{p["year"]}/">{esc(pick_text(p))}</a>{state}'))
    if not picks and prof.get("ドラフト"):
        # 2004年以前のドラフト（答え合わせのページが無い）は、公式の記載をそのまま
        dl.append(("ドラフト", esc(prof["ドラフト"])))
    others = [n for n in seen if key(n) != key(person["name"])]
    aliases = [a for a in person["alias"] if key(a) != key(person["name"])]
    names = []
    for n in aliases + others:
        if key(n) not in {key(x) for x in names}:
            names.append(n)
    if names:
        dl.append(("登録名・旧名", "、".join(esc(disp(n)) for n in names)))
    current = (last, last_team) if last > max(y for y, _, _ in person["spans"]) else None
    dl.append(("在籍", esc(spans_text(person, current))))

    title = f"{name}の成績・WAR｜年度別成績と通算（{last_team}）"
    desc = (f"{name}（{last_team}）の{first}〜{last}年の年度別成績と通算成績。{summary}。"
            f"wOBA・wRC+・FIPなどのセイバー指標と簡易WAR（{war_note or '通算'}{f1(war)}）も年ごとに掲載。")
    status = f"成績は{as_of_text}{'' if final else '時点'}までの一軍公式戦です。"
    body = [f'<p class="stamp">{esc(status)}</p>',
            '<div class="cards">' + "".join(f'<div class="card"><div class="k">{esc(k)}</div><div class="v">{esc(v)}</div></div>'
                                            for k, v in cards) + "</div>",
            '<h2>プロフィール</h2><dl class="prof">'
            + "".join(f"<dt>{esc(k)}</dt><dd>{v if k in ('ドラフト', '登録名・旧名', '在籍') else esc(v)}</dd>" for k, v in dl)
            + "</dl>"]
    if pit:
        body.append(f"<h2>投手成績（年度別）</h2>{pit_table(pit)}")
    if show_bat:
        body.append(f"<h2>打撃成績（年度別）</h2>{bat_table(bat)}")
    notes = ["簡易WARは、打撃・盗塁・守備位置・代替水準（投手はFIP）から計算したもので、"
             "守備の上手さ（UZR）や球場の補正は入っていません（<a href=\"/war/\">計算方法</a>）。"]
    if first < 2005:
        notes.append("2004年以前の成績はNPB公式の記録です。wOBA・wRC+・FIP・WARは2005年以降だけ計算しています。")
    notes.append("複数の球団に在籍した年は、その年の合計です。守備位置は最も多く守った位置です。")
    body.append('<p class="note">' + "<br>".join("・" + n for n in notes) + "</p>")
    body.append(f'<p class="links"><a href="/saber/?k={"pit" if kind == "p" else "bat"}&amp;year={last}">'
                f'{last}年のセイバーメトリクス ランキング</a>　<a href="/player/">選手一覧</a></p>')

    crumb = f'<script> const BREADCRUMB_EXTRA = {{ name: "{esc(name)}", url: "/player/{pid}/" }}; </script>'
    return page(title, desc, f"/player/{pid}/", f"{name}" + (f"<span class='kana'>{esc(kana)}</span>" if kana else ""),
                "\n".join(body), crumb, h1_text=name)


def page(title, desc, canonical, h1_html, body, extra_head="", h1_text=None):
    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">

<!-- npb/build_players.py が生成する。直接書き換えても、次の作り直しで消える -->
<title>{esc(title)}</title>
<meta name="description" content="{esc(desc)}">
<link rel="canonical" href="{SITE}{canonical}">

<script> const CURRENT_TOOL = "player"; </script>
{extra_head}
<script src="/js/tool-data.js"></script>
<script src="/js/head.js"></script>
<script src="/js/analytics.js"></script>

<!-- Google AdSense -->
<script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-8349615939902537" crossorigin="anonymous"></script>

<link rel="stylesheet" href="/player/player.css">
</head>

<body>
<div class="page-wrapper">
<header><h1>{h1_html}</h1></header>
<div class="container">
{body}
<footer class="disclaimer">
成績はNPB（日本野球機構）公式サイトの個人成績をもとに、当サイトが独自に集計・計算したものです。
選手の照合はNPBの在籍者名簿（在籍した年・球団・改名の履歴）で行っています。
</footer>
</div>
</div>
</body>
</html>
"""


def index_page(entries, stores_latest):
    """一覧：50音の行ごと（読みが分からない選手は最後に）"""
    groups = defaultdict(list)
    for e in entries:
        groups[row_of(e["kana"]) or "other"].append(e)
    sections = ROWS + [("foreign", "外国出身の選手", ""), ("other", "その他", "")]
    nav = "".join(f'<a href="#{slug}">{label}</a>' for slug, label, _ in sections if groups.get(slug))
    parts = []
    for slug, label, _ in sections:
        es = sorted(groups.get(slug, []), key=lambda e: (sort_kana(e["kana"]) or "ん", e["name"]))
        if not es:
            continue
        parts.append(f'<h2 id="{slug}">{label}（{len(es)}人）</h2><ul class="plist">'
                     + "".join(f'<li><a href="/player/{e["pid"]}/">{esc(disp(e["name"]))}</a>'
                               f'<span>{esc(e["team"])} {e["first"]}'
                               + (f'〜{e["last"]}' if e["last"] != e["first"] else "") + '</span></li>' for e in es)
                     + "</ul>")
    body = (f'<p class="lead">2005年以降に一軍の公式戦に出場した{len(entries)}人の選手ページです。'
            '年度別の成績と通算成績、wOBA・wRC+・FIPなどのセイバー指標と簡易WAR、ドラフトの指名、登録名の変遷をまとめています。</p>'
            f'<nav class="kana-nav">{nav}</nav>' + "".join(parts))
    return page("プロ野球 選手一覧｜年度別成績・通算成績とWAR【2005年〜】",
                f"2005年以降に一軍に出場したプロ野球選手{len(entries)}人の、年度別成績・通算成績とセイバー指標（wOBA・wRC+・FIP・簡易WAR）を選手ごとにまとめたページの一覧です。",
                "/player/", "プロ野球 選手一覧", body)


CSS = """*{ box-sizing:border-box; }
:root{
    --ink:#1f2937; --ink-strong:#111827; --ink-sub:#4b5563; --ink-mute:#6b7280;
    --line:#d1d5db; --line-soft:#e5e7eb; --head-bg:#f3f4f6; --tint:#f9fafb; --accent:#2563eb;
}
body{ margin:0; padding:0 0 48px; font-family:"Noto Sans JP","Hiragino Kaku Gothic ProN","Hiragino Sans",Meiryo,sans-serif;
      color:var(--ink); line-height:1.75; background:#f5f5f5; }
/* ほかのページ（金特ツールなど）と同じく左に寄せ、左右に20pxの余白を取る。
   サイト共通の style.css は body を幅900pxに絞るので外し、表の広さに合わせた幅にする。
   下に付く「人気のページ」なども本文と同じ幅・余白にそろえる */
body{ max-width:none; }
.page-wrapper{ max-width:1100px; margin:0; padding:0 20px; }
body .td-rail-inline{ max-width:1100px; margin:40px 0 0; padding:0 20px; }
header{ background:var(--ink-strong); color:#fff; padding:20px 16px; margin-bottom:18px; }
h1{ margin:0; font-size:1.45rem; line-height:1.5; }
h1 .kana{ display:block; font-size:0.85rem; font-weight:400; color:#cbd5e1; }
h2{ margin:30px 0 12px; padding-bottom:6px; font-size:1.15rem; color:var(--ink-strong); border-bottom:2px solid var(--line); }
p{ margin:0 0 12px; }
a{ color:var(--accent); }
.stamp{ font-size:0.88rem; color:var(--ink-sub); }
.lead{ font-size:0.95rem; }
.cards{ display:grid; grid-template-columns:repeat(auto-fit, minmax(150px, 1fr)); gap:10px; margin:0 0 6px; }
.card{ background:#fff; border:1px solid var(--line); border-radius:12px; padding:10px 14px; }
.card .k{ font-size:0.78rem; color:var(--ink-sub); font-weight:700; }
.card .v{ font-size:1.25rem; font-weight:800; color:var(--ink-strong); font-variant-numeric:tabular-nums; line-height:1.4; }
dl.prof{ display:grid; grid-template-columns:max-content 1fr; gap:6px 16px; margin:0; background:#fff;
         border:1px solid var(--line); border-radius:12px; padding:12px 16px; font-size:0.93rem; }
dl.prof dt{ font-weight:700; color:var(--ink-sub); }
dl.prof dd{ margin:0; }
.tbl-wrap{ overflow-x:auto; -webkit-overflow-scrolling:touch; background:#fff; border:1px solid var(--line); border-radius:12px; }
table.stats{ border-collapse:collapse; width:100%; font-size:0.84rem; font-variant-numeric:tabular-nums; }
table.stats th, table.stats td{ padding:6px 7px; border-bottom:1px solid var(--line-soft); text-align:right; white-space:nowrap; }
table.stats thead th{ background:var(--head-bg); font-size:0.76rem; color:var(--ink-sub); }
table.stats td:first-child, table.stats th:first-child{ position:sticky; left:0; background:#fff; text-align:left; font-weight:700; }
table.stats thead th:first-child{ background:var(--head-bg); }
table.stats .tm{ text-align:left; }
table.stats td.war{ font-weight:700; }
table.stats tfoot td, table.stats tfoot th{ font-weight:700; background:var(--tint); border-top:2px solid var(--line); }
table.stats tfoot th:first-child{ background:var(--tint); }
.note{ font-size:0.84rem; color:var(--ink-mute); margin-top:12px; }
.links{ font-size:0.92rem; }
.kana-nav{ display:flex; flex-wrap:wrap; gap:6px; margin:0 0 8px; }
.kana-nav a{ padding:4px 12px; border:1px solid var(--line); border-radius:999px; background:#fff; text-decoration:none; font-size:0.9rem; }
ul.plist{ list-style:none; margin:0; padding:0; display:grid; grid-template-columns:repeat(auto-fill, minmax(210px, 1fr)); gap:2px 12px; }
ul.plist li{ padding:3px 0; border-bottom:1px solid var(--line-soft); font-size:0.92rem; }
ul.plist li span{ display:block; font-size:0.74rem; color:var(--ink-mute); }
footer.disclaimer{ margin-top:22px; font-size:0.82rem; color:var(--ink-mute); }
@media (max-width:600px){
    dl.prof{ grid-template-columns:1fr; gap:0 0; }
    dl.prof dd{ margin-bottom:6px; }
}
"""


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--league", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--force", action="store_true", help="シーズン途中でも作り直す")
    ap.add_argument("--no-fetch", action="store_true", help="プロフィールの無い選手の分を公式ページから取らない")
    args = ap.parse_args(argv)

    data = Path(args.data)
    out = Path(args.out)
    league = json.loads(Path(args.league).read_text(encoding="utf-8"))["seasons"]
    latest = max(int(f.stem.split("_")[1]) for f in data.glob("season_*.json"))
    st_latest = json.loads((data / f"season_{latest}.json").read_text(encoding="utf-8"))
    final = bool(st_latest.get("final"))
    built_path = out / "built.json"
    built = json.loads(built_path.read_text(encoding="utf-8")) if built_path.exists() else {}
    if not args.force and built.get("season") == latest and (built.get("final") or not final):
        print(f"player: {latest}年は作成済み（{'シーズン終了' if built.get('final') else 'シーズン途中'}）。作り直さない")
        return 0
    if not args.force and not final and built:
        print(f"player: {latest}年はシーズン途中。シーズン終了まで作り直さない")
        return 0

    if not args.no_fetch:
        # 新しく一軍に出た選手（新人など）の読み仮名・プロフィールを公式ページから取る
        people0 = People(data / "register.json")
        by_pid0, _, _ = bd.load_seasons_people(data, league, people0)
        got = player_profile.fill_missing(data / "player_profiles.json",
                                          [p for p in by_pid0 if not p.startswith("r")])
        print(f"player: プロフィールを{got}人分取得")
    people, by_pid, picks, profiles, stores, last_season = load(data, league)
    as_of = st_latest.get("as_of") or f"{latest}-12-31"
    d = datetime.strptime(as_of, "%Y-%m-%d")
    as_of_text = f"{d.year}年{d.month}月{d.day}日" if not final else f"{latest}年シーズン終了"

    out.mkdir(parents=True, exist_ok=True)
    (out / "player.css").write_text(CSS, encoding="utf-8")
    entries = []
    for pid, rows in by_pid.items():
        if pid.startswith("r") or pid not in people.by_pid:
            continue
        person = people.by_pid[pid]
        profile = profiles.get(pid)
        bat, pit = seasons_of(pid, by_pid, profile)
        if not bat and not pit:
            continue
        seen = people.seen_names.get(pid, [])
        html_text = render_player(pid, person, people.display(pid), seen, bat, pit, picks.get(pid, []),
                                  profile, as_of_text, final)
        d_ = out / pid
        d_.mkdir(exist_ok=True)
        (d_ / "index.html").write_text(html_text, encoding="utf-8")
        years = [r["y"] for r in bat + pit]
        last_row = max(bat + pit, key=lambda r: r["y"])
        entries.append({"pid": pid, "name": person["name"], "kana": (profile or {}).get("kana", ""),
                        "team": last_row["teams"][-1], "first": min(years), "last": max(years)})
    (out / "index.html").write_text(index_page(entries, latest), encoding="utf-8")
    built_path.write_text(json.dumps({"season": latest, "final": final, "as_of": as_of,
                                      "pids": sorted(e["pid"] for e in entries)}, ensure_ascii=False) + "\n",
                          encoding="utf-8")
    print(f"player: {len(entries)}人（{latest}年{'シーズン終了' if final else 'シーズン途中'}）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
