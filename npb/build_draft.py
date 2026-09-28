#!/usr/bin/env python3
"""ドラフトの答え合わせ：指名選手のその後（一軍の通算成績と簡易WAR）を年ごとのページにする。

    python3 npb/build_draft.py --data npb/data --league war/league.json --out draft

- NPB公式のドラフトのページには選手へのリンクが無いので、指名選手はNPB在籍者名簿
  （npb/data/register.json）の「人」に、名前・指名した球団・入団した年で結びつける。
  成績も名簿の「人」ごとにまとめる（npb/people.py）ので、登録名を変えた選手
  （岡田貴弘→T-岡田、中川颯→颯 など）も変更後の成績まで含まれ、同姓同名の別人とも区別できる。
- 名簿が無いときは、名前だけで照合する古いやり方（assign）を使う。
- 簡易WARは /saber/ と同じ計算（守備・走塁・球場補正なし）。
"""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_magic import JST  # noqa: E402
from build_saber import compute_season, season_rows  # noqa: E402
from people import People, franchise, key  # noqa: E402

TEAM_ORDER = ["阪神", "巨人", "DeNA", "横浜", "ヤクルト", "広島", "中日",
              "ソフトバンク", "西武", "日本ハム", "オリックス", "ロッテ", "楽天"]
STAR_WAR = 10       # 通算WARがこれ以上なら「主力級」と書く
TOO_EARLY = 3        # 直近この年数のドラフトは「評価はまだ早い」と添える


def disp(name):
    return name.replace("　", " ")


def esc(s):
    return html.escape(str(s))


def fmt3(x):
    if x is None:
        return "―"
    s = f"{x:.3f}"
    return s[1:] if s.startswith("0") else s


# ---------------------------------------------------------------- 集計

def load_seasons(data_dir, league):
    """名前（照合キー）→ [(年, 打者dict or None, 投手dict or None)]"""
    by_name = defaultdict(list)
    last_year = None
    for f in sorted(data_dir.glob("season_*.json")):
        st = json.loads(f.read_text(encoding="utf-8"))
        y = st["year"]
        if str(y) not in league:
            continue
        batters, pitchers = compute_season(st, league[str(y)])
        rows = defaultdict(lambda: [None, None])
        for b in batters:
            rows[key(b["name"])][0] = b
        for p in pitchers:
            rows[key(p["name"])][1] = p
        for k, (b, p) in rows.items():
            by_name[k].append((y, b, p))
        last_year = y
    return by_name, last_year


