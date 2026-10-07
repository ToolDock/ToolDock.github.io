"""選手ページ（/player/<選手ID>/）と、その一覧（/player/）を作る。

2005年以降に一軍に出場した選手ごとに、年度別の成績とセイバー指標（wOBA・wRC+・FIP・簡易WAR）、
通算成績、ドラフトの指名、登録名の変遷、プロフィールを1ページにまとめる。

- 2005年以降の成績は npb/data/season_<年>.json から計算する（セイバーメトリクス ランキングと同じ計算）
- 2004年以前の成績・読み仮名・プロフィールは npb/data/player_profiles.json（NPB公式の選手ページから取得）
- 選手の照合は在籍者名簿（npb/people.py）

約2900ページあり、毎日作り直すとリポジトリの履歴が膨らむので、全ページはシーズン終了時にだけ作り直す。
どのシーズンまでで作ったかを player/built.json に残し、
「最新のシーズンが終了し、まだそのシーズンで作っていない」ときだけ全ページを作る（--force で常に作る）。
それ以外の日は、球団の選手一覧（npb/data/roster_<年度>.json）をもとに、
検索用の players.json と、新しく一軍に出た選手・在籍が変わった選手（移籍・退団・引退）のページだけを作る。

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
from build_saber import season_rows  # noqa: E402
import player_profile  # noqa: E402
from people import People, franchise, is_foreign_style, key  # noqa: E402

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
    stores, full = {}, {}
    for f in sorted(data_dir.glob("season_*.json")):
        st = json.loads(f.read_text(encoding="utf-8"))
        stores[st["year"]] = {"as_of": st.get("as_of"), "final": bool(st.get("final"))}
        full[st["year"]] = st
    fielding = load_fielding(full, people)
    return people, by_pid, picks, profiles, stores, last_season, fielding


FLD_POS = ["捕手", "一塁手", "二塁手", "三塁手", "遊撃手", "外野手"]
FLD_KEYS = ("g", "po", "a", "e", "dp", "pb")


def load_fielding(full, people):
    """守備成績（NPB公式の守備部門、2005年以降）→ {pid: [{y, pos, teams, g, po, a, e, dp, pb}]}。
    シーズン途中で移籍した年は、同じ守備位置の成績を足す"""
    links = people.link_all({y: season_rows(st) for y, st in full.items()})
    out = defaultdict(dict)
    for y, st in full.items():
        cols = st.get("fld_cols") or []
        if "刺殺" not in cols:
            continue
        c = {k: i for i, k in enumerate(cols)}
        for r in st["fld"]:
            tname = st["teams"][r[c["team"]]]["name"]
            pid = links.get(y, {}).get((r[c["name"]], tname))
            if not pid:
                continue
            row = out[pid].setdefault((y, r[c["pos"]]), {"y": y, "pos": r[c["pos"]], "teams": [],
                                                           **{k: 0 for k in FLD_KEYS}})
            if tname not in row["teams"]:
                row["teams"].append(tname)
            for k, col in zip(FLD_KEYS, ("試合", "刺殺", "補殺", "失策", "併殺", "捕逸")):
                row[k] += r[c[col]]
    return {pid: sorted(rows.values(), key=lambda r: (r["y"], FLD_POS.index(r["pos"]) if r["pos"] in FLD_POS else 9))
            for pid, rows in out.items()}


def fld_pct(r):
    n = r["po"] + r["a"] + r["e"]
    return f3((r["po"] + r["a"]) / n) if n else "―"


def fld_table(rows):
    """守備成績の年度別の表と、守備位置ごとの通算"""
    has_pb = any(r["pos"] == "捕手" for r in rows)
    head = ("<tr><th>年度</th><th class='tm'>球団</th><th class='tm'>守備位置</th><th>試合</th><th>刺殺</th><th>補殺</th>"
            "<th>失策</th><th>併殺</th>" + ("<th>捕逸</th>" if has_pb else "") + "<th>守備率</th></tr>")

    def cells(r):
        return ("".join(f"<td>{r[k]}</td>" for k in ("g", "po", "a", "e", "dp"))
                + (f"<td>{r['pb'] if r['pos'] == '捕手' else '―'}</td>" if has_pb else "") + f"<td>{fld_pct(r)}</td>")
    body = "".join(f"<tr><td>{r['y']}</td><td class='tm'>{esc(team_text(r['teams']))}</td><td class='tm'>{esc(r['pos'])}</td>"
                   + cells(r) + "</tr>" for r in rows)
    foot = ""
    for pos in FLD_POS:
        ps = [r for r in rows if r["pos"] == pos]
        if ps:
            t = {k: sum(r[k] for r in ps) for k in FLD_KEYS}
            t["pos"] = pos
            foot += f"<tr class='total'><th colspan='3'>通算 {esc(pos)}（{len(ps)}年）</th>" + cells(t) + "</tr>"
    return (f"<div class='tbl-wrap'><table class='stats'><thead>{head}</thead>"
            f"<tbody>{body}</tbody><tfoot>{foot}</tfoot></table></div>")


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
            "<th>安打</th><th>二塁打</th><th>三塁打</th><th>本塁打</th><th>打点</th><th>盗塁</th><th>盗塁死</th>"
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


def spans_text(person, extra=(), now=None):
    """在籍の履歴を「2007〜2025 巨人」のように縮める（育成は（育成）と添える）。
    extra：名簿にまだ無い年の在籍（成績・球団の選手一覧から分かるもの）[[年, 球団, 区分]]。
    now：いまの年度。その年度まで続いている在籍は「2007〜 巨人」とする"""
    spans = list(person["spans"])
    for s in extra:
        if not any(y == s[0] and t == s[1] for y, t, _ in spans):
            spans.append(list(s))
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
    def one(a, b, names, ik):
        n = "・".join(names) + ("（育成）" if ik else "")
        if b == now:
            return f"{a}〜 {n}"
        return f"{a}〜{b} {n}" if a != b else f"{a} {n}"
    return "、".join(one(a, b, names, ik) for a, b, _, names, ik in items)


TEAMMATES = 20        # 選手ページに載せるチームメイトの人数（出場の多い順）


def list_order(e):
    """一覧（/player/）と同じ並び：50音の行 → 外国出身 → その他、行の中は読みの順"""
    slugs = [s for s, _, _ in ROWS] + ["foreign", "other"]
    return (slugs.index(row_of(e["kana"]) or "other"), sort_kana(e["kana"]) or "ん", e["name"])


_REL = {}


def related_html(pid, entries, data, picks):
    """選手ページの下に付ける、ほかの選手ページへのリンク。
    前後の選手（一覧の並び）・同期入団（同じ年・同じ球団の指名）・最後の年のチームメイト。
    どの選手ページからでも、ほかの選手ページをたどれるようにする（検索エンジンが見つけやすくなる）"""
    if not _REL:
        order = sorted(entries, key=list_order)
        _REL["pos"] = {e["pid"]: i for i, e in enumerate(order)}
        _REL["order"] = order
        _REL["name"] = {e["pid"]: e["name"] for e in entries}
        mates = defaultdict(dict)                  # (年, 球団) → {pid: 出場}
        for q, (_, _, bat, pit, _) in data.items():
            for r in bat + pit:
                for t in r["teams"]:
                    mates[(r["y"], franchise(t))][q] = max(mates[(r["y"], franchise(t))].get(q, 0), r["g"])
        _REL["mates"] = mates
        classes = defaultdict(list)                # (指名の年, 球団) → pid
        for q, ps in picks.items():
            for p in ps:
                if q in data:
                    classes[(p["year"], p["team"])].append((p["ikusei"], p["round"] or 0, q))
        _REL["classes"] = classes

    def link(q):
        return f'<a href="/player/{q}/">{esc(disp(_REL["name"][q]))}</a>'

    parts = []
    order, i = _REL["order"], _REL["pos"][pid]
    nav = []
    if i > 0:
        nav.append(f'<span>前の選手：{link(order[i - 1]["pid"])}</span>')
    if i + 1 < len(order):
        nav.append(f'<span>次の選手：{link(order[i + 1]["pid"])}</span>')
    for p in picks.get(pid, []):
        same = [q for _, _, q in sorted(_REL["classes"].get((p["year"], p["team"]), [])) if q != pid]
        if same:
            parts.append(f'<h3>{p["year"]}年ドラフトで{esc(p["team"])}に指名された同期</h3>'
                         f'<p class="rel">{"・".join(link(q) for q in same)}</p>')
    person, profile, bat, pit, seen = data[pid]
    last = max(bat + pit, key=lambda r: r["y"])
    team = last["teams"][-1]
    ms = _REL["mates"].get((last["y"], franchise(team)), {})
    top = sorted((q for q in ms if q != pid), key=lambda q: -ms[q])[:TEAMMATES]
    if top:
        parts.append(f'<h3>{last["y"]}年の{esc(team)}のチームメイト（出場の多い順）</h3>'
                     f'<p class="rel">{"・".join(link(q) for q in top)}</p>')
    return ('<section class="related"><h2>ほかの選手</h2>' + "".join(parts)
            + (f'<p class="pn">{"".join(nav)}</p>' if nav else "") + "</section>")


def pick_text(p):
    lab = bd.pick_label(p)
    return f"{p['year']}年 {p['team']} {'育成' if p['ikusei'] else ''}{lab}"


TREND_MIN_PA = 50      # 年度別の推移で、OPS を点にする最低の打席（少ないと極端な値になる）
TREND_MIN_OUTS = 30    # 防御率を点にする最低のアウト数（10回）


def trend_html(bat, pit, kind):
    """年度別の推移のグラフ（WAR と、野手は OPS・投手は防御率）。
    描くのは /player/chart.js。ページには年ごとの数字だけを置く（全選手ぶんの容量を抑えるため）"""
    years = sorted({r["y"] for r in bat + pit})
    if len(years) < 2:
        return ""
    war, val = defaultdict(float), {}
    has_war = set()
    for r in bat + pit:
        if r["src"] == "calc" and r["war"] is not None:
            war[r["y"]] += r["war"]
            has_war.add(r["y"])
    if kind == "p":
        for r in pit:
            if r["outs"] >= TREND_MIN_OUTS:
                val[r["y"]] = round(pit_rates(r)[0], 2)
    else:
        for r in bat:
            if r["pa"] >= TREND_MIN_PA:
                val[r["y"]] = round(bat_rates(r)[3], 3)
    if not has_war and not val:
        return ""
    rows = [[y, round(war[y], 1) if y in has_war else None, val.get(y)] for y in years]
    data = json.dumps(rows, separators=(",", ":"))
    label = "防御率" if kind == "p" else "OPS"
    cond = f"{TREND_MIN_OUTS // 3}回以上投げた年" if kind == "p" else f"{TREND_MIN_PA}打席以上の年"
    return (f'<h2>年度別の推移</h2>'
            f'<div class="trend" data-kind="{kind}" data-rows="{esc(data)}">'
            f'<figure class="tchart" data-series="war"><figcaption>簡易WAR</figcaption></figure>'
            f'<figure class="tchart" data-series="val"><figcaption>{label}'
            f'<span>（{cond}）</span></figcaption></figure></div>')


def render_player(pid, person, display_name, seen, bat, pit, picks, profile, as_of_text, final, related="", fld=None,
                  cur=None, cur_year=None):
    """cur：球団の選手一覧で、いま在籍している球団と育成か (球団, 育成か)。退団・引退していれば None。
    cur_year：その選手一覧の年度（一覧が無いときは None で、成績だけで判断する）"""
    name = disp(person["name"])
    kana = clean_kana((profile or {}).get("kana", ""))
    kind = kind_of(bat, pit)
    last_row = max(bat + pit, key=lambda r: r["y"])
    last_team = last_row["teams"][-1]
    team_now = cur[0] if cur else last_team
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
    if cur:
        dl.append(("所属", f"{cur[0]}{'（育成）' if cur[1] else ''}"))
    else:
        dl.append(("所属", f"{last_team}（{last}年）" if cur_year is None else f"{last_team}（{last}年まで）"))
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
    # 名簿にまだ無い年の在籍は、成績の球団と、球団の選手一覧（いまの在籍）で補う
    max_span = max((y for y, _, _ in person["spans"]), default=0)
    extra = sorted({(r["y"], t) for r in bat + pit if r["y"] > max_span for t in r["teams"]})
    extra = [[y, t, ""] for y, t in extra]
    if cur_year is None:
        now = last if last > max_span else None
    elif cur:
        extra.append([cur_year, cur[0], "育" if cur[1] else ""])
        now = cur_year
    else:
        now = None
    dl.append(("在籍", esc(spans_text(person, extra, now))))

    trend = trend_html(bat if show_bat else [], pit, kind)

    title = f"{name}の成績・WAR｜年度別成績と通算（{team_now}）"
    desc = (f"{name}（{team_now}）の{first}〜{last}年の年度別成績と通算成績。{summary}。"
            f"wOBA・wRC+・FIPなどのセイバー指標と簡易WAR（{war_note or '通算'}{f1(war)}）も年ごとに掲載。")
    status = f"成績は{as_of_text}{'' if final else '時点'}までの一軍公式戦です。"
    body = [f'<p class="stamp">{esc(status)}</p>',
            '<div class="cards">' + "".join(f'<div class="card"><div class="k">{esc(k)}</div><div class="v">{esc(v)}</div></div>'
                                            for k, v in cards) + "</div>",
            '<h2>プロフィール</h2><dl class="prof">'
            + "".join(f"<dt>{esc(k)}</dt><dd>{v if k in ('ドラフト', '登録名・旧名', '在籍') else esc(v)}</dd>" for k, v in dl)
            + "</dl>"]
    if trend:
        body.append(trend)
    if pit:
        body.append(f"<h2>投手成績（年度別）</h2>{pit_table(pit)}")
    if show_bat:
        body.append(f"<h2>打撃成績（年度別）</h2>{bat_table(bat)}")
    if fld:
        body.append(f"<h2>守備成績（年度別）</h2>{fld_table(fld)}")
    notes = ["簡易WARは、打撃・盗塁・守備位置・代替水準（投手はFIP）から計算したもので、"
             "守備の上手さ（UZR）や球場の補正は入っていません（<a href=\"/war/\">計算方法</a>）。"]
    if fld:
        notes.append("守備成績はNPB公式の守備部門の記録（2005年以降・一軍・投手を除く）です。守備率は（刺殺＋補殺）÷（刺殺＋補殺＋失策）です。")
    if first < 2005:
        notes.append("2004年以前の成績はNPB公式の記録です。wOBA・wRC+・FIP・WARは2005年以降だけ計算しています。")
    notes.append("複数の球団に在籍した年は、その年の合計です。守備位置は最も多く守った位置です。")
    body.append('<p class="note">' + "<br>".join("・" + n for n in notes) + "</p>")
    body.append(related)
    body.append(f'<p class="links"><a href="/saber/?k={"pit" if kind == "p" else "bat"}&amp;year={last}">'
                f'{last}年のセイバーメトリクス ランキング</a>　<a href="/player/">選手一覧</a></p>')

    crumb = f'<script> const BREADCRUMB_EXTRA = {{ name: "{esc(name)}", url: "/player/{pid}/" }}; </script>'
    if trend:
        crumb += '\n<script src="/player/chart.js" defer></script>'
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


POS_GROUP = {"捕": "捕手", "一": "内野手", "二": "内野手", "三": "内野手", "遊": "内野手", "外": "外野手"}


def pos_group(bat, pit):
    """投手・捕手・内野手・外野手（最も多く守った位置の組）"""
    if kind_of(bat, pit) == "p":
        return "投手"
    cnt = defaultdict(int)
    for r in bat:
        g = POS_GROUP.get(r.get("pos") or "")
        if g:
            cnt[g] += r["g"]
    return max(cnt, key=cnt.get) if cnt else "野手"


def kana_parts(kana):
    """読み → (苗字, 名前) のひらがな。外国出身の選手は「名前・苗字」の順なので入れ替える"""
    k = clean_kana(kana)
    parts = [x for x in re.split(r"[・･\s　]+", k) if x]
    if not parts:
        return "", ""
    if is_foreign_kana(kana):
        return hira(parts[-1]), hira("".join(parts[:-1]))
    return hira(parts[0]), hira("".join(parts[1:]))


def search_data(entries, latest):
    """選手一覧の検索用（/player/players.json）。cur はいま在籍している球団（退団・引退していれば空）"""
    cols = ["id", "name", "kana", "sei", "mei", "names", "teams", "first", "last", "pos", "hand", "school", "active", "cur"]
    rows = []
    for e in sorted(entries, key=lambda e: (sort_kana(e["kana"]) or "ん", e["name"])):
        sei, mei = kana_parts(e["kana"])
        active = bool(e["cur"]) if e["cur"] is not None else e["last"] == latest
        rows.append([e["pid"], disp(e["name"]), clean_kana(e["kana"]), sei, mei, e["names"], e["teams"],
                     e["first"], e["last"], e["pos"], e["hand"], e["school"], 1 if active else 0, e["cur"] or ""])
    return json.dumps({"latest": latest, "cols": cols, "rows": rows}, ensure_ascii=False, separators=(",", ":")) + "\n"


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
            '年度別の成績と通算成績、wOBA・wRC+・FIPなどのセイバー指標と簡易WAR、ドラフトの指名、登録名の変遷をまとめています。'
            '名前・読み・出身校や、球団・ポジションで探せるほか、しりとりで使える選手も探せます。</p>'
            + SEARCH_HTML +
            f'<h2 class="list-head">50音順の一覧</h2><nav class="kana-nav">{nav}</nav>' + "".join(parts)
            + '<script src="/player/search.js" defer></script>')
    return page("プロ野球 選手一覧・選手検索｜年度別成績とWAR、しりとり検索も【2005年〜】",
                f"2005年以降に一軍に出場したプロ野球選手{len(entries)}人の、年度別成績・通算成績とセイバー指標（wOBA・wRC+・FIP・簡易WAR）を選手ごとにまとめたページの一覧です。",
                "/player/", "プロ野球 選手一覧", body)


SEARCH_HTML = """
<section class="search" id="search" aria-label="選手を探す">
  <input id="q" type="search" placeholder="名前・読み・登録名・出身校（例：さかもと、大阪桐蔭）" autocomplete="off">
  <div class="filters">
    <label>球団<select id="f-team"><option value="">すべて</option></select></label>
    <label>ポジション<select id="f-pos"><option value="">すべて</option><option>投手</option><option>捕手</option><option>内野手</option><option>外野手</option></select></label>
    <label>投げ<select id="f-t"><option value="">すべて</option><option value="右投">右投げ</option><option value="左投">左投げ</option></select></label>
    <label>打席<select id="f-b"><option value="">すべて</option><option value="右打">右打ち</option><option value="左打">左打ち</option><option value="両打">両打ち</option></select></label>
    <label>在籍<select id="f-act"><option value="">すべて</option><option value="1">現役（いまの所属）</option><option value="0">引退・退団</option></select></label>
  </div>
  <fieldset class="shiritori">
    <legend>しりとりで探す</legend>
    <label>読むところ<select id="s-part"><option value="full">フルネーム</option><option value="sei">苗字</option><option value="mei">名前</option></select></label>
    <label>最初の文字<input id="s-head" maxlength="2" inputmode="kana" placeholder="例：と"></label>
    <label>最後の文字<input id="s-tail" maxlength="2" inputmode="kana" placeholder="例：た"></label>
    <label class="check"><input type="checkbox" id="s-dak">濁点・半濁点を区別しない</label>
    <label class="check"><input type="checkbox" id="s-non">「ん」で終わる選手を除く</label>
    <p class="hint">小さい字は大きい字（しょ→よ）、最後の「ー」は前の音の母音（ルー→う）として数えます。外国出身の選手のフルネームは「名前・苗字」の順です。</p>
  </fieldset>
  <p class="count" id="count">読み込み中…</p>
  <ul class="results" id="results"></ul>
  <button type="button" class="more" id="more" hidden>もっと見る</button>
