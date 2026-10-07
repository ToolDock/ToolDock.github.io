#!/usr/bin/env python3
"""NPB公式の個人成績とドラフト指名選手を、年ごとに npb/data/ へ集める。

    python3 npb/stats_store.py --data npb/data            # 今シーズンを取り直し、足りない年を埋める
    python3 npb/stats_store.py --data /tmp/d --html-dir x # 手元のHTMLで試す

保存するもの
  season_<年>.json … 12球団の個人打撃・投手・守備成績と、リーグごとのチーム成績の合計
  draft_<年>.json  … その年のドラフト会議の指名選手（球団・順位・守備位置・出身）
  roster_<年度>.json … 球団の選手一覧（支配下・育成、シーズン途中の退団・移籍を含む）。毎日取り直す

過去の年は一度作れば変わらないので取り直さない（final が付く）。
毎日取り直すのは今シーズンと、まだ指名が出ていない今年のドラフトだけ。
NPBのサーバーに負担をかけないよう、1ページごとに間を空ける。
"""

from __future__ import annotations

import argparse
import json
import html
import re
import sys
import time
import unicodedata
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_magic import JST, _cell, fetch  # noqa: E402
from build_league import (BAT_KEYS, LEAGUES, Source, find_table, ip_of,  # noqa: E402
                          num, parse_table, pitching_totals, table_heads, total)

FIRST_YEAR = 2005        # 個人成績のページがこの年からある
DRAFT_URL = "https://npb.jp/draft/{year}/{page}"

BAT_COLS = ["team", "name", "hand", "試合", "打席", "打数", "得点", "安打", "二塁打", "三塁打",
            "本塁打", "打点", "盗塁", "盗塁刺", "犠打", "犠飛", "四球", "故意四", "死球", "三振", "併殺打"]
PIT_COLS = ["team", "name", "hand", "登板", "勝利", "敗北", "セーブ", "ホールド", "完投", "打者",
            "outs", "安打", "本塁打", "四球", "故意四", "死球", "三振", "失点", "自責点",
            "完封勝", "無四球", "暴投", "ボーク"]
FLD_COLS = ["team", "name", "pos", "試合", "刺殺", "補殺", "失策", "併殺", "捕逸"]
FLD_NUMS = FLD_COLS[3:]          # 守備成績の数の列（捕逸は捕手だけ。ほかの位置は0）
# リーグ全体の守備部門のページ（llf_c / llf_p）にだけある順位（個人の成績表には無い）
LEADER_TITLES = {"csp": "盗塁阻止率（捕手）"}
TEAM_ABBR = {"巨": "巨人", "ヤ": "ヤクルト", "神": "阪神", "広": "広島", "中": "中日", "デ": "DeNA", "横": "横浜",
             "ソ": "ソフトバンク", "日": "日本ハム", "ロ": "ロッテ", "西": "西武", "楽": "楽天", "オ": "オリックス"}
POSITIONS = ("捕手", "一塁手", "二塁手", "三塁手", "遊撃手", "外野手")


def clean_name(s):
    """表示用の名前。先頭の打席・投げの印を外し、姓名の間は全角空白1つにそろえる"""
    s = re.sub(r"^[*+＊＋]\s*", "", s.strip())
    return re.sub(r"[\s　]+", "　", s)


def hand_mark(row, name):
    """'*' = 左、'+' = 両。新しい年は名前の先頭、古い年は別の列にある"""
    mark = (row.get("") or "") + name[:1]
    if "+" in mark or "＋" in mark:
        return "S"
    if "*" in mark or "＊" in mark:
        return "L"
    return "R"


def team_links(tmb_page):
    """チーム打撃成績の表から、球団コード → 表示名"""
    table = find_table(tmb_page, ("チーム", "打数"))
    out = {}
    for code, label in re.findall(r'idb1_(\w+)\.html"[^>]*>(.*?)</a>', table, re.S):
        out[code] = re.sub(r"[\s　]", "", _cell(label))
    return out


def parse_fielding(page):
    """個人守備成績：守備位置の見出しの直後にある表を、位置ごとに読む"""
    out = []
    for m in re.finditer(r"<table.*?</table>", page, re.S):
        before = page[max(0, m.start() - 500):m.start()]
        best = None
        for p in POSITIONS + ("投手",):
            i = before.rfind(p)
            if i >= 0 and (best is None or i > best[1]):
                best = (p, i)
        if not best or best[0] not in POSITIONS:
            continue
        table = m.group(0)
        heads = table_heads(table)
        if "試合" not in heads:
            continue
        for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", table, re.S):
            tds = [_cell(td) for td in re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)]
            if len(tds) != len(heads):
                continue
            row = dict(zip(heads, tds))
            name = row.get("選手", "")
            if name:
                out.append([clean_name(name), best[0]] + [num(row.get(k, 0)) for k in FLD_NUMS])
    return out


