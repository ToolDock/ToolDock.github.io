#!/usr/bin/env python3
"""NPB公式のチーム打撃・投手成績から、WAR計算に使うリーグ平均値を作る。

    python3 npb/build_league.py --out war
    python3 npb/build_league.py --html-dir _probe --year 2026 --out /tmp/war

出力は war/league.json。/war/ の計算ツールが読み込む。
式の枠組みは DELTA（1.02）の WAR の説明に合わせている。
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

URL = "https://npb.jp/bis/{year}/stats/{kind}_{lg}.html"
LEAGUES = [("c", "central", "セ・リーグ"), ("p", "pacific", "パ・リーグ")]

# wOBA の係数（打席結果ごとの得点価値）と、wOBA を得点に戻す係数
WOBA_W = {"bb": 0.7, "1b": 0.9, "2b": 1.3, "3b": 1.6, "hr": 2.0}
WOBA_SCALE = 1.24
RUN_SB = 0.2


def parse_table(page):
    """表の見出しをキーにした行のリスト（数字は文字列のまま）。"""
    as_of = None
    m = re.search(r"(\d{4})年(\d{1,2})月(\d{1,2})日\s*現在", page)
    if m:
        as_of = f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    table = re.search(r"<table.*?</table>", page[page.index("チーム"):], re.S).group(0)
    heads = [_cell(h) for h in re.findall(r"<th[^>]*>(.*?)</th>", table, re.S)]
    rows = []
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", table, re.S):
        tds = [_cell(td) for td in re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)]
        if tds:
            rows.append(dict(zip(heads, tds)))
    return as_of, rows


def ip_to_float(s):
    """'1234.1' → 1234.333…（小数部はアウト1つ・2つ）"""
    whole, _, frac = s.partition(".")
    return int(whole) + (int(frac) if frac else 0) / 3


def total(rows, key):
    return sum(int(r[key]) for r in rows)


def league_constants(bat_rows, pit_rows):
    pa, ab, h = total(bat_rows, "打席"), total(bat_rows, "打数"), total(bat_rows, "安打")
    d2, d3, hr = total(bat_rows, "二塁打"), total(bat_rows, "三塁打"), total(bat_rows, "本塁打")
    bb, ibb, hbp = total(bat_rows, "四球"), total(bat_rows, "故意四"), total(bat_rows, "死球")
    sf, so = total(bat_rows, "犠飛"), total(bat_rows, "三振")
    sb, cs = total(bat_rows, "盗塁"), total(bat_rows, "盗塁刺")
    runs = total(bat_rows, "得点")
    s1 = h - d2 - d3 - hr

    ip = sum(ip_to_float(r["投球回"]) for r in pit_rows)
    ra, er = total(pit_rows, "失点"), total(pit_rows, "自責点")
    p_hr, p_bb, p_ibb = total(pit_rows, "本塁打"), total(pit_rows, "四球"), total(pit_rows, "故意四")
    p_hbp, p_so = total(pit_rows, "死球"), total(pit_rows, "三振")

    woba_den = ab + bb - ibb + hbp + sf
    woba = (WOBA_W["bb"] * (bb - ibb + hbp) + WOBA_W["1b"] * s1 + WOBA_W["2b"] * d2
            + WOBA_W["3b"] * d3 + WOBA_W["hr"] * hr) / woba_den
    obp = (h + bb + hbp) / (ab + bb + hbp + sf)

    era = 9 * er / ip
    ra9 = 9 * ra / ip
    fip_const = era - (13 * p_hr + 3 * (p_bb - p_ibb + p_hbp) - 2 * p_so) / ip

    runs_per_out = ra / (ip * 3)
    run_cs = -(2 * runs_per_out + 0.075)
    wsb_rate = (sb * RUN_SB + cs * run_cs) / (s1 + bb + hbp - ibb)

    rpw = 10 * math.sqrt((runs + ra) / ip)

    return {
        "woba": round(woba, 4),
        "woba_scale": WOBA_SCALE,
        "obp": round(obp, 4),
        "avg": round(h / ab, 4),
        "slg": round((s1 + 2 * d2 + 3 * d3 + 4 * hr) / ab, 4),
        "r_pa": round(runs / pa, 5),
        "era": round(era, 3),
        "ra9": round(ra9, 3),
        "fip_const": round(fip_const, 3),
        "run_cs": round(run_cs, 4),
        "wsb_rate": round(wsb_rate, 5),
        "rpw": round(rpw, 3),
        "k_pct": round(so / pa, 4),
        "bb_pct": round(bb / pa, 4),
    }


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--year", type=int)
    ap.add_argument("--html-dir")
    args = ap.parse_args(argv)

    year = args.year or datetime.now(JST).year

    def load(y):
        out, as_of = {}, None
        for lg, key, label in LEAGUES:
            pages = {}
            for kind in ("tmb", "tmp"):
                if args.html_dir:
                    p = Path(args.html_dir) / f"{kind}_{lg}.html"
                    if not p.exists():
                        continue
                    pages[kind] = p.read_text(encoding="utf-8")
                else:
                    pages[kind] = fetch(URL.format(year=y, kind=kind, lg=lg))
                    time.sleep(1)
            if len(pages) < 2:
                continue
            d, bat = parse_table(pages["tmb"])
            _, pit = parse_table(pages["tmp"])
            as_of = as_of or d
            c = league_constants(bat, pit)
            c["label"] = label
            out[key] = c
        return out, as_of

    try:
        leagues, as_of = load(year)
        if not leagues:
            raise ValueError("データなし")
    except Exception as e:  # 開幕前などは前年
        if args.year or args.html_dir:
            raise
        print(f"{year}年が使えないので前年にする: {e}", file=sys.stderr)
        year -= 1
        leagues, as_of = load(year)

    payload = {"year": year, "as_of": as_of, **leagues}
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "league.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