</section>
"""

SEARCH_JS = r"""// 選手一覧の検索（npb/build_players.py が書き出す。/player/players.json を読む）
(function(){
  "use strict";
  var $ = function(id){ return document.getElementById(id); };
  var PAGE = 60;
  var SMALL = {"ぁ":"あ","ぃ":"い","ぅ":"う","ぇ":"え","ぉ":"お","ゃ":"や","ゅ":"ゆ","ょ":"よ","っ":"つ","ゎ":"わ","ゕ":"か","ゖ":"け"};
  var VOWEL = {};
  ["あかさたなはまやらわがざだばぱぁゃゎ", "いきしちにひみりぎじぢびぴぃ", "うくすつぬふむゆるぐずづぶぷぅゅっゔ",
   "えけせてねへめれげぜでべぺぇ", "おこそとのほもよろをごぞどぼぽぉょ"].forEach(function(row, i){
    for (var j = 0; j < row.length; j++) VOWEL[row[j]] = "あいうえお"[i];
  });
  function hira(s){ return String(s || "").replace(/[ァ-ヶ]/g, function(c){ return String.fromCharCode(c.charCodeAt(0) - 0x60); }); }
  function plain(c){ return c.normalize("NFD").replace(/[゙゚]/g, "").normalize("NFC"); }
  function norm(s){ return hira(String(s || "").normalize("NFKC")).replace(/[\s・･.．]/g, "").toLowerCase(); }
  function kanaOnly(s){ return hira(s).replace(/[^ぁ-ゖー]/g, ""); }
  function big(c){ return SMALL[c] || c; }
  function head(s){ s = kanaOnly(s); return big(s.charAt(0)); }
  function tail(s){
    s = kanaOnly(s);
    var c = s.charAt(s.length - 1);
    if (c === "ー") c = VOWEL[s.charAt(s.length - 2)] || "";
    return big(c);
  }
  function letter(v, dak){ var c = big(kanaOnly(v).charAt(0)); return dak ? plain(c) : c; }

  var data = null, list = [], shown = PAGE;
  function reading(o, part){ return part === "sei" ? o.sei : part === "mei" ? o.mei : o.kana; }

  function run(){
    if (!data) return;
    var q = norm($("q").value), team = $("f-team").value, pos = $("f-pos").value,
        t = $("f-t").value, b = $("f-b").value, act = $("f-act").value,
        part = $("s-part").value, dak = $("s-dak").checked, non = $("s-non").checked,
        h = letter($("s-head").value, dak), tl = letter($("s-tail").value, dak);
    var fix = function(c){ return dak ? plain(c) : c; };
    list = data.filter(function(o){
      // 在籍を「現役」にしたときは、いまその球団にいる選手だけ（移籍・退団した選手は除く）
      if (team && (act === "1" ? o.cur !== team : o.teams.indexOf(team) < 0)) return false;
      if (pos && o.pos !== pos) return false;
      if (t && o.hand.indexOf(t) !== 0) return false;
      if (b && o.hand.indexOf(b) < 0) return false;
      if (act !== "" && String(o.active) !== act) return false;
      if (q && o.key.indexOf(q) < 0) return false;
      var r = reading(o, part);
      if ((h || tl || non) && !kanaOnly(r)) return false;
      if (h && fix(head(r)) !== h) return false;
      if (tl && fix(tail(r)) !== tl) return false;
      if (non && tail(r) === "ん") return false;
      return true;
    });
    shown = PAGE;
    render();
    save();
  }

  function esc(s){ return String(s).replace(/[&<>"]/g, function(c){ return {"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]; }); }

  function render(){
    var part = $("s-part").value, sh = $("s-head").value || $("s-tail").value;
    var act = list.filter(function(o){ return o.active; }).length;
    $("count").textContent = list.length + "人" + (list.length ? "（うち現役 " + act + "人）" : "") +
      (list.length > shown ? "　上から" + shown + "人を表示" : "");
    $("results").innerHTML = list.slice(0, shown).map(function(o){
      var r = reading(o, part), last = tail(r);
      var yrs = o.first === o.last ? o.first : o.first + "〜" + o.last;
      return '<li><a href="/player/' + o.id + '/">' + esc(o.name) + '</a>' +
        (o.names.length ? '<span class="al">（' + esc(o.names.join("／")) + '）</span>' : '') +
        '<span class="kn">' + esc(r || o.kana) + (sh && last ? ' <b>' + esc(last) + '</b>' : '') + '</span>' +
        '<span class="mt">' + esc(o.pos) + '・' + esc(o.teams.join("→")) + '・' + yrs + (o.active ? '・現役' + (o.cur && o.cur !== o.teams[o.teams.length - 1] ? '（いま' + esc(o.cur) + '）' : '') : '') + '</span>' +
        (last && last !== "ん" ? '<button type="button" class="next" data-c="' + esc(last) + '">「' + esc(last) + '」から続ける</button>' : '') +
        '</li>';
    }).join("");
    $("more").hidden = list.length <= shown;
  }

  function save(){
    var p = new URLSearchParams();
    [["q","q"],["team","f-team"],["pos","f-pos"],["t","f-t"],["b","f-b"],["act","f-act"],["part","s-part"],["head","s-head"],["tail","s-tail"]].forEach(function(x){
      var v = $(x[1]).value; if (v && !(x[0] === "part" && v === "full")) p.set(x[0], v);
    });
    if ($("s-dak").checked) p.set("dak", "1");
    if ($("s-non").checked) p.set("non", "1");
    var s = p.toString();
    try { history.replaceState(null, "", location.pathname + (s ? "?" + s : "") + (s ? "#search" : "")); } catch (e) {}
  }

  function load(){
    var p = new URLSearchParams(location.search);
    [["q","q"],["team","f-team"],["pos","f-pos"],["t","f-t"],["b","f-b"],["act","f-act"],["part","s-part"],["head","s-head"],["tail","s-tail"]].forEach(function(x){
      if (p.get(x[0])) $(x[1]).value = p.get(x[0]);
    });
    $("s-dak").checked = p.get("dak") === "1";
    $("s-non").checked = p.get("non") === "1";
  }

  ["q","s-head","s-tail"].forEach(function(id){ $(id).addEventListener("input", run); });
  ["f-team","f-pos","f-t","f-b","f-act","s-part","s-dak","s-non"].forEach(function(id){ $(id).addEventListener("change", run); });
  $("more").addEventListener("click", function(){ shown += PAGE * 2; render(); });
  $("results").addEventListener("click", function(e){
    var btn = e.target.closest("button.next");
    if (!btn) return;
    $("s-head").value = btn.getAttribute("data-c");
    $("s-tail").value = "";
    run();
    $("search").scrollIntoView({behavior: "smooth", block: "start"});
  });

  fetch("/player/players.json").then(function(r){ return r.json(); }).then(function(d){
    var c = {}; d.cols.forEach(function(k, i){ c[k] = i; });
    data = d.rows.map(function(r){
      var o = {}; d.cols.forEach(function(k){ o[k] = r[c[k]]; });
      o.key = norm([o.name, o.kana, o.names.join(" "), o.school].join(" "));
      return o;
    });
    var teams = {};
    data.forEach(function(o){ o.teams.forEach(function(t){ teams[t] = 1; }); });
    var order = ["巨人","阪神","DeNA","横浜","広島","中日","ヤクルト","ソフトバンク","日本ハム","ロッテ","西武","楽天","オリックス"];
    Object.keys(teams).sort(function(a, b){ return (order.indexOf(a) + 99) % 99 - (order.indexOf(b) + 99) % 99; }).forEach(function(t){
      var op = document.createElement("option"); op.textContent = t; $("f-team").appendChild(op);
    });
    load();
    run();
  }).catch(function(){ $("count").textContent = "データを読み込めませんでした。"; });
})();
"""


CHART_JS = r"""// 選手ページの「年度別の推移」（npb/build_players.py が書き出す）。
// .trend の data-rows に [年, WAR, OPSか防御率] が並んでいる。null は出場なし・対象外
(function () {
  var NS = "http://www.w3.org/2000/svg";
  function el(tag, attrs, text) {
    var e = document.createElementNS(NS, tag);
    for (var k in attrs) e.setAttribute(k, attrs[k]);
    if (text != null) e.textContent = text;
    return e;
  }
  function nice(lo, hi, n) {
    var span = hi - lo || 1, raw = span / n, mag = Math.pow(10, Math.floor(Math.log10(raw)));
    var step = [1, 2, 2.5, 5, 10].map(function (m) { return m * mag; }).find(function (s) { return s >= raw; });
    return { lo: Math.floor(lo / step) * step, hi: Math.ceil(hi / step) * step, step: step };
  }
  function fmt(v, series, kind) {
    if (series === "war") return v.toFixed(1);
    return kind === "p" ? v.toFixed(2) : v.toFixed(3).replace(/^0/, "");
  }
  function draw(fig, rows, series, kind) {
    var idx = series === "war" ? 1 : 2;
    var pts = rows.filter(function (r) { return r[idx] != null; });
    if (!pts.length) {
      var p = document.createElement("p");
      p.className = "none";
      p.textContent = "対象の年がありません";
      fig.appendChild(p);
      return;
    }
    // 画面の幅のまま描く（縮小すると、スマホで目盛りの文字が小さくなりすぎる）
    var W = Math.max(280, Math.round(fig.clientWidth - 24)), H = 190, L = 40, R = 8, T = 12, B = 26;
    var y0 = rows[0][0], y1 = rows[rows.length - 1][0], n = y1 - y0 + 1;
    var vals = pts.map(function (r) { return r[idx]; });
    var lo = Math.min.apply(null, vals), hi = Math.max.apply(null, vals);
    if (series === "war") { lo = Math.min(lo, 0); hi = Math.max(hi, 1); }
    else if (kind === "p") { lo = Math.min(lo, 2); hi = Math.max(hi, 4); }
    else { lo = Math.min(lo, .6); hi = Math.max(hi, .8); }
    var sc = nice(lo, hi, 4);
    var cw = (W - L - R) / n;
    function X(y) { return L + (y - y0 + .5) * cw; }
    function Y(v) { return T + (sc.hi - v) / (sc.hi - sc.lo) * (H - T - B); }
    var svg = el("svg", { viewBox: "0 0 " + W + " " + H, role: "img" });
    for (var v = sc.lo; v <= sc.hi + 1e-9; v += sc.step) {
      var yy = Y(v), zero = series === "war" && Math.abs(v) < 1e-9;
      svg.appendChild(el("line", { x1: L, x2: W - R, y1: yy, y2: yy, stroke: zero ? "#9ca3af" : "#e5e7eb", "stroke-width": zero ? 1.2 : 1 }));
      svg.appendChild(el("text", { x: L - 6, y: yy + 3.5, "text-anchor": "end", "font-size": 10, fill: "#6b7280" }, fmt(v, series, kind)));
    }
    // 年のラベル。多いときは間引く
    var fit = Math.max(1, Math.floor((W - L - R) / 34));   // 年のラベルが入る数
    var every = n <= fit ? 1 : n <= fit * 2 ? 2 : n <= fit * 3 ? 3 : 5;
    for (var y = y0; y <= y1; y++) {
      if ((y - y0) % every && y !== y1) continue;
      if (y !== y1 && y1 - y < every && (y - y0) % every === 0 && y !== y0) continue;
      svg.appendChild(el("text", { x: X(y), y: H - 8, "text-anchor": "middle", "font-size": 10, fill: "#6b7280" },
        n > fit / 1.6 ? "'" + String(y).slice(2) : String(y)));
    }
    var best = pts.reduce(function (a, r) {
      if (!a) return r;
      return (series === "val" && kind === "p") ? (r[idx] < a[idx] ? r : a) : (r[idx] > a[idx] ? r : a);
    }, null);
    if (series === "war") {
      var bw = Math.max(2, Math.min(22, cw * .64));
      pts.forEach(function (r) {
        var v = r[1], top = Y(Math.max(v, 0)), h = Math.max(1, Math.abs(Y(v) - Y(0)));
        var b = el("rect", { x: X(r[0]) - bw / 2, y: top, width: bw, height: h, rx: 2,
          fill: v < 0 ? "#dc2626" : (r === best ? "#1d4ed8" : "#60a5fa") });
        b.appendChild(el("title", {}, r[0] + "年 WAR " + v.toFixed(1)));
        svg.appendChild(b);
      });
    } else {
      // 出場のない年・対象外の年で線を切る
      // （MLB 在籍などで年が飛んでいるところも切る）
      var seg = [], segs = [];
      rows.forEach(function (r) {
        var gap = seg.length && r[0] - seg[seg.length - 1][0] > 1;
        if (r[2] == null || gap) { if (seg.length) segs.push(seg); seg = []; }
        if (r[2] != null) seg.push(r);
      });
      if (seg.length) segs.push(seg);
      segs.forEach(function (s) {
        if (s.length < 2) return;
        svg.appendChild(el("polyline", { points: s.map(function (r) { return X(r[0]) + "," + Y(r[2]); }).join(" "),
          fill: "none", stroke: "#0f766e", "stroke-width": 2, "stroke-linejoin": "round" }));
      });
      pts.forEach(function (r) {
        var c = el("circle", { cx: X(r[0]), cy: Y(r[2]), r: r === best ? 4 : 3,
          fill: r === best ? "#0f766e" : "#fff", stroke: "#0f766e", "stroke-width": 2 });
        c.appendChild(el("title", {}, r[0] + "年 " + (kind === "p" ? "防御率 " : "OPS ") + fmt(r[2], "val", kind)));
        svg.appendChild(c);
      });
    }
    var cap = fig.querySelector("figcaption");
    var b = document.createElement("b");
    b.textContent = (series === "war" ? "最高 " : "ベスト ") + best[0] + "年 " + fmt(best[idx], series, kind);
    cap.appendChild(b);
    fig.appendChild(svg);
  }
  document.querySelectorAll(".trend").forEach(function (box) {
    var rows = JSON.parse(box.dataset.rows);
    var kind = box.dataset.kind;
    box.querySelectorAll(".tchart").forEach(function (fig) { draw(fig, rows, fig.dataset.series, kind); });
  });
})();
"""


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
.trend{ display:grid; grid-template-columns:repeat(auto-fit, minmax(min(100%, 420px), 1fr)); gap:10px; }
.tchart{ margin:0; background:#fff; border:1px solid var(--line); border-radius:12px; padding:10px 12px 6px; min-height:200px; }
.tchart figcaption{ font-size:0.86rem; font-weight:800; color:var(--ink-strong); }
.tchart figcaption span{ font-weight:400; font-size:0.76rem; color:var(--ink-mute); }
.tchart figcaption b{ float:right; font-size:0.78rem; font-weight:700; color:var(--ink-sub); }
.tchart svg{ display:block; width:100%; height:auto; overflow:visible; font-family:inherit; }
.tchart .none{ margin:40px 0; text-align:center; font-size:0.85rem; color:var(--ink-mute); }
.related h3{ margin:14px 0 4px; font-size:0.95rem; color:var(--ink-strong); }
.related .rel{ margin:0; font-size:0.9rem; line-height:1.9; }
.related .pn{ display:flex; flex-wrap:wrap; justify-content:space-between; gap:6px 16px; margin:16px 0 0;
              padding-top:10px; border-top:1px solid var(--line); font-size:0.9rem; }
.links{ font-size:0.92rem; }
.kana-nav{ display:flex; flex-wrap:wrap; gap:6px; margin:0 0 8px; }
.kana-nav a{ padding:4px 12px; border:1px solid var(--line); border-radius:999px; background:#fff; text-decoration:none; font-size:0.9rem; }
ul.plist{ list-style:none; margin:0; padding:0; display:grid; grid-template-columns:repeat(auto-fill, minmax(210px, 1fr)); gap:2px 12px; }
ul.plist li{ padding:3px 0; border-bottom:1px solid var(--line-soft); font-size:0.92rem; }
ul.plist li span{ display:block; font-size:0.74rem; color:var(--ink-mute); }
footer.disclaimer{ margin-top:22px; font-size:0.82rem; color:var(--ink-mute); }
.search{ background:#fff; border:1px solid var(--line); border-radius:14px; padding:14px 16px; margin:14px 0 8px; scroll-margin-top:10px; }
.search input[type=search]{ width:100%; font:inherit; font-size:1rem; padding:9px 12px; border:1px solid var(--line); border-radius:10px; }
.search .filters, .search .shiritori{ display:flex; flex-wrap:wrap; gap:8px 12px; margin:10px 0 0; }
.search label{ display:flex; flex-direction:column; gap:2px; font-size:0.78rem; font-weight:700; color:var(--ink-sub); }
.search select, .search .shiritori input[type=text], .search .shiritori input:not([type]), .search .shiritori input[inputmode]{
    font:inherit; font-size:0.92rem; padding:6px 8px; border:1px solid var(--line); border-radius:8px; background:#fff; }
.search .shiritori input[inputmode]{ width:4.5em; text-align:center; font-size:1.05rem; }
.search .shiritori{ border:1px dashed var(--line); border-radius:12px; padding:6px 12px 10px; }
.search legend{ font-size:0.86rem; font-weight:800; color:var(--ink-strong); padding:0 4px; }
.search label.check{ flex-direction:row; align-items:center; gap:6px; font-size:0.86rem; padding-top:14px; }
.search .hint{ flex-basis:100%; margin:2px 0 0; font-size:0.76rem; color:var(--ink-mute); }
.search .count{ margin:12px 0 6px; font-size:0.9rem; font-weight:700; color:var(--ink-sub); }
ul.results{ list-style:none; margin:0; padding:0; display:grid; grid-template-columns:repeat(auto-fill, minmax(260px, 1fr)); gap:6px 14px; }
ul.results li{ border-bottom:1px solid var(--line-soft); padding:6px 0; }
ul.results li a{ font-weight:700; }
ul.results .al{ font-size:0.8rem; color:var(--ink-sub); }
ul.results .kn, ul.results .mt{ display:block; font-size:0.78rem; color:var(--ink-mute); }
ul.results .kn b{ color:var(--accent); font-size:0.95rem; }
ul.results button.next{ margin-top:3px; font:inherit; font-size:0.76rem; padding:2px 10px; border:1px solid var(--line);
    border-radius:999px; background:var(--tint); color:var(--ink-sub); cursor:pointer; }
ul.results button.next:hover{ border-color:var(--accent); color:var(--accent); }
.search .more{ display:block; margin:12px auto 0; font:inherit; font-size:0.9rem; font-weight:700; padding:8px 28px;
    border:1px solid #bfdbfe; border-radius:999px; background:#eff6ff; color:#1d4ed8; cursor:pointer; }
.search .more:hover{ background:#dbeafe; border-color:#93c5fd; }
.search .more[hidden]{ display:none; }
h2.list-head{ margin-top:34px; }
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
    # 全ページを作り直すのは、最新のシーズンが終わってまだ作っていないとき（と --force）。
    # それ以外は、新しい選手と在籍が変わった選手のページだけ（毎日）
    full = args.force or not built or (final and not (built.get("season") == latest and built.get("final")))

    if not args.no_fetch:
        # 新しく一軍に出た選手（新人など）の読み仮名・プロフィールを公式ページから取る
        people0 = People(data / "register.json")
        by_pid0, _, _ = bd.load_seasons_people(data, league, people0)
        got = player_profile.fill_missing(data / "player_profiles.json",
                                          [p for p in by_pid0 if not p.startswith("r")])
        print(f"player: プロフィールを{got}人分取得")
    people, by_pid, picks, profiles, stores, last_season, fielding = load(data, league)
    as_of = st_latest.get("as_of") or f"{latest}-12-31"
    d = datetime.strptime(as_of, "%Y-%m-%d")
    as_of_text = f"{d.year}年{d.month}月{d.day}日" if not final else f"{latest}年シーズン終了"

    out.mkdir(parents=True, exist_ok=True)
    (out / "player.css").write_text(CSS, encoding="utf-8")
    entries = []
    data = {}
    for pid, rows in by_pid.items():
        if pid.startswith("r") or pid not in people.by_pid:
            continue
        person = people.by_pid[pid]
        profile = profiles.get(pid)
        bat, pit = seasons_of(pid, by_pid, profile)
        if not bat and not pit:
            continue
        seen = people.seen_names.get(pid, [])
        data[pid] = (person, profile, bat, pit, seen)
        years = [r["y"] for r in bat + pit]
        last_row = max(bat + pit, key=lambda r: r["y"])
        teams = []
        for r in sorted(bat + pit, key=lambda r: r["y"]):
            for t in r["teams"]:
                if t not in teams:
                    teams.append(t)
        # 外国出身の選手の「Ｔ．バティスタ」と「バティスタ」のような、頭文字だけの違いは添えない
        names = [n for n in list(person["alias"]) + seen if key(n) != key(person["name"])
                 and not (is_foreign_style(person["name"]) and key(n) in key(person["name"]))]
        cur = people.current.get(pid)
        entries.append({"pid": pid, "name": person["name"], "kana": (profile or {}).get("kana", ""),
                        "team": cur[0] if cur else last_row["teams"][-1], "first": min(years), "last": max(years),
                        "cur": (cur[0] if cur else "") if people.current_year else None,
                        "teams": teams, "pos": pos_group(bat, pit), "hand": (profile or {}).get("profile", {}).get("投打", ""),
                        "school": (profile or {}).get("profile", {}).get("経歴", ""),
                        "names": list(dict.fromkeys(disp(n) for n in names))})
    def state(pid):
        cur = people.current.get(pid)
        return (cur[0] + ("育" if cur[1] else "")) if cur else ""

    old_pids, old_state = set(built.get("pids", [])), built.get("state", {})
    no_prof = set(built.get("noprof", []))   # プロフィール（読み仮名など）を取れないまま作ったページ
    if full:
        todo = entries
    else:
        todo = [e for e in entries if e["pid"] not in old_pids or old_state.get(e["pid"], "") != state(e["pid"])
                or (e["pid"] in no_prof and profiles.get(e["pid"]))]
    for e in todo:
        pid = e["pid"]
        person, profile, bat, pit, seen = data[pid]
        html_text = render_player(pid, person, people.display(pid), seen, bat, pit, picks.get(pid, []),
                                  profile, as_of_text, final, related_html(pid, entries, data, picks),
                                  fielding.get(pid), people.current.get(pid), people.current_year)
        d_ = out / pid
        d_.mkdir(exist_ok=True)
        (d_ / "index.html").write_text(html_text, encoding="utf-8")
    pids = sorted(e["pid"] for e in entries)
    if full or set(pids) != old_pids:
        (out / "index.html").write_text(index_page(entries, latest), encoding="utf-8")
    (out / "players.json").write_text(search_data(entries, latest), encoding="utf-8")
    (out / "search.js").write_text(SEARCH_JS, encoding="utf-8")
    (out / "chart.js").write_text(CHART_JS, encoding="utf-8")
    keep = {"season": latest, "final": final, "as_of": as_of} if full else \
        {k: built[k] for k in ("season", "final", "as_of")}
    built_path.write_text(json.dumps({**keep, "pids": pids,
                                      "state": {e["pid"]: state(e["pid"]) for e in entries if state(e["pid"])},
                                      "noprof": sorted(e["pid"] for e in entries if not profiles.get(e["pid"]))},
                                     ensure_ascii=False) + "\n", encoding="utf-8")
    if full:
        print(f"player: {len(entries)}人（{latest}年{'シーズン終了' if final else 'シーズン途中'}）")
    else:
        print(f"player: 新しい選手・在籍が変わった選手の{len(todo)}ページだけ作成（全ページはシーズン終了時）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