def parse_fielding_old(page):
    """古い年の個人守備成績：1つの表の中に「【一塁手】」の見出し行が挟まっている。
    見出し行は【一塁手】・試合・刺殺…、選手の行は 印・選手名・試合・刺殺… の順"""
    out = []
    pos, heads = None, []
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", page, re.S):
        head = re.search(r"【(.+?)】", _cell(tr)) if "<th" in tr else None
        if head:
            pos = head.group(1) if head.group(1) in POSITIONS else None
            new = [re.sub(r"\s", "", _cell(h)) for h in re.findall(r"<t[hd][^>]*>(.*?)</t[hd]>", tr, re.S)][1:]
            # 列名は最初の【一塁手】の行にだけあり、2つ目からの見出し行は空
            if any(new):
                heads = new
            continue
        if not pos:
            continue
        m = re.search(r'<td class="stplayer">(.*?)</td>(.*)', tr, re.S)
        if not m:
            continue
        name = _cell(m.group(1))
        vals = [_cell(td) for td in re.findall(r"<td[^>]*>(.*?)</td>", m.group(2), re.S)]
        row = dict(zip(heads, vals))
        if name and re.fullmatch(r"\d+", row.get("試合", "")):
            out.append([clean_name(name), pos] + [num(row.get(k, 0)) for k in FLD_NUMS])
    return out


def parse_leaders(page):
    """守備部門のページ → {"csp": [{"rank": 1, "name": "古賀　優大", "team": "ヤクルト", "value": 0.5}, ...]}。
    同じ順位に何人もいて「( 3 選手 )」とまとめられている行は、名前が無いので外す"""
    text = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", page)))
    out = {}
    for key, title in LEADER_TITLES.items():
        i = text.find(title)
        if i < 0:
            continue
        rest = text[i + len(title):]
        nxt = re.search(r"\S+（[^）]+）", rest)          # 次の部門の見出し（守備率（投手） など）
        body = rest[:nxt.start()] if nxt else rest[:400]
        rows = []
        for m in re.finditer(r"(\d+)\s+([^()（）]+?)\s*[（(]\s*(\S)\s*[）)]\s*([\d.]+)", body):
            rows.append({"rank": int(m.group(1)), "name": clean_name(m.group(2)),
                         "team": TEAM_ABBR.get(m.group(3), m.group(3)), "value": float(m.group(4))})
        out[key] = rows
    return out


def fetch_fielding(src, year, code):
    page = src.get(year, f"idf1_{code}")
    return parse_fielding(page) or parse_fielding_old(page)


def fetch_season(src, year):
    teams, bat, pit, fld, totals = {}, [], [], [], {}
    as_of = None
    for lg, key, label in LEAGUES:
        tmb = src.get(year, f"tmb_{lg}")
        a, team_bat = parse_table(tmb, ("チーム", "打席"))
        _, team_pit = parse_table(src.get(year, f"tmp_{lg}"), ("チーム", "投球回"))
        as_of = as_of or a
        if not team_bat or total(team_bat, "打席") == 0:
            raise ValueError(f"{year}年 {label} はまだ成績がない")
        games = max(num(r["試合"]) for r in team_bat)
        totals[key] = {"bat": {k: total(team_bat, k) for k in BAT_KEYS + ["打点"]},
                       "pit": pitching_totals(team_pit),
                       "games": games}
        for code, name in team_links(tmb).items():
            teams[code] = {"name": name, "league": key,
                           "games": next((num(r["試合"]) for r in team_bat
                                          if re.sub(r"[\s　]", "", r["チーム"]) == name), games)}

    for code in teams:
        _, rows = parse_table(src.get(year, f"idb1_{code}"), ("選手", "打席"))
        for r in rows:
            name = r["選手"]
            vals = [num(r.get(k, 0)) for k in BAT_COLS[3:]]
            if not any(vals[1:]):          # 打席も何もない（登録だけ）
                continue
            bat.append([code, clean_name(name), hand_mark(r, name)] + vals)
        _, rows = parse_table(src.get(year, f"idp1_{code}"), ("選手", "投球回"))
        for r in rows:
            name = r["選手"]
            outs = round(ip_of(r) * 3)
            row = [code, clean_name(name), hand_mark(r, name)]
            for k in PIT_COLS[3:]:
                row.append(outs if k == "outs" else num(r.get(k, 0)))
            pit.append(row)
        try:
            for row in fetch_fielding(src, year, code):
                fld.append([code] + row)
        except Exception as e:  # 守備は無くても打撃・投手の集計はできる
            print(f"注意: {year} {code} 守備成績を読めない: {e}", file=sys.stderr)

    leaders = {}
    for lg, key, label in LEAGUES:
        try:
            for k, rows in parse_leaders(src.get(year, f"llf_{lg}")).items():
                leaders.setdefault(k, {})[key] = rows
        except Exception as e:  # 無くても成績の集計はできる
            print(f"注意: {year} {label} 守備部門の順位を読めない: {e}", file=sys.stderr)

    return {"year": year, "as_of": as_of, "teams": teams, "totals": totals,
            "bat_cols": BAT_COLS, "bat": bat, "pit_cols": PIT_COLS, "pit": pit,
            "fld_cols": FLD_COLS, "fld": fld, "leaders": leaders}


