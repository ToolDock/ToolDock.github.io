"""順位推移グラフの元データ（試合ごとの結果）を集める。

npb/data/games_<年>.json に、その年のレギュラーシーズンの全試合を
[日付, ホーム, ビジター, ホームの得点, ビジターの得点] で並べて保存する。

- 今季（2026年〜）：NPB公式の月別の日程・結果（/games/<年>/schedule_<月>_detail.html）
  クライマックスシリーズ・日本シリーズも同じページに載るので、URLの末尾の「同じカードの何試合目か」
  （/scores/2026/1010/g-db-01/ の 01）で見分ける。同じカードの同じ番号が既に行われていれば公式戦ではない
  （中止になった試合の振り替えは、中止になった試合と同じ番号で行われるので公式戦として数える）
- 過去の年：NPB公式の月別カレンダー（/bis/<年>/calendar/index_<月>.html）。
  「巨 3 - 2 デ」の形で、左がホーム。「*」は中止、「セ」「パ」はオールスター。
  ポストシーズンも載っているので、日付の順に数えて、球団の公式戦の試合数（season_<年>.json）を
  終えたあとの試合は除く
- 終わった年は、球団ごとの勝・敗・分を season_<年>.json（投手の勝敗の合計と試合数）と照らし合わせ、
  合わないときは保存しない（次の更新でもう一度取りにいく）
"""

from __future__ import annotations

import json
import re
import sys
import time
import urllib.error
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_magic import fetch  # noqa: E402

UA = "Mozilla/5.0 (compatible; ToolDock/1.0; +https://tooldock.github.io/)"
FIRST_YEAR = 2005
CUR_URL = "https://npb.jp/games/{year}/schedule_{m:02d}_detail.html"
OLD_URL = "https://npb.jp/bis/{year}/calendar/index_{m:02d}.html"
CUR_MONTHS = range(3, 12)     # 3月〜11月（無い月は404）
OLD_MONTHS = range(4, 12)     # index_04 は「3・4月」

ABBR = {"巨": "巨人", "ヤ": "ヤクルト", "神": "阪神", "広": "広島", "中": "中日", "デ": "DeNA", "横": "横浜",
        "ソ": "ソフトバンク", "日": "日本ハム", "西": "西武", "オ": "オリックス", "ロ": "ロッテ", "楽": "楽天"}
CENTRAL = {"巨人", "ヤクルト", "阪神", "広島", "中日", "DeNA", "横浜"}
PACIFIC = {"ソフトバンク", "日本ハム", "西武", "オリックス", "ロッテ", "楽天"}


def league_of(team):
    return "central" if team in CENTRAL else "pacific"


def get(url):
    """無い月（404）は None。それ以外の失敗は、build_magic.fetch と同じく何度か取り直す"""
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=30) as r:
            return r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
    except Exception:  # noqa: BLE001
        pass
    return fetch(url)


# ---------------------------------------------------------------- 読み取り

ROW = re.compile(r'<tr id="date(\d{2})(\d{2})"[^>]*>(.*?)</tr>', re.S)


def parse_current(page, year, seen):
    """今季の月別ページ → 公式戦の試合。seen は (カード, 番号) の集合で、月をまたいで引き継ぐ"""
    games = []
    for mm, dd, body in ROW.findall(page):
        t1 = re.search(r'class="team1">([^<]*)<', body)
        t2 = re.search(r'class="team2">([^<]*)<', body)
        s1 = re.search(r'class="score1">(\d+)<', body)
        s2 = re.search(r'class="score2">(\d+)<', body)
        link = re.search(r'href="/scores/\d+/\d+/([a-z]+)-([a-z]+)-(\d+)/"', body)
        if not (t1 and t2 and s1 and s2 and link) or 'class="cancel"' in body:
            continue
        key = (frozenset((link.group(1), link.group(2))), int(link.group(3)))
        if key in seen:
            continue        # 同じカードの同じ番号が既にある → ポストシーズン
        seen.add(key)
        home, away = t1.group(1).strip(), t2.group(1).strip()
        if home not in CENTRAL | PACIFIC or away not in CENTRAL | PACIFIC:
            continue
        games.append([f"{year}-{mm}-{dd}", home, away, int(s1.group(1)), int(s2.group(1))])
    return games


