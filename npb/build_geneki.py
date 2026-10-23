#!/usr/bin/env python3
"""現役ドラフト答え合わせ（/geneki-draft/）：現役ドラフトで移籍した選手の、移籍前と移籍後を比べる。

    python3 npb/build_geneki.py --data npb/data --league war/league.json --out geneki-draft

- 移籍の一覧は npb/data/geneki_draft.json（手で入れる。毎年12月の開催日に、その年の分を足す）
- 選手は在籍者名簿（npb/data/register.json）の「人」に、名前と「指名の年に元の球団にいたこと」で結びつける。
  成績・簡易WARはドラフト答え合わせ（build_draft.py）と同じ集計を使う
- 移籍前は、移籍の年までの3シーズン。移籍後は、移籍の翌年から最新のシーズンまで（移籍先を出た後も含む）
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_draft as bd  # noqa: E402
from build_draft import disp, esc  # noqa: E402
from people import People, franchise, key  # noqa: E402

BEFORE_YEARS = 3     # 移籍前は、移籍の年を含めた直近この年数
GOOD_WAR = 1.0       # 1シーズンでこれ以上のWARなら「主力級のシーズン」と数える
FOOTER = """移籍の一覧はNPB（日本野球機構）の現役ドラフト結果、成績はNPB公式サイトの個人成績をもとに、当サイトが独自に集計したものです。
成績は一軍の公式戦のみです。選手と成績は、NPBの在籍者名簿（在籍した年・球団・改名の履歴）で照合しています。"""


def load_moves(path):
    d = json.loads(path.read_text(encoding="utf-8"))
    moves = {}
    for y, rows in d.items():
        if not y.isdigit():
            continue
        moves[int(y)] = [{"year": int(y), "to": r[0], "name": r[1], "from": r[2], "pos": r[3],
                          "round": r[4] if len(r) > 4 else 1} for r in rows]
    return moves


def find_pid(people, m):
    """名前（登録名だけの選手は下の名前）と、指名の年に元の球団にいたことで、名簿の「人」を探す"""
    k = key(m["name"])
    found = []
    for p in people.players:
        if not p.get("pid"):
            continue
        keys = p.get("keys") or {key(p["name"])}
        if not (k in keys or any(x.endswith(k) for x in keys)):
            continue
        if any(s[0] == m["year"] and franchise(s[1]) == franchise(m["from"]) for s in p["spans"]):
            found.append(p["pid"])
    return found[0] if len(found) == 1 else None


def ra9_war(seasons):
    """投手としての防御率ベース（実際の失点から）のWAR"""
    return round(sum(p.get("war_ra9") or 0 for _, _, p in seasons if p), 1)


def season_war(s):
    _, b, p = s
    return (b["war"] or 0 if b else 0) + (p["war"] or 0 if p else 0)


def name_link(m, has_page):
    n = esc(disp(m["name"]))
    return f'<a class="pl" href="/player/{m["pid"]}/">{n}</a>' if m["pid"] in has_page else n


def move_text(m):
    return f'{m["from"]}→{m["to"]}'


def war_cell(c, played, ra9=None):
    """投手は、防御率ベースのWARを下に添える（下の「投手のWARについて」）"""
    if not played:
        return "―"
    return f'{c["war"]:.1f}' + (f'<span class="ra9">（{ra9:.1f}）</span>' if ra9 is not None else "")


def points(done, latest):
    """見どころ（データから短い文で書く）"""
    pts = []
    ok = [m for m in done if m["pid"]]
    tops = sorted((m for m in ok if m["after"]["years"]), key=lambda m: -m["after"]["war"])
    if tops:
        t = tops[0]
        txt = (f'移籍後に最も活躍しているのは{disp(t["name"])}（{t["year"]}年・{move_text(t)}）で、'
               f'移籍後の通算WARは{t["after"]["war"]:.1f}。移籍前の3年間は{t["before"]["war"]:.1f}だった。')
        if len(tops) > 1 and tops[1]["after"]["war"] > 0:
            s = tops[1]
            txt += f'次いで{disp(s["name"])}（{s["year"]}年・{move_text(s)}）の{s["after"]["war"]:.1f}。'
        pts.append(txt)
    up = [m for m in ok if m["after"]["years"]]
    good = [m for m in ok if m["good"]]
    pts.append(f'{len(ok)}人のうち、移籍後に一軍に出場したのは{len(up)}人。'
               f'1シーズンでWAR{GOOD_WAR:.0f}以上を記録したのは{len(good)}人'
               + (f'（{"・".join(disp(m["name"]) for m in sorted(good, key=lambda m: -m["after"]["war"]))}）' if 0 < len(good) <= 5 else "")
               + "。移籍をきっかけに主力へ定着できたのは、ごく一握りだ。")
    rise = [m for m in up if m["after_per"] > m["before_per"] + 0.3]
    if rise:
        pts.append(f'1シーズンあたりのWARが移籍前より上がったのは{len(rise)}人'
                   f'（{"・".join(disp(m["name"]) for m in sorted(rise, key=lambda m: -(m["after_per"] - m["before_per"]))[:4])}など）。')
    by_year = defaultdict(float)
    for m in ok:
        by_year[m["year"]] += m["after"]["war"]
    if by_year:
        y = max(by_year, key=lambda y: by_year[y])
        pts.append(f'年別では{y}年の移籍組が、移籍後のWAR合計{by_year[y]:.1f}で最も多い。')
    pit = [m for m in ok if m["pos"] == "投手"]
    fld = [m for m in ok if m["pos"] != "投手"]
    if pit and fld:
        pw = sum(m["after"]["war"] for m in pit)
        fw = sum(m["after"]["war"] for m in fld)
        pr = sum(m["after_ra9"] for m in pit)
        pts.append(f'投手は{len(pit)}人で移籍後のWAR合計{pw:.1f}（防御率ベースでは{pr:.1f}）、野手は{len(fld)}人で{fw:.1f}。'
                   + ("野手のほうが、移籍で出番をつかみやすい傾向がある。" if fw / len(fld) > pw / len(pit)
                      else "投手のほうが、移籍で出番をつかみやすい傾向がある。"))
    return pts


def build(moves, by_pid, people, has_page, latest):
    for ms in moves.values():
        for m in ms:
            m["pid"] = find_pid(people, m)
            seasons = by_pid.get(m["pid"], []) if m["pid"] else []
            before = [s for s in seasons if m["year"] - BEFORE_YEARS < s[0] <= m["year"]]
            after = [s for s in seasons if s[0] > m["year"]]
            m["before"] = bd.career({"seasons": before, "pos": m["pos"]})
            m["after"] = bd.career({"seasons": after, "pos": m["pos"]})
            m["pit"] = m["pos"] == "投手"
            m["before_ra9"], m["after_ra9"] = ra9_war(before), ra9_war(after)
            m["after_seasons"] = [(s[0], season_war(s)) for s in sorted(after, key=lambda s: s[0])]
            m["good"] = any(w >= GOOD_WAR for _, w in m["after_seasons"])
            n_after = max(1, latest - m["year"])
            m["before_per"] = m["before"]["war"] / BEFORE_YEARS
            m["after_per"] = m["after"]["war"] / n_after

    done = [m for y in sorted(moves) for m in moves[y] if y < latest]
    missing = [m["name"] for m in done if not m["pid"]]
    if missing:
        print("名簿で見つからない:", "、".join(missing), file=sys.stderr)

    played = [m for m in done if m["pid"] and m["after"]["years"]]
    tops = sorted(played, key=lambda m: -m["after"]["war"])
    good = [m for m in done if m["pid"] and m["good"]]

    # 球団別：獲得した選手と、放出した選手の、移籍後のWAR合計
    led = defaultdict(lambda: {"got": 0.0, "gave": 0.0, "got_n": 0, "gave_n": 0, "best": None})
    for m in done:
        if not m["pid"]:
            continue
        w = m["after"]["war"]
        g = led[m["to"]]
        g["got"] += w
        g["got_n"] += 1
        if g["best"] is None or w > g["best"]["after"]["war"]:
            g["best"] = m
        led[m["from"]]["gave"] += w
        led[m["from"]]["gave_n"] += 1
    ledger = sorted(led.items(), key=lambda kv: -(kv[1]["got"] - kv[1]["gave"]))

    years = sorted(moves)
    first, last_done = min(years), max(y for y in years if y < latest) if done else min(years)
    pts = points(done, latest)

    def best_cell(m):
        return f'{name_link(m, has_page)}（{m["after"]["war"]:.1f}）' if m else "―"

    top_rows = "".join(
        f'<tr><td>{i}</td><td class="nm">{name_link(m, has_page)}</td><td>{m["year"]}年</td>'
        f'<td>{esc(move_text(m))}</td><td>{esc(bd.stat_text(m["after"]))}</td>'
        f'<td class="n">{war_cell(m["before"], True, m["before_ra9"] if m["pit"] else None)}</td>'
        f'<td class="war">{war_cell(m["after"], True, m["after_ra9"] if m["pit"] else None)}</td></tr>'
        for i, m in enumerate(tops[:10], 1))
    led_rows = "".join(
        f'<tr><td>{i}</td><td class="nm">{bd.team_link(t)}</td>'
        f'<td class="n">{v["got"]:.1f}<span class="cnt">（{v["got_n"]}人）</span></td>'
        f'<td class="n">{v["gave"]:.1f}<span class="cnt">（{v["gave_n"]}人）</span></td>'
        f'<td class="war">{v["got"] - v["gave"]:+.1f}</td>'
        f'<td>{best_cell(v["best"])}</td></tr>'
        for i, (t, v) in enumerate(ledger, 1))

    def rows(ms):
        out = []
        for m in ms:
            a, b = m["after"], m["before"]
            per = "".join(f'<span class="ys">{y % 100:02d}年 {w:.1f}</span>' for y, w in m["after_seasons"])
            cls = "" if a["years"] else ' class="none"'
            out.append(
                f'<tr{cls}><td class="nm" data-v="{esc(m["name"])}">{name_link(m, has_page)}'
                + ('<span class="tag">2巡目</span>' if m["round"] == 2 else "")
                + f'<span class="mv">{esc(m["from"])}→<b>{esc(m["to"])}</b></span></td>'
                f'<td data-v="{esc(m["pos"])}">{esc(m["pos"])}</td>'
                f'<td class="war" data-v="{a["war"] if a["years"] else -999}">{war_cell(a, a["years"], m["after_ra9"] if m["pit"] else None)}</td>'
                f'<td class="n" data-v="{b["war"] if b["years"] else -999}">{war_cell(b, b["years"], m["before_ra9"] if m["pit"] else None)}</td>'
                f'<td data-v="{a["war"] if a["years"] else -999}">{esc(bd.stat_text(a) if a["years"] else "一軍出場なし")}'
                f'{f"<div class=yss>{per}</div>" if len(m["after_seasons"]) > 1 else ""}</td>'
                f'<td class="sub" data-v="{b["war"] if b["years"] else -999}">{esc(bd.stat_text(b) if b["years"] else "一軍出場なし")}</td></tr>')
        return "\n".join(out)

    groups = []
    upcoming = ""
    for y in sorted(moves, reverse=True):
        ms = moves[y]
        if not ms:
            if y >= latest:
                upcoming = (f'<p class="note">・{y}年の現役ドラフトは12月に行われます。結果が出たら、このページに追加します。</p>')
            continue
        if y >= latest:
            label_small = "・移籍後の成績はこれから"
        else:
            w = sum(m["after"]["war"] for m in ms if m["pid"])
            label_small = f"・移籍後のWAR合計 {w:.1f}"
        groups.append((y, ms, label_small))
    year_nav = '<ul class="years teams">' + "".join(f'<li><a href="#y-{y}">{y}年</a></li>' for y, _, _ in groups) + "</ul>"
    tbodies = "\n".join(
        f'<tbody id="y-{y}"><tr class="tm"><th colspan="6"><span>{y}年の現役ドラフト'
        f'<small>{len(ms)}人{small}</small></span></th></tr>\n{rows(sorted(ms, key=lambda m: -m["after"]["war"] if m["after"]["years"] else 999))}\n</tbody>'
        for y, ms, small in groups)

    body = f"""