# ---------------------------------------------------------------- ドラフト

TEAM_KEYWORDS = [("阪神", "阪神"), ("読売", "巨人"), ("DeNA", "DeNA"), ("横浜", "横浜"),
                 ("ヤクルト", "ヤクルト"), ("広島", "広島"), ("中日", "中日"),
                 ("ソフトバンク", "ソフトバンク"), ("西武", "西武"), ("日本ハム", "日本ハム"),
                 ("オリックス", "オリックス"), ("ロッテ", "ロッテ"), ("楽天", "楽天")]


def team_short(full):
    for kw, short in TEAM_KEYWORDS:
        if kw in full:
            return short
    return full


def zen2han(s):
    return s.translate(str.maketrans("０１２３４５６７８９", "0123456789"))


def parse_draft_list(page):
    title = re.search(r"<title>(.*?)</title>", page, re.S).group(1)
    team = team_short(re.split(r"\s*[|｜]|\s+選択選手一覧", title)[0].strip())
    picks = []
    parts = re.split(r"<h4[^>]*>", page)[1:]
    for part in parts:
        section = _cell(part.split("</h4>", 1)[0])
        body = part.split("</h4>", 1)[1] if "</h4>" in part else ""
        m = re.search(r"<table.*?</table>", body, re.S)
        if not m:
            continue
        for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", m.group(0), re.S):
            th = re.search(r"<th[^>]*>(.*?)</th>", tr, re.S)
            tds = [_cell(td).replace("\xa0", " ").strip()
                   for td in re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)]
            if not tds or not tds[0] or "選択権" in tds[0]:
                continue
            label = zen2han(_cell(th.group(1)).replace("\xa0", "").strip()) if th else ""
            rnd = re.search(r"\d+", label)
            pos = next((re.sub(r"[\s\u3000\xa0]", "", t) for t in tds[1:]
                        if re.fullmatch(r"(投|捕|内野|外野)手", re.sub(r"[\s\u3000\xa0]", "", t))), "")
            picks.append({
                "team": team,
                "section": section,
                "ikusei": "育成" in section,
                "round": int(rnd.group(0)) if rnd else None,
                "label": label or ("希望枠" if "希望" in section or "自由" in section else ""),
                "name": clean_name(tds[0]),
                "pos": pos,
                "from": tds[-1] if len(tds) > 1 else "",
            })
    return picks


def fetch_draft(src, year):
    index = src.draft(year, "")
    codes = list(dict.fromkeys(re.findall(r"draftlist_(\w+)\.html", index)))
    if not codes:
        raise ValueError(f"{year}年のドラフトはまだない")
    picks = []
    for code in codes:
        picks += parse_draft_list(src.draft(year, f"draftlist_{code}.html"))
    return {"year": year, "picks": picks}


# ---------------------------------------------------------------- 在籍者名簿

REGISTER_URL = "https://npb.jp/history/register/{page}"
REGISTER_PAGES = ("a i u e o ka ki ku ke ko sa si su se so ta ti tu te to na ni nu ne no "
                  "ha hi hu he ho ma mi mu me mo ya yu yo ra ri ru re ro wa").split()
REGISTER_FROM = 2003          # これより前にしか在籍していない選手は保存しない
REGISTER_REFRESH_DAYS = 7     # 名簿はこの日数ごとに取り直す
YEAR_CHARS = r"[\d～途開幕閉\.春夏秋]*"


def _full_year(yy):
    yy = int(yy)
    return 1900 + yy if yy >= 36 else 2000 + yy


