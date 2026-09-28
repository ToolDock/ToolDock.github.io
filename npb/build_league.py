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
  毎回取り直すのは今シーズンと、まだ無い過去のシーズン（FIRST_SEASON 以降）だけ。

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

# 計算ツールで選べる最初のシーズン。これ以降で未作成・未確定の年は、
# 次の実行時に一度だけ作ってファイルに残す（2020年は120試合の短縮シーズン）
FIRST_SEASON = 2020

BAT_KEYS = ["打席", "打数", "得点", "安打", "二塁打", "三塁打", "本塁打",
            "四球", "故意四", "死球", "犠飛", "三振", "盗塁", "盗塁刺"]


YEARLY = "https://npb.jp/bis/yearly/{name}_{year}.html"
YEARLY_NAME = {"c": "centralleague", "p": "pacificleague"}

# まとめて選べる時代。期間中のシーズンの値を単純平均する。
# 2004年以前は、NPB公式に四球・死球・犠飛や投手の被本塁打・与四球が
# 載っていないため、2005年の同じリーグの割合で補った推定値になる
ERAS = {
    "2001-2005": {"label": "2001〜2005年平均（飛ぶボール期）", "years": [2001, 2002, 2003, 2004, 2005]},
    "2011-2012": {"label": "2011〜2012年平均（統一球期）", "years": [2011, 2012]},
}
FULL_STATS_FROM = 2005   # これより前は年度別成績のページしかない


class Source:
    def __init__(self, html_dir):
        self.dir = Path(html_dir) if html_dir else None

    def get(self, year, page):
        if self.dir:
            return (self.dir / f"{year}_{page}.html").read_text(encoding="utf-8")
        text = fetch(BASE.format(year=year, page=page))
        time.sleep(0.7)
        return text

    def yearly(self, year, lg):
        if self.dir:
            return (self.dir / f"yearly_{lg}_{year}.html").read_text(encoding="utf-8")
        text = fetch(YEARLY.format(name=YEARLY_NAME[lg], year=year))
        time.sleep(0.7)
        return text


def table_heads(table):
    """表の見出し。年によって「打 率」「打<br>率」のように空白や改行が入るので除く。"""
    heads = [re.sub(r"\s", "", _cell(h)) for h in re.findall(r"<th[^>]*>(.*?)</th>", table, re.S)]
    # 古い年は長音が縦書きの「｜」になっている（セ｜ブ、ホ｜ル）
    heads = [{"セ｜ブ": "セーブ", "ホ｜ル": "ホールド", "ボ｜ク": "ボーク"}.get(h, h) for h in heads]
    # 古い年は投球回が「1060」「.2」の2列に分かれ、端数の列は見出しが空
    heads = ["投球回端数" if h == "" and i and heads[i - 1] == "投球回" else h
             for i, h in enumerate(heads)]
    # 古い年の個人投手成績は、選手名の見出しが「投手」
    return ["選手" if h == "投手" and "登板" in heads else h for h in heads]


def find_table(page, must=()):
    """見出しに must をすべて含む最初の表（HTML）。must が空なら最初の表。"""
    for table in re.findall(r"<table.*?</table>", page, re.S):
        heads = table_heads(table)
        if heads and all(k in heads for k in must):
            return table
    raise ValueError(f"表が見つからない: {must}")


def parse_table(page, must=()):
    """成績表 → (as_of, 行のリスト)。行は見出しをキーにした dict。
    列数の合わない行（注記の行など）は捨てる。"""
    as_of = None
    m = re.search(r"(\d{4})年(\d{1,2})月(\d{1,2})日\s*現在", page)
    if m:
        as_of = f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    table = find_table(page, must)
    heads = table_heads(table)
    rows = []
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", table, re.S):
        tds = [_cell(td) for td in re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)]
        if len(tds) == len(heads):
            rows.append(dict(zip(heads, tds)))
    return as_of, rows


def team_codes(tmb_page):
    """チーム打撃成績の表の中のリンク（idb1_t.html など）から球団コードを拾う。
    ページ上部のメニューにも別リーグのリンクがあるので、表の中だけを見る。"""
    table = find_table(tmb_page, ("チーム", "打数"))
    return list(dict.fromkeys(re.findall(r"idb1_(\w+)\.html", table)))