<p class="lead">現役ドラフトは、出場機会の少ない選手に移籍のチャンスを与えるため、{first}年に始まった制度です。毎年12月、12球団が2人以上の選手を候補に出し合い、1人ずつ指名して獲得します。このページでは、これまでに移籍した{len(done)}人について、移籍前（移籍の年までの{BEFORE_YEARS}年間）と移籍後の一軍成績・簡易WARを比べ、移籍が「当たり」だったかを振り返ります。成績は{latest}年シーズンまでの一軍公式戦の合計です。</p>

<div class="cards">
  <div class="card"><div class="k">移籍した選手（{first}〜{last_done}年）</div><div class="v">{len(done)}人</div><div class="s">うち投手 {sum(m["pos"] == "投手" for m in done)}人</div></div>
  <div class="card"><div class="k">移籍後に一軍に出場</div><div class="v">{len(played)}人</div><div class="s">{len(played) * 100 // max(1, len(done))}%</div></div>
  <div class="card"><div class="k">WAR{GOOD_WAR:.0f}以上のシーズンあり</div><div class="v">{len(good)}人</div><div class="s">移籍後に1度でも</div></div>
  <div class="card"><div class="k">移籍後のWARトップ</div><div class="v">{esc(disp(tops[0]["name"])) if tops else "―"}</div><div class="s">{(f'{tops[0]["year"]}年 ' + esc(move_text(tops[0])) + f' ・WAR {tops[0]["after"]["war"]:.1f}') if tops else ""}</div></div>
</div>

<h2>現役ドラフトの見どころ</h2>
<ul class="points">
{"".join(f"<li>{esc(t)}</li>" for t in pts)}
</ul>

<h2>現役ドラフトの「当たり」トップ10</h2>
<p>移籍の翌年から{latest}年までの、一軍での通算WARの順です。投手の下の（　）は、実際の失点から計算した「防御率ベース」のWARです（<a href="#ra9">理由</a>）。</p>
<div class="tbl-wrap"><table>
<thead><tr><th>順位</th><th>選手</th><th>年</th><th>移籍</th><th>移籍後の一軍成績</th><th class="n">移籍前3年WAR</th><th class="n">移籍後WAR</th></tr></thead>
<tbody>{top_rows}</tbody></table></div>

<h2>球団別の損得</h2>
<p>獲得した選手と、出ていった選手の、移籍後の通算WARの合計を比べます。差がプラスなら、現役ドラフトで得をしている球団です。</p>
<div class="tbl-wrap"><table>
<thead><tr><th>順位</th><th>球団</th><th class="n">獲得した選手</th><th class="n">出ていった選手</th><th class="n">差</th><th>獲得した選手のトップ</th></tr></thead>
<tbody>{led_rows}</tbody></table></div>

<h2>年ごとの現役ドラフト 移籍した選手とその後</h2>
{year_nav}
<p class="note">表の見出しを押すと、年の中で並べ替えられます。「移籍前3年」は、移籍の年までの3シーズンの合計です。投手のWARの下の（　）は、実際の失点から計算した「防御率ベース」のWARです（<a href="#ra9">理由</a>）。</p>
<div class="tbl-wrap"><table class="sortable" id="picks">
<thead><tr><th data-k>選手（元の球団→移籍先）</th><th data-k>守備</th><th data-k class="n">移籍後WAR</th><th data-k class="n">移籍前3年WAR</th><th data-k>移籍後の一軍成績</th><th data-k>移籍前3年の一軍成績</th></tr></thead>
{tbodies}
</table></div>
{upcoming}

<h2 id="ra9">投手のWARについて（このページだけ「防御率ベース」を添えている理由）</h2>
<p>このサイトの簡易WARは、投手の部分を防御率ではなくFIP（奪三振・与四死球・被本塁打だけから計算する指標）で出しています。運に左右されにくく、他のページではこの値だけを使っています。ただしFIPでは、次のような投手が実際の働きより低く出やすくなります。</p>
<ul class="points">
<li>制球と緩急で弱い打球を打たせて取る投手（三振が少なくても、失点が少ない投手）</li>
<li>救援投手（WARは投げたイニングに比例するので、年に50イニングほどでは、よく抑えても1前後にとどまる）</li>
</ul>
<p>現役ドラフトで移籍した選手は半分以上が投手で、その多くが救援です。移籍後に「実際にどれだけ失点を防いだか」も見ないと、移籍の当たり外れを見誤りやすいため、このページでは投手に限り、実際の失点から計算した「防御率ベース」のWARを、WARの下に（　）で添えています。順位や合計は、他のページと同じFIPベースの値です。</p>
<p>なお、救援投手が勝敗を左右する場面で投げた価値（メジャーのWARでは上乗せされる分）は、どちらの値にも入っていません。</p>

<p class="note">・簡易WARは、打撃・盗塁・守備位置・代替水準（投手はFIP）から計算したもので、守備の上手さ（UZR）や球場の補正は入っていません（<a href="/war/">計算方法</a>）。<br>
・移籍後の成績には、移籍先から別の球団に移った後の成績も含めています。<br>
・ドラフト会議で指名された選手のその後は、<a href="/draft/">ドラフト答え合わせ</a>で見られます。</p>
"""
    top_txt = "・".join(f'{disp(m["name"])}（{m["after"]["war"]:.1f}）' for m in tops[:3])
    title = f"現役ドラフト答え合わせ｜移籍した選手のその後・成績とWAR【{first}年〜】"
    desc = (f"プロ野球の現役ドラフト（{first}年〜）で移籍した{len(done)}人の、移籍前と移籍後の一軍成績・簡易WARを比較。"
            + (f"移籍後のWARトップは{top_txt}。" if top_txt else "")
            + "球団別の損得や、年ごとの移籍選手のその後もまとめています。")
    return bd.shell(title, desc, "/geneki-draft/", "現役ドラフト答え合わせ",
                    "移籍した選手の「移籍前」と「移籍後」を、一軍の成績と簡易WARで比べます", body, "geneki-draft",
                    footer=FOOTER).replace("</style>", CSS + "</style>", 1)


CSS = """
.cnt{ margin-left:2px; font-size:0.74rem; color:var(--ink-mute); font-weight:400; }
.yss{ margin-top:2px; }
.ra9{ display:block; font-size:0.72rem; font-weight:400; color:var(--ink-mute); white-space:nowrap; }
.mv{ display:block; font-size:0.74rem; font-weight:400; color:var(--ink-mute); }
.mv b{ color:var(--ink); }
.ys{ display:inline-block; margin-right:8px; font-size:0.74rem; color:var(--ink-mute); }
"""


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--league", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args(argv)
    data = Path(args.data)
    league = json.loads(Path(args.league).read_text(encoding="utf-8"))["seasons"]
    people = People(data / "register.json")
    by_pid, _, latest = bd.load_seasons_people(data, league, people)
    built = Path(args.out).parent / "player" / "built.json"
    has_page = set(json.loads(built.read_text(encoding="utf-8"))["pids"]) if built.exists() else set()
    moves = load_moves(data / "geneki_draft.json")
    page = build(moves, by_pid, people, has_page, latest)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "index.html").write_text(page, encoding="utf-8")
    print(f"geneki-draft: {sum(len(v) for v in moves.values())}人（〜{latest}年の成績）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