def parse_old(page, year):
    """過去の年の月別カレンダー → {試合ID: 試合}"""
    games = {}
    pat = rf'<a href="/bis/{year}/games/s(\d{{4}})(\d{{2}})(\d{{2}})(\d+)\.html">([^<]+)</a>'
    for y, mm, dd, gid, text in re.findall(pat, page):
        m = re.fullmatch(r"\s*(\S+)\s+(\d+)\s*-\s*(\d+)\s+(\S+)\s*", text)
        if not m or m.group(1) not in ABBR or m.group(4) not in ABBR:
            continue        # 中止（*）・オールスター（セ・パ）
        games[y + mm + dd + gid] = [f"{y}-{mm}-{dd}", ABBR[m.group(1)], ABBR[m.group(4)],
                                    int(m.group(2)), int(m.group(3))]
    return games


def within_season(games, quota):
    """日付の順に数えて、どちらかの球団が公式戦の試合数を終えたあとの試合（ポストシーズン）を除く"""
    played = Counter()
    out = []
    for g in games:
        home, away = g[1], g[2]
        if played[home] >= quota.get(home, 10 ** 9) or played[away] >= quota.get(away, 10 ** 9):
            continue
        played[home] += 1
        played[away] += 1
        out.append(g)
    return out


def fetch_year(year, current, quota=None):
    if current:
        games, seen = [], set()
        for m in CUR_MONTHS:
            page = get(CUR_URL.format(year=year, m=m))
            if page:
                games += parse_current(page, year, seen)
            time.sleep(1)
    else:
        found = {}
        for m in OLD_MONTHS:
            page = get(OLD_URL.format(year=year, m=m))
            if page:
                found.update(parse_old(page, year))
            time.sleep(1)
        games = list(found.values())
    games.sort(key=lambda g: g[0])      # 同じ日の試合はページの並びのまま（安定ソート）
    if not current and quota:
        # 過去の年のカレンダーには、クライマックスシリーズ・日本シリーズも載っている
        games = within_season(games, quota)
    return games


# ---------------------------------------------------------------- 照らし合わせ

def records(games):
    rec = defaultdict(lambda: [0, 0, 0])
    for _, home, away, hs, as_ in games:
        if hs > as_:
            rec[home][0] += 1
            rec[away][1] += 1
        elif hs < as_:
            rec[home][1] += 1
            rec[away][0] += 1
        else:
            rec[home][2] += 1
            rec[away][2] += 1
    return {t: tuple(r) for t, r in rec.items()}


def expected_records(season):
    """season_<年>.json の投手の勝敗の合計と試合数から、球団ごとの (勝, 敗, 分)"""
    pc = {c: i for i, c in enumerate(season["pit_cols"])}
    w, l = Counter(), Counter()
    for r in season["pit"]:
        w[r[pc["team"]]] += r[pc["勝利"]]
        l[r[pc["team"]]] += r[pc["敗北"]]
    out = {}
    for code, info in season["teams"].items():
        out[info["name"]] = (w[code], l[code], info["games"] - w[code] - l[code])
    return out


def mismatches(games, expected):
    got = records(games)
    return {t: (got.get(t), e) for t, e in expected.items() if got.get(t) != e}


# ---------------------------------------------------------------- 保存

def update(data_dir, current_year, fetch_ok=True, log=print):
    """足りない年・今季を取りにいき、npb/data/games_<年>.json を書く。年 → 試合の一覧 を返す"""
    data_dir = Path(data_dir)
    out = {}
    for year in range(FIRST_YEAR, current_year + 1):
        path = data_dir / f"games_{year}.json"
        season_path = data_dir / f"season_{year}.json"
        season = json.loads(season_path.read_text(encoding="utf-8")) if season_path.exists() else None
        final = bool(season and season.get("final"))
        saved = json.loads(path.read_text(encoding="utf-8")) if path.exists() else None
        if saved and saved.get("final"):
            out[year] = saved["games"]
            continue
        if not fetch_ok:
            if saved:
                out[year] = saved["games"]
            continue
        quota = {info["name"]: info["games"] for info in season["teams"].values()} if season else None
        games = fetch_year(year, current=(year == current_year), quota=quota)
        if not games:
            log(f"games {year}: 試合が見つからない")
            continue
        if season:
            bad = mismatches(games, expected_records(season))
            if bad and final:
                log(f"games {year}: 勝敗が合わないので保存しない {bad}")
                if saved:
                    out[year] = saved["games"]
                continue
            if bad:
                log(f"games {year}: 途中のため勝敗の差あり（成績の更新待ち） {bad}")
        path.write_text(json.dumps({"year": year, "final": final, "games": games}, ensure_ascii=False,
                                   separators=(",", ":")), encoding="utf-8")
        log(f"games {year}: {len(games)}試合{'（シーズン終了）' if final else ''}")
        out[year] = games
    return out


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--year", type=int, required=True, help="今季")
    a = ap.parse_args()
    update(a.data, a.year)