def player_key(name):
    """'*佐藤　輝明' → '佐藤輝明'（左打ち・両打ちの印と空白を除く）"""
    return re.sub(r"[\s\u3000*+]", "", name)


def ip_to_float(s):
    """'1234.1' → 1234.333…（小数部はアウト1つ・2つ）。
    アウトを取れずに降板した投手は「+」「0+」と書かれるので、数字以外は捨てる"""
    s = re.sub(r"[^\d.]", "", s)
    whole, _, frac = s.partition(".")
    return int(whole or 0) + (int(frac) if frac else 0) / 3


def ip_of(row):
    """行の投球回。端数が別の列になっている年にも対応する"""
    return ip_to_float(row["投球回"] + (row.get("投球回端数") or ""))


def num(v):
    return int(v) if str(v).strip() not in ("", "-") else 0


def total(rows, key):
    return sum(num(r[key]) for r in rows)


def position_player_batting(src, year, codes):
    """各球団の個人打撃成績から、投手を除いた野手の合計を出す。"""
    tot = dict.fromkeys(BAT_KEYS, 0)
    pitcher_pa = 0
    for code in codes:
        _, bat = parse_table(src.get(year, f"idb1_{code}"), ("選手", "打席"))
        _, pit = parse_table(src.get(year, f"idp1_{code}"), ("選手", "投球回"))
        pitchers = {player_key(r["選手"]) for r in pit}
        for r in bat:
            if player_key(r["選手"]) in pitchers:
                pitcher_pa += num(r["打席"])
                continue
            for k in BAT_KEYS:
                tot[k] += num(r[k])
    return tot, pitcher_pa


def pitching_totals(pit_rows):
    return {
        "ip": sum(ip_of(r) for r in pit_rows),
        "ra": total(pit_rows, "失点"), "er": total(pit_rows, "自責点"),
        "hr": total(pit_rows, "本塁打"), "bb": total(pit_rows, "四球"),
        "ibb": total(pit_rows, "故意四"), "hbp": total(pit_rows, "死球"),
        "so": total(pit_rows, "三振"),
    }


def league_constants(bat, runs, pit):
    """bat: 打撃の合計（BAT_KEYS）、runs: リーグの総得点、pit: pitching_totals の形"""
    pa, ab, h = bat["打席"], bat["打数"], bat["安打"]
    d2, d3, hr = bat["二塁打"], bat["三塁打"], bat["本塁打"]
    bb, ibb, hbp, sf = bat["四球"], bat["故意四"], bat["死球"], bat["犠飛"]
    sb, cs = bat["盗塁"], bat["盗塁刺"]
    s1 = h - d2 - d3 - hr
    ip = pit["ip"]

    woba = (WOBA_W["bb"] * (bb - ibb + hbp) + WOBA_W["1b"] * s1 + WOBA_W["2b"] * d2
            + WOBA_W["3b"] * d3 + WOBA_W["hr"] * hr) / (ab + bb - ibb + hbp + sf)
    era = 9 * pit["er"] / ip
    fip_const = era - (13 * pit["hr"] + 3 * (pit["bb"] - pit["ibb"] + pit["hbp"]) - 2 * pit["so"]) / ip
    run_cs = -(2 * pit["ra"] / (ip * 3) + 0.075)

    return {
        "woba": round(woba, 4),
        "woba_scale": WOBA_SCALE,
        "obp": round((h + bb + hbp) / (ab + bb + hbp + sf), 4),
        "avg": round(h / ab, 4),
        "slg": round((s1 + 2 * d2 + 3 * d3 + 4 * hr) / ab, 4),
        "r_pa": round(bat["得点"] / pa, 5),
        "era": round(era, 3),
        "ra9": round(9 * pit["ra"] / ip, 3),
        "fip_const": round(fip_const, 3),
        "run_cs": round(run_cs, 4),
        "wsb_rate": round((sb * RUN_SB + cs * run_cs) / (s1 + bb + hbp - ibb), 5),
        "rpw": round(10 * math.sqrt((runs + pit["ra"]) / ip), 3),
    }


