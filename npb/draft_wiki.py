#!/usr/bin/env python3
"""ドラフトの指名選手を、Wikipedia（日本語版）の記事から取る。NPB公式に届かないとき用。

2026-10-21 から GitHub Actions（米国）から npb.jp へ接続できなくなったため、
その年のドラフトの指名選手を、ja.wikipedia.org の「YYYY年度新人選手選択会議 (日本プロ野球)」の
「球団別指名選手一覧」から読み、npb/data/draft_YYYY.json に stats_store.py と同じ形で書く。

    python3 npb/draft_wiki.py --data npb/data            # 今年
    python3 npb/draft_wiki.py --data npb/data --year 2025 --check   # NPB公式の保存分と突き合わせるだけ

- NPB公式から取った保存分（"source" が無いもの）は上書きしない。npb.jp に届くようになれば、
  stats_store.py が公式の一覧で上書きする
- 名前は記事の表示のまま（姓と名の間の空白は無い）。照合は空白を無視するので、成績の結びつけには困らない
- 指名の途中で記事が書きかけでも、読めた行だけ書く（指名が進めば、次の実行で増える）
"""

import argparse
import json
import re
import sys
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_magic import JST  # noqa: E402
from people import key  # noqa: E402
from stats_store import load, save, team_short, zen2han  # noqa: E402

API = "https://ja.wikipedia.org/w/api.php"
TITLE = "{year}年度新人選手選択会議 (日本プロ野球)"
UA = "ToolDock/1.0 (https://tooldock.github.io/; draft results)"
POSITIONS = ("投手", "捕手", "内野手", "外野手")


def fetch_wikitext(year):
    q = urllib.parse.urlencode({"action": "parse", "page": TITLE.format(year=year), "prop": "wikitext",
                                "format": "json", "formatversion": "2"})
    req = urllib.request.Request(f"{API}?{q}", headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.loads(r.read().decode("utf-8"))
    if "error" in data:
        raise ValueError(f"{year}年の記事が無い: {data['error'].get('info')}")
    return data["parse"]["wikitext"]


def plain(cell):
    """wiki の書式を外して、表示される文字だけにする"""
    s = re.sub(r"<ref[^>]*/>|<ref[^>]*>.*?</ref>", "", cell, flags=re.S)
    s = re.sub(r"\{\{[^{}]*\}\}", "", s)
    s = re.sub(r"\[\[(?:[^|\]]*\|)?([^\]]*)\]\]", r"\1", s)
    s = re.sub(r"<br\s*/?>", "", s)
    s = re.sub(r"<[^>]+>", "", s)
    s = s.replace("'''", "").replace("''", "")
    if re.match(r"^\s*style\s*=", s) and "|" in s:     # 「style=...|中身」のセル
        s = s.split("|", 1)[1]
    return s.strip()


def parse(wikitext):
    """「球団別指名選手一覧」の各球団の表 → stats_store.py の draft_YYYY.json と同じ picks"""
    m = re.search(r"==\s*球団別指名選手一覧\s*==(.*?)(?:\n==[^=]|\Z)", wikitext, re.S)
    if not m:
        return []
    picks = []
    for sec in re.split(r"\n===\s*", m.group(1))[1:]:
        team_full, body = sec.split("===", 1)
        team = team_short(team_full.strip())
        section, label = "新人選手選択会議", None
        for line in body.split("\n"):
            line = line.strip()
            if "育成選手選択会議" in line:
                section = "育成選手選択会議"
            elif "新人選手選択会議" in line:
                section = "新人選手選択会議"
            elif re.match(r"^!\s*\S*\d+\s*位", zen2han(line)) and "!!" not in line:
                label = re.search(r"\d+\s*位", zen2han(line)).group(0).replace(" ", "")
            elif line.startswith("|") and not line.startswith(("|-", "|}", "|+")) and label:
                raw = line[1:].split("||")
                cells = [plain(c) for c in raw]
                # 名前は記事の見出し（リンク先）を優先する。表示だけ異体字のことがある
                # （[[山崎太陽|山埼太陽]] → NPB公式は「山崎」）。「伊藤樹 (野球)」の括弧は外す
                link = re.search(r"\[\[([^|\]]+)", raw[0]) if raw else None
                name = re.sub(r"\s*\(.*?\)$", "", link.group(1)).strip() if link else (cells[0] if cells else "")
                if not name or set(name) <= set("-―ー— "):
                    label = None
                    continue
                pos = next((c for c in cells[1:] if c in POSITIONS), "")
                frm = cells[2] if len(cells) > 2 else ""
                picks.append({
                    "team": team,
                    "section": section,
                    "ikusei": section == "育成選手選択会議",
                    "round": int(re.search(r"\d+", label).group(0)),
                    "label": label,
                    "name": name,
                    "pos": pos,
                    "from": frm,
                })
                label = None
    return picks


def check(picks, official):
    """NPB公式から保存した一覧と、球団・会議・順位・名前・守備を突き合わせる"""
    def sig(p):
        return (p["team"], p["ikusei"], p["round"], key(p["name"]), p["pos"])
    a, b = {sig(p) for p in picks}, {sig(p) for p in official}
    print(f"Wikipedia {len(picks)}人 / NPB公式 {len(official)}人 / 一致 {len(a & b)}人")
    for s in sorted(b - a):
        print("  公式にだけある:", s)
    for s in sorted(a - b):
        print("  記事にだけある:", s)
    return a == b


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--year", type=int)
    ap.add_argument("--check", action="store_true", help="保存済みの一覧と突き合わせるだけ（書かない）")
    args = ap.parse_args(argv)
    year = args.year or datetime.now(JST).year
    path = Path(args.data) / f"draft_{year}.json"

    picks = parse(fetch_wikitext(year))
    old = load(path)
    if args.check:
        return 0 if old and check(picks, old["picks"]) else 1
    if old and "source" not in old:
        print(f"{year}年はNPB公式の一覧を保存済みなので、Wikipediaでは上書きしない")
        return 0
    if not picks:
        print(f"{year}年のドラフトはまだ記事に無い")
        return 0
    if old and len(picks) < len(old["picks"]):
        print(f"記事の指名が前回より少ない（{len(picks)} < {len(old['picks'])}人）ので、書き換えない")
        return 0
    save(path, {"year": year, "picks": picks, "source": "wikipedia"})
    print(f"draft {year}: {len(picks)}人（Wikipedia）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