def parse_spans(text, this_year):
    """'16途～17巨人（育）,18途～19巨人' → [[2016,'巨人','育'],[2017,'巨人','育'],[2018,'巨人',''],...]"""
    spans, pending = [], []
    for tok in re.split(r"[,、・]", text):
        tok = tok.strip()
        m = re.match(rf"^({YEAR_CHARS})(.*?)(?:（([^）]*)）)?$", tok)
        if not m:
            continue
        nums = [int(x) for x in re.findall(r"(?<![\d.])\d{2}(?![\d])", m.group(1))]
        if nums:
            first = _full_year(nums[0])
            last = _full_year(nums[-1]) if len(nums) > 1 else (this_year if m.group(1).endswith("～") else first)
            pending.extend(range(first, last + 1))
        team = unicodedata.normalize("NFKC", m.group(2)).strip()
        if team:
            kind = m.group(3) or ""
            for y in pending:
                spans.append([y, team, kind])
            pending = []
    return spans


def parse_aliases(text):
    """'～06.2.27宇部銀次,2.28～赤見内銀次（銀次）' → ['宇部銀次', '赤見内銀次', '銀次']"""
    names = []
    for tok in re.split(r"[,、]", text):
        name = re.sub(rf"^{YEAR_CHARS}", "", tok.strip()).strip()
        if not name:
            continue
        m = re.match(r"^(.*?)（(.+)）$", name)
        found = [m.group(1), m.group(2)] if m else [name]
        for n in found:
            n = n.strip()
            if n and n not in names:
                names.append(n)
    return names


def parse_register(page, this_year):
    out = []
    for m in re.finditer(r'<(a|div) class="unit player_unit_\d+"(?: href="/bis/players/(\d+)\.html")?\s*>(.*?)</\1>',
                         page, re.S):
        tds = [_cell(td) for td in re.findall(r"<td[^>]*>(.*?)</td>", m.group(3), re.S)]
        if len(tds) < 3:
            continue
        head = re.sub(r"\s*（[^）]*）\s*$", "", tds[0]).strip()
        hist = tds[2]
        rename = ""
        if "［改名］" in hist:
            hist, rename = hist.split("［改名］", 1)
            if rename.strip().startswith("（読み方）"):    # 読み方だけの変更は名前ではない
                rename = ""
        spans = parse_spans(hist, this_year)
        if not spans or max(y for y, _, _ in spans) < REGISTER_FROM:
            continue
        out.append({"id": m.group(2), "name": clean_name(head),
                    "alias": parse_aliases(rename), "spans": spans})
    return out


def fetch_register(src, this_year):
    entries = []
    for pg in REGISTER_PAGES:
        entries += parse_register(src.register(f"index_{pg}.html"), this_year)
    return entries


# ---------------------------------------------------------------- 球団の選手一覧（いまの在籍）

ROSTER_URL = "https://npb.jp/bis/teams/rst_{code}.html"
ROSTER_TEAMS = {"g": "巨人", "t": "阪神", "db": "DeNA", "s": "ヤクルト", "c": "広島", "d": "中日",
                "h": "ソフトバンク", "f": "日本ハム", "l": "西武", "b": "オリックス", "e": "楽天", "m": "ロッテ"}


def parse_roster(page, team):
    """球団の選手一覧（支配下・育成）→ (年度, 現在の日付, [{id, name, team, no, ikusei, left, note}])。
    シーズン途中に退団・移籍した選手も「left」として載っている（備考に「6/8 自由契約」など）"""
    y = re.search(r"(\d{4})年度 選手一覧", page)
    d = re.search(r'class="rosterUpdate">(\d{4})年(\d{1,2})月(\d{1,2})日', page)
    if not y:
        raise ValueError(f"{team}の選手一覧が読めない")
    as_of = f"{d.group(1)}-{int(d.group(2)):02d}-{int(d.group(3)):02d}" if d else None
    out = []
    for part in re.split(r"<h3>", page)[1:]:
        ikusei = part.startswith("■ 育成")
        for m in re.finditer(r'<tr class="(rosterPlayer|rosterRetire)"><td>([^<]*)</td><td class="rosterRegister">'
                             r'<a href="/bis/players/(\d+)\.html">([^<]*)</a></td>.*?<td class="rosterdetail">(.*?)</td></tr>',
                             part, re.S):
            note = _cell(m.group(5))
            out.append({"id": m.group(3), "name": html.unescape(m.group(4)).strip(), "team": team, "no": m.group(2),
                        "ikusei": ikusei, "left": m.group(1) == "rosterRetire", "note": note})
    return int(y.group(1)), as_of, out


