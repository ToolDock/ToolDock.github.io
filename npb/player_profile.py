"""NPB公式の選手ページ（/bis/players/<選手ID>.html）から、読み仮名・プロフィール・年度別成績を読む。

選手ページ（/player/）で使う。取った結果は npb/data/player_profiles.json に選手IDごとにためる。
  {"kana": "さかもと・はやと",
   "profile": {"ポジション": ..., "投打": ..., "身長／体重": ..., "生年月日": ..., "経歴": ..., "ドラフト": ...},
   "bat": [{"y": 2004, "teams": ["ヤクルト"], "g": ..., ...}],   # 2004年以前の年度別成績だけ
   "pit": [...]}

2005年以降の成績は npb/data/season_<年>.json から計算するので、ここでは2004年以前だけ持つ。
"""

from __future__ import annotations

import json
import re
import time
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

URL = "https://npb.jp/bis/players/{}.html"
FIRST_CALC_YEAR = 2005     # これより前の年度別成績だけ持つ
PROFILE_KEYS = ("ポジション", "投打", "身長／体重", "生年月日", "経歴", "ドラフト")

# 公式ページの球団名 → 短い名前（個人成績のページと同じ呼び方）
TEAMS = {"読売": "巨人", "阪神": "阪神", "中日": "中日", "広島東洋": "広島", "横浜": "横浜", "横浜DeNA": "DeNA",
         "ヤクルト": "ヤクルト", "東京ヤクルト": "ヤクルト", "福岡ダイエー": "ダイエー", "福岡ソフトバンク": "ソフトバンク",
         "西武": "西武", "埼玉西武": "西武", "日本ハム": "日本ハム", "北海道日本ハム": "日本ハム",
         "オリックス": "オリックス", "大阪近鉄": "近鉄", "近鉄": "近鉄", "ロッテ": "ロッテ", "千葉ロッテ": "ロッテ",
         "東北楽天": "楽天", "オリックス・ブルーウェーブ": "オリックス", "横浜大洋": "大洋", "大洋": "大洋",
         "阪急": "阪急", "南海": "南海", "日本ハム・ファイターズ": "日本ハム"}

BAT = {"試合": "g", "打席": "pa", "打数": "ab", "得点": "r", "安打": "h", "二塁打": "d2", "三塁打": "d3",
       "本塁打": "hr", "打点": "rbi", "盗塁": "sb", "盗塁刺": "cs", "犠打": "sh", "犠飛": "sf",
       "四球": "bb", "死球": "hbp", "三振": "so", "併殺打": "gdp"}
PIT = {"登板": "g", "勝利": "w", "敗北": "l", "セーブ": "sv", "H": "hld", "完投": "cg",
       "打者": "bf", "安打": "ha", "本塁打": "hr", "四球": "bb", "死球": "hbp", "三振": "so",
       "失点": "ra", "自責点": "er"}


class Tables(HTMLParser):
    """いちばん外側の表だけを行・セルに分ける。
    投球回の欄は中に表が入れ子になっている（178 と .1）ので、正規表現では表の終わりを取り違える"""

    def __init__(self):
        super().__init__()
        self.tables, self.depth, self.row, self.cell = [], 0, None, None
        self.kana = self.name = None
        self._li = None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "li" and a.get("id") in ("pc_v_kana", "pc_v_name"):
            self._li = [a["id"], ""]
        if tag == "table":
            self.depth += 1
            if self.depth == 1:
                self.tables.append([])
        elif self.depth == 1 and tag == "tr":
            self.row = []
        elif self.depth == 1 and tag in ("td", "th"):
            self.cell = ""

    def handle_endtag(self, tag):
        if tag == "li" and self._li:
            text = " ".join(self._li[1].split())
            if self._li[0] == "pc_v_kana":
                self.kana = text
            else:
                self.name = text
            self._li = None
        if tag == "table":
            self.depth -= 1
        elif self.depth == 1 and tag in ("td", "th") and self.cell is not None and self.row is not None:
            self.row.append(" ".join(self.cell.split()))
            self.cell = None
        elif self.depth == 1 and tag == "tr" and self.row is not None:
            if self.row:
                self.tables[-1].append(self.row)
            self.row = None

    def handle_data(self, data):
        if self._li is not None:
            self._li[1] += data
        if self.cell is not None:
            self.cell += data


def num(s):
    s = re.sub(r"[^\d]", "", s or "")
    return int(s) if s else 0


def outs_of(ip):
    """'178 .1' '178.1' '178' → アウト数"""
    m = re.match(r"^\s*(\d+)\s*(?:\.?\s*(\d))?", (ip or "").replace("+", ""))
    if not m:
        return 0
    return int(m.group(1)) * 3 + (int(m.group(2)) if m.group(2) else 0)


def team_name(s):
    s = re.sub(r"\s", "", s or "")
    return TEAMS.get(s, s)


def rows_of(table, kind):
    """年度別成績の表 → [{y, teams, ...}]。同じ年の複数の行（途中移籍）はまとめる"""
    head = [re.sub(r"\s", "", h) for h in table[0]]
    cols = BAT if kind == "bat" else PIT
    by_year = {}
    for r in table[1:]:
        if not r or not re.fullmatch(r"\d{4}", r[0]):
            continue
        cells = dict(zip(head, r))
        y = int(r[0])
        row = by_year.setdefault(y, {"y": y, "teams": [], **{k: 0 for k in cols.values()},
                                     **({"outs": 0} if kind == "pit" else {})})
        t = team_name(cells.get("所属球団"))
        if t and t not in row["teams"]:
            row["teams"].append(t)
        for h, k in cols.items():
            row[k] += num(cells.get(h))
        if kind == "pit":
            row["outs"] += outs_of(cells.get("投球回"))
    return [by_year[y] for y in sorted(by_year)]


def parse(page, before=FIRST_CALC_YEAR):
    p = Tables()
    p.feed(page)
    out = {"kana": p.kana or "", "profile": {}, "bat": [], "pit": []}
    for t in p.tables:
        if not t or not t[0]:
            continue
        if t[0][0] == "年度":
            head = [re.sub(r"\s", "", h) for h in t[0]]
            kind = "pit" if "登板" in head else "bat"
            out[kind] = [r for r in rows_of(t, kind) if r["y"] < before]
        else:
            for r in t:
                if len(r) == 2 and r[0] in PROFILE_KEYS:
                    out["profile"][r[0]] = r[1]
    return out


def fetch(pid, tries=3):
    req = urllib.request.Request(URL.format(pid), headers={"User-Agent": "Mozilla/5.0 (compatible; ToolDock NPB data)"})
    for i in range(tries):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return parse(r.read().decode("utf-8", "replace"))
        except Exception:
            time.sleep(3 * (i + 1))
    return None


def fill_missing(path: Path, pids, delay=0.5, limit=400):
    """player_profiles.json に無い選手の分だけ公式ページから取る（新人など）。取れた人数を返す"""
    data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    todo = [p for p in pids if p not in data][:limit]
    got = 0
    for pid in todo:
        d = fetch(pid)
        if d:
            data[pid] = d
            got += 1
        time.sleep(delay)
    if got:
        path.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":"), sort_keys=True) + "\n",
                        encoding="utf-8")
    return got
