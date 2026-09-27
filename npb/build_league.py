#!/usr/bin/env python3
"""NPB公式の成績から、WAR計算に使うリーグ平均値を作る。

    python3 npb/build_league.py --out war
    python3 npb/build_league.py --html-dir _probe --year 2026 --out /tmp/war

出力は war/league.json。/war/ の計算ツールが読み込む。
式の枠組みは DELTA（1.02）の WAR の説明に合わせている。

- 打撃の平均（wOBA・打席あたり得点・盗塁）は「野手」の平均。
  セ・リーグは投手も打席に立つので、各球団の個人打撃成績から
  投手（個人投手成績に名前がある選手）の打席を除いて集計する。
- 失点・投球回・RPW などはチーム成績の合計から出す。
- 過去のシーズンは一度作れば変わらないので、ファイルに残して使い回す。
  毎回取り直すのは今シーズンと、まだ無い前年だけ。

--html-dir のときは、<dir>/<年>_tmb_c.html、<年>_idb1_t.html のような
名前のファイルを読む。
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_magic import JST, _cell, fetch  # noqa: E402

BASE = "https://npb.jp/bis/{year}/stats/{page}.html"
LEAGUES = [("c", "central", "セ・リーグ"), ("p", "pacific", "パ・リーグ")]

# wOBA の係数（打席結果ごとの得点価値）と、wOBA を得点に戻す係数
WOBA_W = {"bb": 0.7, "1b": 0.9, "2b": 1.3, "3b": 1.6, "hr": 2.0}
WOBA_SCALE = 1.24
RUN_SB = 0.2

BAT_KEYS = ["打席", "打数", "得点", "安打", "二塁打", "三塁打", "本塁打",
            "四球", "故意四", "死球", "犠飛", "三振", "盗塁", "盗塁刺"]


class Source:
    def __init__(self, html_dir):
        self.dir = Path(html_dir) if html_dir else None

    def get(self, year, page):
        if self.dir:
            return (self.dir / f"{year}_{page}.html").read_text(encoding="utf-8")
        text = fetch(BASE.format(year=year, page=page))
        time.sleep(0.7)
        return text


def parse_table(page):
    """ページ内の最初の成績表 → (as_of, 行のリスト)。行は見出しをキーにした dict。"""
    as_of = None
    m = re.search(r"(\d{4})年(\d{1,2})月(\d{1,2})日\s*現在", page)
    if m:
        as_of = f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    table = re.search(r"<table.*?</table>", page[page.index("<table"):], re.S).group(0)
    heads = [_cell(h) for h in re.findall(r"<th[^>]*>(.*?)</th>", table, re.S)]
    heads = [h.split()[-1] if h else h for h in heads]   # 見出しに <tr> が混ざることがある
    rows = []
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", table, re.S):
        tds = [_cell(td) for td in re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)]
        if tds:
            rows.append(dict(zip(heads, tds)))
    return as_of, rows


def team_codes(tmb_page):
    """チーム打撃成績のリンク（idb1_t.html など）から球団コードを拾う。"""
    return list(dict.fromkeys(re.findall(r"idb1_(\w+)\.html", tmb_page)))


def player_key(name):
    """'*佐藤　輝明' → '佐藤輝明'（左打ち・両打ちの印と空白を除く）"""
    return re.sub(r"[\s　*+]", "", name)


def ip_to_float(s):
    """'1234.1' → 1234.333…（小数部はアウト1つ・2つ）"""
    whole, _, frac = s.partition(".")
    return int(whole) + (int(frac) if frac else 0) / 3


def total(rows, key):
    return sum(int(r[key]) for r in rows)


def position_player_batting(src, year, codes):
    """各球団の個人打撃成績から、投手を除いた野手の合計を出す。"""
    tot = dict.fromkeys(BAT_KEYS, 0)
    pitcher_pa = 0
    for code in codes:
        _, bat = parse_table(src.get(year, f"idb1_{code}"))
        _, pit = parse_table(src.get(year, f"idp1_{code}"))
        pitchers = {player_key(r["選手"]) for r in pit}
        for r in bat:
            if player_key(r["選手"]) in pitchers:
                pitcher_pa += int(r["打席"])
                continue
            for k in BAT_KEYS:
                tot[k] += int(r[k])
    return tot, pitcher_pa


def league_constants(bat, team_bat_rows, pit_rows):
    pa, ab, h = bat["打席"], bat["打数"], bat["安打"]
    d2, d3, hr = bat["二塁打"], bat["三塁打"], bat["本塁打"]
    bb, ibb, hbp, sf, so = bat["四球"], bat["故意四"], bat["死球"], bat["犠飛"], bat["三振"]
    sb, cs, runs_pos = bat["盗塁"], bat["盗塁刺"], bat["得点"]
    s1 = h - d2 - d3 - hr

    runs = total(team_bat_rows, "得点")
    ip = sum(ip_to_float(r["投球回"]) for r in pit_rows)
    ra, er = total(pit_rows, "失点"), total(pit_rows, "自責点")
    p_hr, p_bb, p_ibb = total(pit_rows, "本塁打"), total(pit_rows, "四球"), total(pit_rows, "故意四")
    p_hbp, p_so = total(pit_rows, "死球"), total(pit_rows, "三振")

    woba = (WOBA_W["bb"] * (bb - ibb + hbp) + WOBA_W["1b"] * s1 + WOBA_W["2b"] * d2
            + WOBA_W["3b"] * d3 + WOBA_W["hr"] * hr) / (ab + bb - ibb + hbp + sf)

    era = 9 * er / ip
    fip_const = era - (13 * p_hr + 3 * (p_bb - p_ibb + p_hbp) - 2 * p_so) / ip
    run_cs = -(2 * ra / (ip * 3) + 0.075)

    return {
        "woba": round(woba, 4),
        "woba_scale": WOBA_SCALE,
        "obp": round((h + bb + hbp) / (ab + bb + hbp + sf), 4),
        "avg": round(h / ab, 4),
        "slg": round((s1 + 2 * d2 + 3 * d3 + 4 * hr) / ab, 4),
        "r_pa": round(runs_pos / pa, 5),
        "era": round(era, 3),
        "ra9": round(9 * ra / ip, 3),
        "fip_const": round(fip_const, 3),
        "run_cs": round(run_cs, 4),
        "wsb_rate": round((sb * RUN_SB + cs * run_cs) / (s1 + bb + hbp - ibb), 5),
        "rpw": round(10 * math.sqrt((runs + ra) / ip), 3),
    }


def build_season(src, year):
    season = {"as_of": None}
    for lg, key, label in LEAGUES:
        tmb_page = src.get(year, f"tmb_{lg}")
        as_of, team_bat = parse_table(tmb_page)
        _, team_pit = parse_table(src.get(year, f"tmp_{lg}"))
        if not team_bat or total(team_bat, "打席") == 0:
            raise ValueError(f"{year}年 {label} はまだ成績がない")
        bat, pitcher_pa = position_player_batting(src, year, team_codes(tmb_page))
        if abs(bat["打席"] + pitcher_pa - total(team_bat, "打席")) > 0:
            print(f"注意: {year} {label} 個人の打席合計がチーム成績と合わない", file=sys.stderr)
        c = league_constants(bat, team_bat, team_pit)
        c["label"] = label
        c["pitcher_pa"] = pitcher_pa
        season[key] = c
        season["as_of"] = season["as_of"] or as_of
    return season


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--year", type=int)
    ap.add_argument("--html-dir")
    args = ap.parse_args(argv)

    src = Source(args.html_dir)
    out = Path(args.out)
    path = out / "league.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        seasons = data.get("seasons", {})
    except (FileNotFoundError, ValueError):
        seasons = {}

    year = args.year or datetime.now(JST).year
    try:
        seasons[str(year)] = build_season(src, year)
    except Exception as e:  # 開幕前は今シーズンの成績がない
        if args.year:
            raise
        print(f"{year}年は作れない: {e}", file=sys.stderr)
    prev = str(year - 1)
    if prev not in seasons or not seasons[prev].get("final"):
        seasons[prev] = build_season(src, year - 1)
        seasons[prev]["final"] = True

    latest = max(seasons, key=int)
    payload = {"latest": int(latest), "seasons": dict(sorted(seasons.items(), reverse=True))}
    out.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