def fetch_roster(src):
    """12球団の選手一覧 → {year, as_of, players}"""
    year, as_of, players = None, None, []
    for code, team in ROSTER_TEAMS.items():
        y, d, ps = parse_roster(src.roster(code), team)
        year = max(year or y, y)
        as_of = max(as_of or d or "", d or "")
        players += ps
    if len(players) < 600:     # 12球団で900人ほど。読めていないページがある
        raise ValueError(f"選手一覧の人数が少ない（{len(players)}人）")
    return {"year": year, "as_of": as_of, "players": players}


class Store(Source):
    def roster(self, code):
        if self.dir:
            return (self.dir / f"rst_{code}.html").read_text(encoding="utf-8")
        text = fetch(ROSTER_URL.format(code=code))
        time.sleep(0.7)
        return text

    def register(self, page):
        if self.dir:
            return (self.dir / f"reg_{page.replace('index_', '')}").read_text(encoding="utf-8")
        text = fetch(REGISTER_URL.format(page=page))
        time.sleep(0.7)
        return text

    def draft(self, year, page):
        if self.dir:
            name = f"draft_{year}.html" if not page else f"draft_{year}_{page.split('_')[-1]}"
            return (self.dir / name).read_text(encoding="utf-8")
        text = fetch(DRAFT_URL.format(year=year, page=page))
        time.sleep(0.7)
        return text


def load(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, ValueError):
        return None


def save(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--year", type=int)
    ap.add_argument("--html-dir")
    ap.add_argument("--first", type=int, default=FIRST_YEAR)
    args = ap.parse_args(argv)

    src = Store(args.html_dir)
    data = Path(args.data)
    data.mkdir(parents=True, exist_ok=True)
    year = args.year or datetime.now(JST).year

    for y in range(args.first, year + 1):
        path = data / f"season_{y}.json"
        old = load(path)
        # 終わった年は取り直さない。ただし保存する項目を増やしたあと（列が足りない年）は1回だけ取り直す
        current = old and old.get("pit_cols") == PIT_COLS and old.get("fld_cols") == FLD_COLS and "leaders" in old
        if old and old.get("final") and y < year and current:
            continue
        try:
            season = fetch_season(src, y)
        except Exception as e:
            if y == year:          # 開幕前
                print(f"{y}年の成績はまだない: {e}", file=sys.stderr)
                continue
            if old:                # 取り直しに失敗した過去の年は、前のデータのまま
                print(f"注意: {y}年を取り直せない（前のデータのまま）: {e}", file=sys.stderr)
                continue
            raise
        season["final"] = y < year
        save(path, season)
        print(f"season {y}: 打者 {len(season['bat'])} 投手 {len(season['pit'])} 守備 {len(season['fld'])}")

    reg_path = data / "register.json"
    reg = load(reg_path)
    today = datetime.now(JST).date()
    if args.html_dir is None and (not reg or (today - datetime.fromisoformat(reg["fetched"]).date()).days
                                  >= REGISTER_REFRESH_DAYS):
        try:
            entries = fetch_register(src, year)
            save(reg_path, {"fetched": today.isoformat(), "players": entries})
            print(f"register: {len(entries)}人")
        except Exception as e:  # 名簿が取れなくても成績の集計は続ける
            print(f"注意: 在籍者名簿を取れない: {e}", file=sys.stderr)

    # 球団の選手一覧（いまの在籍）は毎日取り、年度ごとに保存する。
    # 在籍者名簿（前のシーズンまで）に載っていない今シーズンの新しい選手の結びつけと、現役・いまの所属に使う。
    # 年度が変わっても前の年度のファイルは残す（名簿に載るまでの、その年の新しい選手の結びつけに要る）
    try:
        ro = fetch_roster(src)
        ro["fetched"] = today.isoformat()
        save(data / f"roster_{ro['year']}.json", ro)
        print(f"roster {ro['year']}: {len(ro['players'])}人（{ro['as_of'] or '日付なし'}）")
    except Exception as e:  # 取れなくても前のファイルのまま
        print(f"注意: 球団の選手一覧を取れない: {e}", file=sys.stderr)

    for y in range(args.first, year + 1):
        path = data / f"draft_{y}.json"
        if load(path) and y < year:
            continue
        try:
            d = fetch_draft(src, y)
        except Exception as e:
            print(f"{y}年のドラフトはまだない: {e}", file=sys.stderr)
            continue
        save(path, d)
        print(f"draft {y}: {len(d['picks'])}人")
    return 0


if __name__ == "__main__":
    sys.exit(main())