def load_drafts(data_dir):
    drafts = {}
    for f in sorted(data_dir.glob("draft_*.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        # 「（辞退）」のような、選手名ではない行は除く
        picks = [p for p in d["picks"] if not p["name"].startswith(("（", "("))]
        for p in picks:   # 名前の後ろの「※」などの印を外す
            p["name"] = re.sub(r"[\s\u3000]*[※＊*]+$", "", p["name"])
        if picks:
            drafts[d["year"]] = picks
    return drafts


REDRAFT_GAP = 5      # 入団せずに再指名されるのは、この年数以内（浪人＋大学4年でも5年）


def assign(drafts, by_name):
    """指名ごとに、そのあとの一軍成績を割り当てる。

    同じ名前の指名が複数あるとき
      - 前の指名から5年以内・守備位置が同じで、前の指名の選手がまだ一軍に出ていない → 同じ人の再指名
        （入団拒否→大学・社会人を経て再指名など）。成績は新しいほうの指名に付ける
      - それ以外 → 同姓同名の別人。その年の成績は、前年か前々年にも出場していた
        （現役を続けている）ほうに付ける。あとから指名された同名の選手は、
        成績が混ざっている可能性があるので集計しない
    """
    picks_by_key = defaultdict(list)
    for y, picks in drafts.items():
        for p in picks:
            p["year"] = y
            p["key"] = key(p["name"])
            p["seasons"] = []
            p["ambiguous"] = False
            p["redrafted"] = None
            picks_by_key[p["key"]].append(p)

    for k, plist in picks_by_key.items():
        plist.sort(key=lambda p: p["year"])
        stats = sorted(by_name.get(k, []), key=lambda s: s[0])
        stat_years = [s[0] for s in stats]

        # 指名を「人」ごとにまとめる
        persons = [[plist[0]]]
        for p in plist[1:]:
            last = persons[-1][-1]
            played_before = any(last["year"] < y <= p["year"] for y in stat_years)
            same_pos = not (p["pos"] and last["pos"] and p["pos"] != last["pos"])
            if p["year"] - last["year"] <= REDRAFT_GAP and same_pos and not played_before:
                last["redrafted"] = (p["year"], p["team"])
                persons[-1].append(p)
            else:
                persons.append([p])

        seasons_of = {id(g): [] for g in persons}
        for (y, b, pt) in stats:
            cands = [g for g in persons if g[0]["year"] < y]
            if not cands:
                # 最初の指名より前に同名の選手がいる → 指名された選手と区別できない
                for p in plist:
                    p["ambiguous"] = True
                continue
            if len(cands) > 1:
                cont = [g for g in cands if any(py in (y - 1, y - 2) for py, _ in seasons_of[id(g)])]
                owner = cont[0] if cont else cands[-1]
                # 成績が混ざっている可能性があるのは、持ち主より新しく指名された同名の選手だけ
                # （引退した古いほうの選手とは取り違えようがない）
                for g in cands:
                    if g is not owner and g[0]["year"] > owner[0]["year"]:
                        for p in g:
                            p["ambiguous"] = True
            else:
                owner = cands[0]
            seasons_of[id(owner)].append((y, (b, pt)))
            target = max((p for p in owner if p["year"] < y), key=lambda p: p["year"])
            target["seasons"].append((y, b, pt))


def load_seasons_people(data_dir, league, people):
    """在籍者名簿の「人」ごとに成績をまとめる。
    → ({pid: [(年, 打者, 投手)]}, {名前キー: [(年, 打者, 投手)]}（名簿と結びつかなかった行）, 最新の年)"""
    stores = {}
    for f in sorted(data_dir.glob("season_*.json")):
        st = json.loads(f.read_text(encoding="utf-8"))
        if str(st["year"]) in league:
            stores[st["year"]] = st
    links = people.link_all({y: season_rows(st) for y, st in stores.items()})

    by_pid = defaultdict(list)
    by_name = defaultdict(list)
    last_year = None
    for y, st in sorted(stores.items()):
        batters, pitchers = compute_season(st, league[str(y)], links[y])
        rows = defaultdict(lambda: [None, None])
        for b in batters:
            rows[b["pid"] or (b["name"], tuple(b["teams"]))][0] = b
        for p in pitchers:
            rows[p["pid"] or (p["name"], tuple(p["teams"]))][1] = p
        for k, (b, p) in rows.items():
            if isinstance(k, str):
                by_pid[k].append((y, b, p))
            else:
                by_name[key(k[0])].append((y, b, p))
        last_year = y
    return by_pid, by_name, last_year


def assign_people(drafts, people, by_pid, by_name):
    """指名 → 在籍者名簿の「人」。指名の翌年（〜翌々年）に指名した球団に在籍した、同じ名前の人を探す。

    - 見つかれば、その人の一軍成績を（登録名が変わった年の分も含めて）すべて付ける
    - 見つからず、5年以内に同じ名前が再指名されていれば「入団せず」（入団拒否→再指名）
    - 名簿で見つからないときだけ、名簿と結びつかなかった成績を名前で拾う
    """
    picks_by_key = defaultdict(list)
    for y, picks in drafts.items():
        for p in picks:
            p.update(year=y, key=key(p["name"]), seasons=[], ambiguous=False,
                     redrafted=None, pid=None, unsigned=False)
            picks_by_key[p["key"]].append(p)

    def first_after(person, y):
        """指名の年より後で、最初に在籍した年と、その年の球団"""
        after = sorted(s for s in person["spans"] if s[0] > y)
        if not after:
            return None, set()
        first = after[0][0]
        return first, {franchise(s[1]) for s in after if s[0] == first}

    def played_before(person, y):
        return any(s[0] <= y for s in person["spans"])

    def pick_score(p, q):
        """指名の名前と、名簿の新人の名前の近さ。下の名前が同じなら改姓とみなす（大滝愛斗→武田愛斗）"""
        sc = people._score(p["key"], q)
        given_p = re.split(r"[\s\u3000]+", p["name"].strip())
        given_q = re.split(r"[\s\u3000]+", q["name"].strip())
        if len(given_p) == 2 and len(given_q) == 2 and key(given_p[1]) == key(given_q[1]):
            sc = max(sc, 1.2)
        return sc

    # 名簿で最初に在籍した年・球団ごとの「新人」（名前で見つからない指名の受け皿）
    rookies = defaultdict(list)
    for person in people.players:
        if person["spans"]:
            y0 = min(s[0] for s in person["spans"])
            for s in person["spans"]:
                if s[0] == y0:
                    rookies[(y0, franchise(s[1]))].append(person)
    taken = set()

    for y, picks in sorted(drafts.items()):
        for p in picks:
            team = franchise(p["team"])
            found = []
            # ドラフトのあとで改名した選手（李秉諺→李杜軒）は、手で補った対応表で探す
            for person in people.by_key.get(people.manual.get(p["key"], p["key"]), []):
                first, teams = first_after(person, y)
                if first and first <= y + 2 and team in teams:
                    found.append((first, played_before(person, y), person))
            # 同じ年に入った同名の人が複数いれば、指名より前に在籍していなかった人（新人）を選ぶ
            found.sort(key=lambda x: (x[0], x[1]))
            if len(found) > 1 and found[0][:2] == found[1][:2]:
                p["ambiguous"] = True
                continue
            person = found[0][2] if found else None
            if person:
                # 入団する前に、もう一度指名されている → この指名では入団していない
                # （2015年 巨人育成3位の松澤裕介は入団せず、2016年の育成8位で入団）
                again = [q for q in picks_by_key[p["key"]] if y < q["year"] < found[0][0]]
                if again:
                    p["unsigned"] = True
                    p["redrafted"] = (again[0]["year"], again[0]["team"])
                    continue
            if not person:
                # 名前が違う（改姓・異体字・外国出身選手の表記）→ 翌年・翌々年にその球団へ入った新人から探す
                pool = [q for q in rookies.get((y + 1, team), []) if q["pid"] not in taken]
                scored = sorted(((pick_score(p, q), q) for q in pool), key=lambda x: -x[0])
                if scored and scored[0][0] >= 0.6 and (len(scored) == 1 or scored[1][0] < scored[0][0]):
                    person = scored[0][1]
            if person:
                taken.add(person["pid"])
                p["pid"] = person["pid"]
                seasons = list(by_pid.get(p["pid"], []))
                # 名簿にまだ載っていない今シーズンの成績で、名簿と結びつかなかった行は名前で拾う
                have = {yy for yy, _, _ in seasons}
                for k in person["keys"]:
                    seasons += [s for s in by_name.get(k, []) if s[0] > people.max_year and s[0] not in have]
                p["seasons"] = sorted(seasons, key=lambda s: s[0])
                continue
            later = [q for q in picks_by_key[p["key"]] if y < q["year"] <= y + REDRAFT_GAP]
            if later:
                p["unsigned"] = True
                p["redrafted"] = (later[0]["year"], later[0]["team"])
                continue
            p["seasons"] = sorted((s for s in by_name.get(p["key"], []) if s[0] > y), key=lambda s: s[0])


def career(p):
    bt = defaultdict(int)
    pt = defaultdict(int)
    war = 0.0
    best = None
    years = []
    teams = []
    for (y, b, pi) in p["seasons"]:
        w = 0.0
        if b:
            for k in ("g", "pa", "ab", "h", "d2", "d3", "hr", "rbi", "sb", "bb", "hbp", "sf"):
                bt[k] += b.get(k) or 0
            w += b["war"] or 0
            teams += [t for t in b["teams"] if t not in teams]
        if pi:
            for k in ("g", "w", "l", "sv", "hld", "outs", "so", "er"):
                pt[k] += pi.get(k) or 0
            w += pi["war"] or 0
            teams += [t for t in pi["teams"] if t not in teams]
        war += w
        years.append(y)
        if best is None or w > best[1]:
            best = (y, w)
    c = {"years": len(years), "first": min(years) if years else None, "last": max(years) if years else None,
         "war": round(war, 1), "best": best, "teams": teams}
    # 野手か投手か：投手として出た量が多ければ投手成績を主に出す
    is_pitcher = pt["outs"] >= 3 * max(10, bt["pa"] / 4) or (p["pos"] == "投手" and bt["pa"] < 100)
    c["kind"] = "p" if (pt["g"] and is_pitcher) else ("b" if bt["g"] else None)
    if bt["ab"]:
        s1 = bt["h"] - bt["d2"] - bt["d3"] - bt["hr"]
        obp_den = bt["ab"] + bt["bb"] + bt["hbp"] + bt["sf"]
        c["avg"] = bt["h"] / bt["ab"]
        c["ops"] = ((bt["h"] + bt["bb"] + bt["hbp"]) / obp_den if obp_den else 0) + \
                   (s1 + 2 * bt["d2"] + 3 * bt["d3"] + 4 * bt["hr"]) / bt["ab"]
    c["bat"] = dict(bt)
    c["pit"] = dict(pt)
    if pt["outs"]:
        c["era"] = 9 * pt["er"] / (pt["outs"] / 3)
    return c


# ---------------------------------------------------------------- 表示

CSS = """
*{ box-sizing:border-box; }
:root{
    --ink:#1f2937; --ink-strong:#111827; --ink-sub:#4b5563; --ink-mute:#6b7280;
    --line:#d1d5db; --line-soft:#e5e7eb; --head-bg:#f3f4f6; --tint:#f9fafb;
    --accent:#2563eb; --good:#15803d; --gold:#b45309;
}
body{ margin:0; padding:0 0 48px; font-family:"Noto Sans JP","Hiragino Kaku Gothic ProN","Hiragino Sans",Meiryo,sans-serif;
      color:var(--ink); line-height:1.75; background:#f5f5f5; }
.page-wrapper{ max-width:1100px; margin:0 auto; padding:0 16px; }
/* ほかのページ（金特ツールなど）と同じく左に寄せ、左右に20pxの余白を取る。
   サイト共通の style.css は body を幅900pxに絞るので外し、表の広さに合わせた幅にする。
   下に付く「人気のページ」なども本文と同じ幅・余白にそろえる */
body{ max-width:none; }
.page-wrapper{ margin:0; padding:0 20px; }
body .td-rail-inline{ max-width:1100px; margin:40px 0 0; padding:0 20px; }
header{ background:var(--ink-strong); color:#fff; padding:20px 16px; margin-bottom:18px; }
header .page-wrapper{ padding:0; }
h1{ margin:0; font-size:1.35rem; line-height:1.5; }
header p{ margin:6px 0 0; font-size:0.9rem; color:#cbd5e1; }
h2{ margin:30px 0 12px; padding-bottom:6px; font-size:1.15rem; color:var(--ink-strong); border-bottom:2px solid var(--line); }
h3{ margin:20px 0 8px; padding-left:10px; font-size:1rem; color:var(--ink-strong); border-left:4px solid var(--accent); }
p{ margin:0 0 12px; }
.lead{ font-size:0.95rem; }
ul.points{ margin:0 0 8px; padding-left:1.3em; }
ul.points li{ margin:4px 0; }
.note{ font-size:0.84rem; color:var(--ink-mute); }
.years{ display:flex; flex-wrap:wrap; gap:6px; margin:0 0 16px; padding:0; list-style:none; }
.years a, .years span{ display:inline-block; padding:4px 10px; border:1px solid var(--line); border-radius:16px; background:#fff;
                       font-size:0.86rem; color:var(--ink-sub); text-decoration:none; }
.years span{ background:var(--ink-strong); color:#fff; border-color:var(--ink-strong); }
.cards{ display:grid; gap:10px; grid-template-columns:repeat(auto-fill,minmax(180px,1fr)); margin:0 0 16px; }
.card{ background:#fff; border:1px solid var(--line); border-radius:12px; padding:10px 12px; }
.card .k{ font-size:0.78rem; color:var(--ink-sub); }
.card .v{ font-size:1.35rem; font-weight:800; color:var(--ink-strong); line-height:1.3; }
.card .s{ font-size:0.8rem; color:var(--ink-mute); }
.tbl-wrap{ overflow-x:auto; -webkit-overflow-scrolling:touch; background:#fff; border:1px solid var(--line); border-radius:12px; margin:0 0 14px; }
table{ border-collapse:collapse; width:100%; font-size:0.86rem; font-variant-numeric:tabular-nums; }
th, td{ padding:7px 8px; border-bottom:1px solid var(--line-soft); text-align:left; white-space:nowrap; }
thead th{ background:var(--head-bg); font-size:0.78rem; color:var(--ink-sub); }
td.n, th.n{ text-align:right; }
td.nm{ font-weight:700; color:var(--ink-strong); }
td.sub{ font-size:0.78rem; color:var(--ink-mute); }
td.war{ font-weight:800; text-align:right; }
tr.none td{ color:var(--ink-mute); }
tr.none td.nm{ font-weight:400; }
.tag{ display:inline-block; font-size:0.7rem; padding:0 6px; border-radius:8px; background:#fef3c7; color:var(--gold); margin-left:4px; font-weight:700; }
.tag.ik{ background:#e0e7ff; color:#3730a3; }
.filter{ display:flex; flex-wrap:wrap; gap:8px 12px; align-items:center; margin:0 0 10px; font-size:0.86rem; color:var(--ink-sub); }
.filter select{ font:inherit; padding:5px 8px; border:1px solid var(--line); border-radius:8px; background:#fff; }
table.sortable th[data-k]{ cursor:pointer; }
article{ background:#fff; border:1px solid var(--line); border-radius:14px; padding:4px 20px 18px; margin-top:26px; }
footer.disclaimer{ margin-top:22px; font-size:0.82rem; color:var(--ink-mute); }
@media (max-width:600px){
    th, td{ padding:6px 6px; font-size:0.8rem; }
    article{ padding:2px 14px 14px; }
}
"""

SORT_JS = """
<script>
"use strict";
/* 表の見出しを押すと並べ替え、球団で絞り込み */
(function(){
  var t = document.getElementById("picks");
  if (!t) return;
  var body = t.tBodies[0];
  t.tHead.addEventListener("click", function(e){
    var th = e.target.closest("th[data-k]");
    if (!th) return;
    var idx = Array.prototype.indexOf.call(th.parentNode.children, th);
    var desc = th.dataset.dir !== "desc";
    th.parentNode.querySelectorAll("th").forEach(function(x){ delete x.dataset.dir; });
    th.dataset.dir = desc ? "desc" : "asc";
    var rows = Array.prototype.slice.call(body.rows);
    rows.sort(function(a, b){
      var x = a.cells[idx].dataset.v, y = b.cells[idx].dataset.v;
      var nx = parseFloat(x), ny = parseFloat(y);
      if (!isNaN(nx) && !isNaN(ny)) return desc ? ny - nx : nx - ny;
      return desc ? String(y).localeCompare(String(x), "ja") : String(x).localeCompare(String(y), "ja");
    });
    rows.forEach(function(r){ body.appendChild(r); });
  });
  var sel = document.getElementById("team-filter");
  if (sel) sel.addEventListener("change", function(){
    Array.prototype.forEach.call(body.rows, function(r){
      r.hidden = !!sel.value && r.dataset.team !== sel.value;
    });
  });
})();
</script>
"""


def shell(title, desc, canonical, h1, sub, body, tool_id, crumb=None):
    """crumb: パンくずの最後に足す段の名前（年別ページの「2018年」）"""
    extra = (f'<script> const BREADCRUMB_EXTRA = {{ name: "{esc(crumb)}", url: "{canonical}" }}; </script>\n'
             if crumb else "")
    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">

<!-- npb/build_draft.py が生成する。直接書き換えても、次の自動更新で消える -->
<title>{esc(title)}</title>
<meta name="description" content="{esc(desc)}">
<link rel="canonical" href="https://tooldock.github.io{canonical}">

<script> const CURRENT_TOOL = "{tool_id}"; </script>
{extra}<script src="/js/tool-data.js"></script>
<script src="/js/head.js"></script>
<script src="/js/analytics.js"></script>

<!-- Google AdSense -->
<script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-8349615939902537" crossorigin="anonymous"></script>

<style>{CSS}</style>
</head>

<body>
<div class="page-wrapper">
<header>
    <h1>{esc(h1)}</h1>
    <p>{esc(sub)}</p>
</header>
<div class="container">
{body}
<footer class="disclaimer">
指名選手と成績はNPB（日本野球機構）公式サイトのドラフト会議・個人成績をもとに、当サイトが独自に集計したものです。
成績は一軍の公式戦のみです。指名選手と成績は、NPBの在籍者名簿（在籍した年・球団・改名の履歴）で照合しています。
</footer>
</div>
</div>
{SORT_JS}
</body>
</html>
"""


def pick_label(p):
    if p["label"] == "希望枠":
        return "希望枠"
    lab = p["label"]
    if "高校生" in p["section"]:
        lab = "高" + lab
    elif "大学生" in p["section"]:
        lab = "大社" + lab
    return lab


def stat_text(c):
    if c["kind"] == "b":
        b = c["bat"]
        return f'{b["g"]}試合 打率{fmt3(c.get("avg"))} {b["hr"]}本 {b["sb"]}盗塁'
    if c["kind"] == "p":
        pt = c["pit"]
        s = f'{pt["g"]}登板 {pt["w"]}勝{pt["l"]}敗'
        if pt["sv"]:
            s += f' {pt["sv"]}S'
        if pt["hld"]:
            s += f' {pt["hld"]}H'
        s += f' 防御率{c["era"]:.2f}' if c.get("era") is not None else ""
        return s
    return "一軍出場なし"


def pick_rows(picks):
    out = []
    for p in picks:
        c = p["career"]
        tags = ""
        if p["ikusei"]:
            tags += '<span class="tag ik">育成</span>'
        if p["redrafted"]:
            tags += f'<span class="tag">{p["redrafted"][0]}年に{esc(p["redrafted"][1])}が再指名</span>'
        if p["ambiguous"]:
            stat, war_v, war_t = "同姓同名の選手がいるため集計していません", -999, "―"
        elif p.get("unsigned"):
            stat, war_v, war_t = "入団せず", -999, "―"
        else:
            stat = stat_text(c)
            war_v = c["war"] if c["years"] else -999
            war_t = f'{c["war"]:.1f}' if c["years"] else "―"
        yrs = f'{c["years"]}年' if c["years"] else "―"
        cls = "" if c["years"] else ' class="none"'
        order = (0 if p["label"] == "希望枠" else 1) * 100 + (p["round"] or 0) + (50 if p["ikusei"] else 0)
        out.append(
            f'<tr{cls} data-team="{esc(p["team"])}">'
            f'<td data-v="{esc(p["team"])}">{esc(p["team"])}</td>'
            f'<td data-v="{order}">{esc(pick_label(p))}</td>'
            f'<td class="nm" data-v="{esc(p["name"])}">{esc(disp(p["name"]))}{tags}</td>'
            f'<td data-v="{esc(p["pos"])}">{esc(p["pos"] or "―")}</td>'
            f'<td class="sub" data-v="{esc(p["from"])}">{esc(p["from"])}</td>'
            f'<td class="n" data-v="{c["years"]}">{yrs}</td>'
            f'<td data-v="{war_v}">{esc(stat)}</td>'
            f'<td class="war" data-v="{war_v}">{war_t}</td></tr>')
    return "\n".join(out)


def team_sort_key(t):
    return TEAM_ORDER.index(t) if t in TEAM_ORDER else 99


def year_points(year, picks, played, team_rank, early):
    """その年の見どころを、データから短い文で書く → (4位以下の当たり, [文...])"""
    def who(p):
        return f'{disp(p["name"])}（{p["team"]}{"育成" if p["ikusei"] else ""}{pick_label(p)}・通算WAR {p["career"]["war"]:.1f}）'

    def ok(p):
        return not p["ambiguous"] and not p["unsigned"]

    pts = []
    # 1位（高校生・大学生社会人の1巡目、希望枠を含む）
    top_picks = [p for p in picks if ok(p) and not p["ikusei"] and (p["round"] == 1 or p["label"] == "希望枠")]
    if top_picks:
        up = [p for p in top_picks if p["career"]["years"]]
        stars = sorted((p for p in top_picks if p["career"]["war"] >= STAR_WAR), key=lambda p: -p["career"]["war"])
        # 2005〜2007年は高校生と大学生・社会人に分かれていて、1巡目と希望枠がある
        t = (f"1巡目・希望枠の{len(top_picks)}人" if year <= 2007 else f"1位指名{len(top_picks)}人") + \
            f"のうち、一軍に出場したのは{len(up)}人。"
        if stars:
            t += f"通算WAR{STAR_WAR}以上の主力級は{len(stars)}人（{'・'.join(disp(p['name']) for p in stars[:4])}{'など' if len(stars) > 4 else ''}）。"
        elif not early:
            t += f"通算WAR{STAR_WAR}以上の主力級はいません。"
        pts.append(t)
    # 4位以下（育成を除く）の当たり
    low = sorted((p for p in played if ok(p) and not p["ikusei"] and (p["round"] or 0) >= 4
                  and p["career"]["war"] > 0), key=lambda p: -p["career"]["war"])[:2]
    if low:
        pts.append(("4巡目以下" if year <= 2007 else "4位以下") + "で最も活躍しているのは"
                   + "、次いで".join(who(p) for p in low) + "。")
    # 育成
    n_ik = sum(1 for p in picks if p["ikusei"] and ok(p))
    ik = sorted((p for p in played if ok(p) and p["ikusei"]), key=lambda p: -p["career"]["war"])
    if n_ik:
        if ik:
            pts.append(f"育成指名{n_ik}人のうち{len(ik)}人が一軍に出場。最も活躍しているのは{who(ik[0])}。")
        elif not early:
            pts.append(f"育成指名{n_ik}人から一軍に出場した選手はいません。")
    # 球団別
    if team_rank and team_rank[0][1][0] > 0:
        team, v = team_rank[0]
        best = sorted((p for p in played if p["team"] == team and ok(p)), key=lambda p: -p["career"]["war"])[:2]
        pts.append(f"球団別では{team}が通算WAR合計{v[0]:.1f}でトップ（{'・'.join(disp(p['name']) for p in best)}）。")
    # 入団しなかった選手
    uns = [p for p in picks if p["unsigned"]]
    if uns:
        pts.append("指名されたが入団しなかった選手：" + "、".join(
            f'{disp(p["name"])}（{p["team"]}{pick_label(p)}→{p["redrafted"][0]}年に{p["redrafted"][1]}が再指名）'
            for p in uns) + "。")
    if early:
        pts.append("指名から日が浅いため、評価はこれからです。")
    return (low[0] if low else None), pts


def year_page(year, picks, years, last_season):
    n_all = len(picks)
    n_ik = sum(p["ikusei"] for p in picks)
    played = [p for p in picks if p["career"]["years"] and not p["ambiguous"]]
    tops = sorted(played, key=lambda p: -p["career"]["war"])[:5]
    firsts = [p for p in picks if p["round"] == 1 and not p["ikusei"] and "高校生" not in p["section"]] or \
             [p for p in picks if p["round"] == 1 and not p["ikusei"]]
    ik_up = [p for p in played if p["ikusei"]]
    by_team = defaultdict(lambda: [0.0, 0, 0])
    for p in picks:
        t = by_team[p["team"]]
        t[1] += 1
        if not p["ambiguous"]:
            t[0] += p["career"]["war"]
            t[2] += 1 if p["career"]["years"] else 0
    team_rank = sorted(by_team.items(), key=lambda kv: -kv[1][0])

    early = last_season is not None and last_season - year < TOO_EARLY
    nav = '<ul class="years">' + "".join(
        f'<li><span>{y}</span></li>' if y == year else f'<li><a href="/draft/{y}/">{y}</a></li>'
        for y in sorted(years, reverse=True)) + "</ul>"

    top_txt = "・".join(f'{disp(p["name"])}（{p["team"]}{pick_label(p)}）' for p in tops[:3])
    low, points = year_points(year, picks, played, team_rank, early)
    body = f"""
{nav}
<p class="lead">{year}年のドラフト会議で指名された{n_all}人（うち育成{n_ik}人）が、その後どうなったかを一軍の通算成績と簡易WARで振り返ります。成績は{last_season}年{"シーズン途中" if last_season == datetime.now(JST).year else ""}までの一軍公式戦の合計です。</p>
{'<p class="note">※指名からまだ日が浅いため、評価はこれからです。</p>' if early else ''}

<div class="cards">
  <div class="card"><div class="k">指名された選手</div><div class="v">{n_all}人</div><div class="s">うち育成 {n_ik}人</div></div>
  <div class="card"><div class="k">一軍に出場した選手</div><div class="v">{len(played)}人</div><div class="s">{len(played) * 100 // max(1, n_all)}%</div></div>
  <div class="card"><div class="k">通算WARトップ</div><div class="v">{esc(disp(tops[0]["name"])) if tops else "―"}</div><div class="s">{(esc(tops[0]["team"]) + " " + esc(pick_label(tops[0])) + f' ・WAR {tops[0]["career"]["war"]:.1f}') if tops else ""}</div></div>
  <div class="card"><div class="k">育成から一軍へ</div><div class="v">{len(ik_up)}人</div><div class="s">{esc("・".join(disp(p["name"]) for p in sorted(ik_up, key=lambda p: -p["career"]["war"])[:2]))}</div></div>
</div>

<h2>{year}年ドラフトの見どころ</h2>
<ul class="points">
{"".join(f"<li>{esc(t)}</li>" for t in points)}
</ul>

<h2>{year}年ドラフトの「当たり」トップ5</h2>
<div class="tbl-wrap"><table>
<thead><tr><th>順位</th><th>選手</th><th>指名</th><th>一軍通算</th><th class="n">通算WAR</th></tr></thead>
<tbody>
{"".join(f'<tr><td>{i}</td><td class="nm">{esc(disp(p["name"]))}</td><td>{esc(p["team"])} {esc(pick_label(p))}</td><td>{esc(stat_text(p["career"]))}</td><td class="war">{p["career"]["war"]:.1f}</td></tr>' for i, p in enumerate(tops, 1))}
</tbody></table></div>

<h2>球団別のドラフト採点（{year}年）</h2>
<p>その年に指名した選手の、一軍での通算WARの合計です。</p>
<div class="tbl-wrap"><table>
<thead><tr><th>順位</th><th>球団</th><th class="n">指名</th><th class="n">一軍出場</th><th class="n">通算WAR合計</th></tr></thead>
<tbody>
{"".join(f'<tr><td>{i}</td><td class="nm">{esc(t)}</td><td class="n">{v[1]}人</td><td class="n">{v[2]}人</td><td class="war">{v[0]:.1f}</td></tr>' for i, (t, v) in enumerate(team_rank, 1))}
</tbody></table></div>

<h2>{year}年ドラフト 指名選手一覧とその後</h2>
<div class="filter"><label>球団で絞り込む <select id="team-filter"><option value="">全球団</option>
{"".join(f'<option>{esc(t)}</option>' for t in sorted(by_team, key=team_sort_key))}
</select></label><span class="note">見出しを押すと並べ替えられます</span></div>
<div class="tbl-wrap"><table class="sortable" id="picks">
<thead><tr><th data-k>球団</th><th data-k>指名</th><th data-k>選手</th><th data-k>守備</th><th data-k>出身</th><th data-k class="n">一軍</th><th data-k>一軍通算成績</th><th data-k class="n">通算WAR</th></tr></thead>
<tbody>
{pick_rows(sorted(picks, key=lambda p: (team_sort_key(p["team"]), p["ikusei"], 0 if p["label"] == "希望枠" else 1, p["round"] or 0)))}
</tbody></table></div>
<p class="note">・「一軍」は一軍の公式戦に出場したシーズン数です。<br>
・簡易WARは、打撃・盗塁・守備位置・代替水準（投手はFIP）から計算したもので、守備の上手さ（UZR）や球場の補正は入っていません（<a href="/war/">計算方法</a>）。<br>
・登録名を変えた選手は「岡田 貴弘（T-岡田）」のように表示し、変更後の成績も含めて集計しています。<br>
・「入団せず」は、指名後に入団せず、のちに再指名された選手です。</p>
{'<p class="note">・2005〜2007年は高校生と大学生・社会人でドラフトが分かれていたため、「高1巡目」「大社1巡目」のように表記しています。「希望枠」は希望入団枠での獲得です。</p>' if year <= 2007 else ''}
"""
    title = f"{year}年ドラフト 答え合わせ｜12球団の指名結果と評価・その後の成績"
    desc = (f"{year}年のプロ野球ドラフト会議で指名された{n_all}人の指名結果と、その後の一軍通算成績・簡易WAR。"
            f"通算WARトップは{top_txt}。"
            + (f"{'4巡目' if year <= 2007 else '4位'}以下の当たりは{disp(low['name'])}（{low['team']}{pick_label(low)}）。"
               if low and low not in tops[:3] else "")
            + "球団別のドラフト採点や、育成指名からの出世組もまとめています。") if tops else \
           f"{year}年のプロ野球ドラフト会議で指名された{n_all}人の指名結果と、その後の一軍成績。"
    return shell(title, desc, f"/draft/{year}/", f"{year}年ドラフト 答え合わせ",
                 "指名選手のその後を、一軍の通算成績と簡易WARで振り返ります", body, "draft",
                 crumb=f"{year}年")


def index_page(drafts, last_season):
    all_picks = [p for y in drafts for p in drafts[y]]
    graded = [p for p in all_picks if not p["ambiguous"] and last_season - p["year"] >= 5]
    tops = sorted([p for p in all_picks if not p["ambiguous"]], key=lambda p: -p["career"]["war"])[:30]

    # 指名順位ごとの平均（5年以上たったドラフトのみ）
    def bucket(p):
        if p["ikusei"]:
            return "育成"
        if p["label"] == "希望枠":
            return "希望枠"
        if p["round"] is None:
            return None
        return f'{p["round"]}位' if p["round"] <= 5 else "6位以下"
    bk = defaultdict(list)
    for p in graded:
        b = bucket(p)
        if b:
            bk[b].append(p)
    order = ["1位", "2位", "3位", "4位", "5位", "6位以下", "育成"]
    rank_rows = ""
    for b in order:
        ps = bk.get(b, [])
        if not ps:
            continue
        played = sum(1 for p in ps if p["career"]["years"])
        good = sum(1 for p in ps if p["career"]["war"] >= 10)
        avg = sum(p["career"]["war"] for p in ps) / len(ps)
        rank_rows += (f'<tr><td class="nm">{b}</td><td class="n">{len(ps)}人</td>'
                      f'<td class="n">{played * 100 // len(ps)}%</td><td class="n">{good * 100 / len(ps):.1f}%</td>'
                      f'<td class="war">{avg:.1f}</td></tr>')

    by_team = defaultdict(float)
    for p in all_picks:
        if not p["ambiguous"]:
            by_team[team_short_franchise(p["team"])] += p["career"]["war"]
    team_rows = "".join(f'<tr><td>{i}</td><td class="nm">{esc(t)}</td><td class="war">{w:.1f}</td></tr>'
                        for i, (t, w) in enumerate(sorted(by_team.items(), key=lambda kv: -kv[1]), 1))

    years = sorted(drafts, reverse=True)
    year_rows = ""
    for y in years:
        ps = [p for p in drafts[y] if not p["ambiguous"]]
        best = max(ps, key=lambda p: p["career"]["war"]) if ps else None
        year_rows += (f'<tr><td class="nm"><a href="/draft/{y}/">{y}年</a></td><td class="n">{len(drafts[y])}人</td>'
                      f'<td>{esc(disp(best["name"])) + "（" + esc(best["team"]) + " " + esc(pick_label(best)) + "）" if best and best["career"]["years"] else "―"}</td>'
                      f'<td class="war">{best["career"]["war"]:.1f}</td></tr>' if best and best["career"]["years"] else
                      f'<tr><td class="nm"><a href="/draft/{y}/">{y}年</a></td><td class="n">{len(drafts[y])}人</td><td>―</td><td class="war">―</td></tr>')

    body = f"""
<p class="lead">{min(drafts)}年以降のプロ野球ドラフト会議で指名された全{len(all_picks)}人について、その後の一軍通算成績と簡易WARを集計しました。年ごとの「答え合わせ」ページで、どの球団のどの指名が当たりだったのかを振り返れます。</p>

<h2>年別のドラフト答え合わせ</h2>
<div class="tbl-wrap"><table>
<thead><tr><th>年</th><th class="n">指名</th><th>その年の通算WARトップ</th><th class="n">WAR</th></tr></thead>
<tbody>{year_rows}</tbody></table></div>

<h2>指名順位ごとの「当たり」の確率</h2>
<p>指名から5年以上たったドラフト（{min(drafts)}〜{last_season - 5}年）について、指名順位ごとに一軍に出場した割合と、通算WARが10以上（主力として数年活躍した目安）になった割合をまとめました。</p>
<div class="tbl-wrap"><table>
<thead><tr><th>指名順位</th><th class="n">人数</th><th class="n">一軍出場</th><th class="n">通算WAR10以上</th><th class="n">平均WAR</th></tr></thead>
<tbody>{rank_rows}</tbody></table></div>
<p class="note">2005〜2007年の分離ドラフトは、高校生・大学生社会人の各巡目をそのまま順位として数えています。希望入団枠は含めていません。</p>

<h2>ドラフト指名選手の通算WAR ランキング（{min(drafts)}年以降）</h2>
<div class="tbl-wrap"><table>
<thead><tr><th>順位</th><th>選手</th><th>指名</th><th>一軍通算</th><th class="n">通算WAR</th></tr></thead>
<tbody>
{"".join(f'<tr><td>{i}</td><td class="nm">{esc(disp(p["name"]))}</td><td><a href="/draft/{p["year"]}/">{p["year"]}年</a> {esc(p["team"])} {esc(pick_label(p))}</td><td>{esc(stat_text(p["career"]))}</td><td class="war">{p["career"]["war"]:.1f}</td></tr>' for i, p in enumerate(tops, 1))}
</tbody></table></div>

<h2>球団別 ドラフト指名選手の通算WAR合計（{min(drafts)}年以降）</h2>
<p>各球団が指名した選手が、その後（他球団に移ってからも含めて）一軍で積み上げたWARの合計です。</p>
<div class="tbl-wrap"><table>
<thead><tr><th>順位</th><th>球団</th><th class="n">通算WAR合計</th></tr></thead>
<tbody>{team_rows}</tbody></table></div>
<p class="note">横浜（〜2011年）はDeNAに含めています。</p>

<article>
<h2>このページについて</h2>
<p>NPB公式サイトのドラフト会議の指名選手一覧と、各年の個人成績（一軍）を、NPBの在籍者名簿（在籍した年・球団・改名の履歴）で1人ずつ照合して集計しています。簡易WARの計算方法は<a href="/war/">WAR計算ツール</a>、毎年の選手ごとの指標は<a href="/saber/">セイバーメトリクス ランキング</a>で見られます。</p>
<p class="note">・登録名を変えた選手（T-岡田、颯など）も、変更後の成績まで含めて1人の選手として集計しています。同姓同名の別人は、在籍した球団と年で区別しています。<br>
・簡易WARには守備の上手さ（UZR）や球場の補正が入っていないため、守備の名手は低めに出ます。<br>
・成績は毎日更新しています。その年のドラフト会議が終わると、翌日以降に新しい年のページが追加されます。</p>
</article>
"""
    title = "ドラフト答え合わせ｜全指名選手のその後・通算成績とWAR【2005年〜】"
    desc = (f"{min(drafts)}年以降のプロ野球ドラフト会議で指名された全{len(all_picks)}人の、その後の一軍通算成績と簡易WARを年別に集計。"
            "指名順位ごとの当たりの確率、球団別のドラフト採点、通算WARランキングもまとめています。")
    return shell(title, desc, "/draft/", "ドラフト答え合わせ",
                 "指名選手のその後を、一軍の通算成績と簡易WARで年ごとに振り返ります", body, "draft")


def team_short_franchise(t):
    return "DeNA" if t == "横浜" else t


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--league", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args(argv)

    league = json.loads(Path(args.league).read_text(encoding="utf-8"))["seasons"]
    data = Path(args.data)
    drafts = load_drafts(data)
    reg = data / "register.json"
    if reg.exists():
        people = People(reg)
        by_pid, by_name, last_season = load_seasons_people(data, league, people)
        assign_people(drafts, people, by_pid, by_name)
        # 登録名を変えた選手は「岡田 貴弘（T-岡田）」のように表示する
        for y in drafts:
            for p in drafts[y]:
                if p["pid"]:
                    p["name"] = people.display(p["pid"], p["name"])
    else:
        by_name, last_season = load_seasons(data, league)
        assign(drafts, by_name)
    for y in drafts:
        for p in drafts[y]:
            p.setdefault("unsigned", False)
            p["career"] = career(p)

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    years = sorted(drafts)
    for y in years:
        d = out / str(y)
        d.mkdir(exist_ok=True)
        (d / "index.html").write_text(year_page(y, drafts[y], years, last_season), encoding="utf-8")
    (out / "index.html").write_text(index_page(drafts, last_season), encoding="utf-8")
    print(f"draft: {years[0]}〜{years[-1]}年 {sum(len(v) for v in drafts.values())}人")
    return 0


if __name__ == "__main__":
    sys.exit(main())