# 2004年以前の推定に使う、完全な成績がある年の内訳（年, リーグ）→ dict
_DETAIL = {}


def build_season(src, year):
    season = {"as_of": None}
    for lg, key, label in LEAGUES:
        tmb_page = src.get(year, f"tmb_{lg}")
        as_of, team_bat = parse_table(tmb_page, ("チーム", "打席"))
        _, team_pit = parse_table(src.get(year, f"tmp_{lg}"), ("チーム", "投球回"))
        if not team_bat or total(team_bat, "打席") == 0:
            raise ValueError(f"{year}年 {label} はまだ成績がない")
        bat, pitcher_pa = position_player_batting(src, year, team_codes(tmb_page))
        if bat["打席"] + pitcher_pa != total(team_bat, "打席"):
            print(f"注意: {year} {label} 個人の打席合計がチーム成績と合わない", file=sys.stderr)
        team_tot = {k: total(team_bat, k) for k in BAT_KEYS}
        runs = team_tot["得点"]
        pit = pitching_totals(team_pit)
        c = league_constants(bat, runs, pit)
        c["label"] = label
        c["pitcher_pa"] = pitcher_pa
        season[key] = c
        season["as_of"] = season["as_of"] or as_of
        _DETAIL[(year, lg)] = {"team": team_tot, "pos": bat, "pit": pit, "runs": runs,
                               "all": league_constants(team_tot, runs, pit), "const": c}
    return season


def season_from_store(st):
    """stats_store.py が保存した season_<年>.json から、build_season と同じ形を作る"""
    bc = {c: i for i, c in enumerate(st["bat_cols"])}
    pc = {c: i for i, c in enumerate(st["pit_cols"])}
    pitchers = {(r[pc["team"]], r[pc["name"]]) for r in st["pit"]}
    season = {"as_of": st.get("as_of")}
    for lg, key, label in LEAGUES:
        codes = {c for c, t in st["teams"].items() if t["league"] == key}
        bat = dict.fromkeys(BAT_KEYS, 0)
        pitcher_pa = 0
        for r in st["bat"]:
            if r[bc["team"]] not in codes:
                continue
            if (r[bc["team"]], r[bc["name"]]) in pitchers:
                pitcher_pa += r[bc["打席"]]
                continue
            for k in BAT_KEYS:
                bat[k] += r[bc[k]]
        tot = st["totals"][key]
        runs = tot["bat"]["得点"]
        pit = tot["pit"]
        c = league_constants(bat, runs, pit)
        c["label"] = label
        c["pitcher_pa"] = pitcher_pa
        season[key] = c
        _DETAIL[(st["year"], lg)] = {"team": {k: tot["bat"][k] for k in BAT_KEYS}, "pos": bat, "pit": pit,
                                     "runs": runs, "all": league_constants(tot["bat"], runs, pit), "const": c}
    if st.get("final"):
        season["final"] = True
    return season


def estimate_season(src, year, ref_year=FULL_STATS_FROM):
    """2004年以前：年度別成績のページ（打数・安打・本塁打・得点・盗塁、防御率・投球回・
    奪三振・失点）に、ref_year の同じリーグの割合を当てはめて推定する。"""
    if not any(k[0] == ref_year for k in _DETAIL):
        build_season(src, ref_year)
    season = {"as_of": None, "estimated": True}
    for lg, key, label in LEAGUES:
        ref = _DETAIL[(ref_year, lg)]
        rt = ref["team"]
        page = src.yearly(year, lg)
        _, bat_rows = parse_table(page, ("チーム", "打数", "盗塁"))
        _, pit_rows = parse_table(page, ("チーム", "防御率", "投球回"))

        ab = total(bat_rows, "打数")
        bat = {"打数": ab, "安打": total(bat_rows, "安打"), "二塁打": total(bat_rows, "二塁打"),
               "三塁打": total(bat_rows, "三塁打"), "本塁打": total(bat_rows, "本塁打"),
               "得点": total(bat_rows, "得点"), "盗塁": total(bat_rows, "盗塁")}
        for k in ("打席", "四球", "故意四", "死球", "犠飛", "三振"):
            bat[k] = round(ab * rt[k] / rt["打数"])
        bat["盗塁刺"] = round(bat["盗塁"] * rt["盗塁刺"] / rt["盗塁"])

        ip = sum(ip_of(r) for r in pit_rows)
        er = sum(float(r["防御率"]) * ip_of(r) / 9 for r in pit_rows)
        # 交流戦が始まる前なので、リーグの被本塁打・与四死球は打撃側と同じ
        pit = {"ip": ip, "ra": total(pit_rows, "失点"), "er": er, "so": total(pit_rows, "奪三振"),
               "hr": bat["本塁打"], "bb": bat["四球"], "ibb": bat["故意四"], "hbp": bat["死球"]}

        allc = league_constants(bat, bat["得点"], pit)
        # 投手の打席を除いた分の差は、ref_year の差をそのまま使う
        c = dict(allc)
        for k in ("woba", "obp", "avg", "slg", "wsb_rate"):
            c[k] = round(allc[k] + ref["const"][k] - ref["all"][k], 5 if k == "wsb_rate" else 4)
        c["r_pa"] = round(allc["r_pa"] * ref["const"]["r_pa"] / ref["all"]["r_pa"], 5)
        c["label"] = label
        season[key] = c
    return season


