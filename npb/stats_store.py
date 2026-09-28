#!/usr/bin/env python3
"""NPB公式の個人成績とドラフト指名選手を、年ごとに npb/data/ へ集める。

    python3 npb/stats_store.py --data npb/data            # 今シーズンを取り直し、足りない年を埋める
    python3 npb/stats_store.py --data /tmp/d --html-dir x # 手元のHTMLで試す

保存するもの
  season_<年>.json … 12球団の個人打撃・投手・守備成績と、リーグごとのチーム成績の合計
  draft_<年>.json  … その年のドラフト会議の指名選手（球団・順位・守備位置・出身）

過去の年は一度作れば変わらないので取り直さない（final が付く）。
毎日取り直すのは今シーズンと、まだ指名が出ていない今年のドラフトだけ。
NPBのサーバーに負担をかけないよう、1ページごとに間を空ける。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
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
            "outs", "安打", "本塁打", "四球", "故意四", "死球", "三振", "失点", "自責点"]
FLD_COLS = ["team", "name", "pos", "試合"]
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
                out.append([clean_name(name), best[0], num(row["試合"])])
    return out


def parse_fielding_old(page):
    """古い年の個人守備成績：1つの表の中に「【一塁手】」の見出し行が挟まっている"""
    out = []
    pos = None
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", page, re.S):
        head = re.search(r"【(.+?)】", _cell(tr)) if "<th" in tr else None
        if head:
            pos = head.group(1) if head.group(1) in POSITIONS else None
            continue
        if not pos:
            continue
        tds = [_cell(td) for td in re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)]
        m = re.search(r'<td class="stplayer">(.*?)</td>\s*<td[^>]*>(.*?)</td>', tr, re.S)
        if m:
            name, g = _cell(m.group(1)), _cell(m.group(2))
            if name and re.fullmatch(r"\d+", g):
                out.append([clean_name(name), pos, int(g)])
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
            for name, pos, g in fetch_fielding(src, year, code):
                fld.append([code, name, pos, g])
        except Exception as e:  # 守備は無くても打撃・投手の集計はできる
            print(f"注意: {year} {code} 守備成績を読めない: {e}", file=sys.stderr)

    return {"year": year, "as_of": as_of, "teams": teams, "totals": totals,
            "bat_cols": BAT_COLS, "bat": bat, "pit_cols": PIT_COLS, "pit": pit,
            "fld_cols": FLD_COLS, "fld": fld}


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


class Store(Source):
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

    # 守備成績が空の年（古いページ形式を読めなかった年）は、守備だけ取り直す
    for y in range(args.first, year):
        path = data / f"season_{y}.json"
        old = load(path)
        if old and old.get("final") and not old.get("fld"):
            fld = []
            for code in old["teams"]:
                fld += [[code, n, p, g] for n, p, g in fetch_fielding(src, y, code)]
            old["fld"] = fld
            save(path, old)
            print(f"season {y}: 守備 {len(fld)} を補完")

    for y in range(args.first, year + 1):
        path = data / f"season_{y}.json"
        old = load(path)
        if old and old.get("final") and y < year:
            continue
        try:
            season = fetch_season(src, y)
        except Exception as e:
            if y == year:          # 開幕前
                print(f"{y}年の成績はまだない: {e}", file=sys.stderr)
                continue
            raise
        season["final"] = y < year
        save(path, season)
        print(f"season {y}: 打者 {len(season['bat'])} 投手 {len(season['pit'])} 守備 {len(season['fld'])}")

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