def build_era(src, era, known):
    years = ERAS[era]["years"]
    per_year = []
    for y in years:
        if str(y) in known:
            per_year.append(known[str(y)])
        elif y < FULL_STATS_FROM:
            per_year.append(estimate_season(src, y))
        else:
            per_year.append(build_season(src, y))
    out = {"label": ERAS[era]["label"], "years": years, "final": True,
           "estimated_years": [y for y in years if y < FULL_STATS_FROM]}
    for lg, key, label in LEAGUES:
        vals = [s[key] for s in per_year]
        c = {"label": label}
        for k, v in vals[0].items():
            if isinstance(v, (int, float)) and k != "pitcher_pa":
                c[k] = round(sum(x[k] for x in vals) / len(vals), 5)
        out[key] = c
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--year", type=int)
    ap.add_argument("--html-dir")
    ap.add_argument("--data", help="stats_store.py の保存先。指定するとそこから計算する")
    args = ap.parse_args(argv)

    src = Source(args.html_dir)
    out = Path(args.out)
    if args.data:
        return main_from_store(src, Path(args.data), out)
    path = out / "league.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, ValueError):
        data = {}
    seasons = data.get("seasons", {})
    eras = data.get("eras", {})

    year = args.year or datetime.now(JST).year
    try:
        seasons[str(year)] = build_season(src, year)
    except Exception as e:  # 開幕前は今シーズンの成績がない
        if args.year:
            raise
        print(f"{year}年は作れない: {e}", file=sys.stderr)
    for y in range(FIRST_SEASON, year):
        key = str(y)
        if key in seasons and seasons[key].get("final"):
            continue
        seasons[key] = build_season(src, y)
        seasons[key]["final"] = True

    # 時代の平均は一度作れば変わらない
    for era in ERAS:
        if era not in eras:
            eras[era] = build_era(src, era, seasons)

    latest = max(seasons, key=int)
    payload = {"latest": int(latest),
               "seasons": dict(sorted(seasons.items(), reverse=True)),
               "eras": eras}
    out.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False)[:3000])
    return 0


def main_from_store(src, data_dir, out):
    """保存済みの個人成績（npb/data/season_<年>.json）から、全シーズンのリーグ平均を作る"""
    path = out / "league.json"
    try:
        eras = json.loads(path.read_text(encoding="utf-8")).get("eras", {})
    except (FileNotFoundError, ValueError):
        eras = {}
    seasons = {}
    for f in sorted(data_dir.glob("season_*.json")):
        st = json.loads(f.read_text(encoding="utf-8"))
        seasons[str(st["year"])] = season_from_store(st)
    for era in ERAS:
        if era not in eras:
            eras[era] = build_era(src, era, seasons)
    latest = max(seasons, key=int)
    payload = {"latest": int(latest),
               "seasons": dict(sorted(seasons.items(), reverse=True)),
               "eras": eras}
    out.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"league.json: {len(seasons)}シーズン・{len(eras)}時代")
    return 0


if __name__ == "__main__":
    sys.exit(main())
