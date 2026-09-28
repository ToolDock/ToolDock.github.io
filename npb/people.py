"""成績の「登録名」と、NPB在籍者名簿の「人」を結びつける。

成績は年ごとの登録名で載っているので、登録名を変えた選手（岡田貴弘→T-岡田、
新庄剛志→SHINJO、中川颯→颯、後藤武敏→後藤武敏G.→… など）は名前だけでは
同じ人だとわからない。また同姓同名の別人もいる。

在籍者名簿（npb/data/register.json）には、1人ずつ「在籍した年と球団」と
「改名の履歴」があるので、次の順で結びつける。

  1. 名前（本名・改名の履歴）が一致し、その年にその球団に支配下で在籍していた人
  2. 1で決まらなかった名前は、同じ年・同じ球団の中で残った人と照らし合わせる
     - 登録名が名簿の名前の一部になっている（颯 ⊂ 中川颯、セギノール ⊂ Ｆ．セギノール）
     - 名前が似ている（亀井義行 ↔ 亀井善行、李承ヨプ ↔ 李承燁）
     似ている組から順に確定させ、最後に1人と1人だけ残ればその2つを結ぶ（SHINJO ↔ 新庄剛志）
名簿の改名の履歴には、本名の変更は載っているが登録名だけの変更は載っていないことが多いので、
2の照らし合わせが必要になる。
"""

from __future__ import annotations

import difflib
import json
import re
import unicodedata
from collections import defaultdict
from pathlib import Path

ITAIJI = str.maketrans({"髙": "高", "﨑": "崎", "𠮷": "吉", "德": "徳", "瀨": "瀬", "邉": "辺", "邊": "辺",
                        "齋": "斎", "齊": "斉", "濵": "浜", "濱": "浜", "澤": "沢", "廣": "広", "國": "国",
                        "櫻": "桜", "眞": "真", "惠": "恵", "條": "条", "嶋": "島", "嶌": "島",
                        "會": "会", "攝": "摂", "靍": "鶴", "藏": "蔵", "龍": "竜", "穗": "穂", "峯": "峰"})

# 球団名の変更（同じ球団として扱う）
FRANCHISE = {"横浜": "DeNA"}


def franchise(team):
    return FRANCHISE.get(team, team)


def key(name):
    """照合用：全角半角・異体字をそろえ、空白と中黒・ピリオドを除く"""
    s = unicodedata.normalize("NFKC", name)
    return re.sub(r"[\s　・.．]", "", s).translate(ITAIJI)


def is_foreign_style(name):
    """「Ｆ．セギノール」のような、名前の頭文字つきの外国人選手の表記"""
    return bool(re.match(r"^[A-Za-zＡ-Ｚａ-ｚ][.．]", name.strip()))


def is_player(kind):
    """在籍の区分が選手（支配下）か。「兼監」（選手兼任監督）も選手として数える"""
    return kind == "" or kind.startswith("兼")


ALIASES = Path(__file__).resolve().parent / "aliases.json"


class People:
    def __init__(self, register_path, aliases_path=ALIASES):
        data = json.loads(Path(register_path).read_text(encoding="utf-8"))
        self.players = data["players"]
        # 名簿に改名の記録がない登録名（SHINJO など）を手で補う表：登録名 → 名簿の名前
        try:
            manual = json.loads(Path(aliases_path).read_text(encoding="utf-8"))
        except FileNotFoundError:
            manual = {}
        self.manual = {key(k): key(v) for k, v in manual.items() if not k.startswith("_")}
        for i, p in enumerate(self.players):
            p["pid"] = p["id"] or f"r{i}"
            # 「（読み方）かく・しゅんりん」のような、読み方だけの変更は名前として扱わない
            p["alias"] = [a for a in p["alias"] if not re.fullmatch(r"[ぁ-んー・（）()読み方]+", a)]
            p["keys"] = {key(p["name"])} | {key(a) for a in p["alias"]}
        self.by_key = defaultdict(list)
        for p in self.players:
            for k in p["keys"]:
                self.by_key[k].append(p)
        self.by_pid = {p["pid"]: p for p in self.players}
        # 名簿は前のシーズンまで（今シーズンの在籍はまだ載っていない）
        self.max_year = max(y for p in self.players for y, _, _ in p["spans"])
        # (年, 球団) → その年にその球団に在籍した人（区分つき）
        self.roster = defaultdict(list)
        for p in self.players:
            for y, team, kind in p["spans"]:
                self.roster[(y, team)].append((p, kind))
        self.seen_names = defaultdict(list)     # pid → 成績に出てきた登録名

    def _in(self, p, year, teams, ikusei=False):
        year = min(year, self.max_year)
        return any(y == year and t in teams and (is_player(k) or (ikusei and k == "育"))
                   for y, t, k in p["spans"])

    def _active(self, p, year):
        """その年（名簿にまだ無い年は名簿の最後の年）に、どこかの球団に選手として在籍していたか"""
        year = min(year, self.max_year)
        return any(y == year and is_player(k) for y, _, k in p["spans"])

    @staticmethod
    def _base(k):
        """外国人選手の頭文字を外す（'Aラミレス' → 'ラミレス'）"""
        return re.sub(r"^[A-Za-z]{1,2}(?=[^A-Za-z])", "", k)

    def _score(self, name_key, p):
        # 登録名が名前（下の名前）か苗字だけ：颯（中川 颯）、康介（加藤 康介）
        parts = [key(x) for x in re.split(r"[\s\u3000]+", p["name"]) if x]
        if len(parts) == 2 and name_key in parts:
            return 1.9
        best = 0.0
        for pk in p["keys"]:
            for other in (pk, self._base(pk)):
                if name_key == other:
                    return 2.0
                if name_key and other and (name_key in other or other in name_key):
                    ratio = difflib.SequenceMatcher(None, name_key, other).ratio()
                    best = max(best, 1.5 + ratio / 10)
                elif name_key and other and name_key[0] == other[0]:
                    # 似ているだけのときは、苗字の1文字目が同じものに限る
                    # （重信慎之介 と 小笠原慎之介 のような、下の名前だけ同じ別人を避ける）
                    best = max(best, difflib.SequenceMatcher(None, name_key, other).ratio())
        return best

    def link_season(self, year, rows):
        """rows: [(登録名, [球団名...])] → {登録名: pid}"""
        out = {}
        pending = []
        for name, teams in rows:
            k = key(name)
            ps = self.by_key.get(self.manual.get(k, k), [])
            cands = [p for p in ps if self._in(p, year, teams)] or \
                    [p for p in ps if self._in(p, year, teams, ikusei=True)]
            if not cands and year > self.max_year:
                # 今シーズン：オフに移籍した選手は、前年にどこかで在籍していれば同じ人
                cands = [p for p in ps if self._active(p, year)]
            if len(cands) == 1:
                out[name] = cands[0]["pid"]
            else:
                pending.append((name, teams))

        # 名簿にまだ載っていない今シーズンは、前年の在籍で代用しているだけで、
        # 今年入った選手（新人・新外国人・メジャー帰り）と取り違えやすいので、照らし合わせはしない
        if year > self.max_year:
            pending = []

        # 同じ年・同じ球団で、まだ誰とも結びついていない人と照らし合わせる
        used = set(out.values())
        names_by_team = defaultdict(list)
        for name, teams in pending:
            for t in teams:
                names_by_team[t].append(name)
        for team, names in names_by_team.items():
            left = {p["pid"]: p for p, kind in self.roster.get((min(year, self.max_year), team), [])
                    if is_player(kind) and p["pid"] not in used}
            pairs = []
            for n in names:
                if n in out:
                    continue
                for pid, p in left.items():
                    sc = self._score(key(n), p)
                    if sc >= 0.5:
                        pairs.append((sc, n, pid))
            # 似ている組から順に確定させる
            for sc, n, pid in sorted(pairs, key=lambda x: -x[0]):
                if n in out or pid in used:
                    continue
                out[n] = pid
                used.add(pid)
            rest_n = [n for n in names if n not in out]
            rest_p = [pid for pid in left if pid not in used]
            if len(rest_n) == 1 and len(rest_p) == 1:
                out[rest_n[0]] = rest_p[0]
                used.add(rest_p[0])

        for name, pid in out.items():
            if key(name) not in {key(n) for n in self.seen_names[pid]}:
                self.seen_names[pid].append(name)
        return out

    def display(self, pid, fallback=None):
        """「岡田 貴弘（T-岡田）」のように、名簿の名前に、成績で使われた別の登録名を添える"""
        p = self.by_pid.get(pid)
        if not p:
            return fallback
        head = p["name"]
        others = []
        for n in list(p["alias"]) + self.seen_names.get(pid, []):
            if key(n) == key(head) or any(key(n) == key(o) for o in others):
                continue
            # 外国人選手の「Ｆ．セギノール」と「セギノール」のような表記の違いは添えない
            if is_foreign_style(head) and key(n) in key(head):
                continue
            others.append(n)
        return head + (f"（{'／'.join(others)}）" if others else "")

    def registered_name(self, pid, stats_name):
        """成績の行に出す名前。名簿の名前と登録名が違えば「本名（登録名）」"""
        p = self.by_pid.get(pid)
        if not p or key(p["name"]) == key(stats_name):
            return stats_name
        if is_foreign_style(p["name"]) and key(stats_name) in key(p["name"]):
            return stats_name
        return f"{p['name']}（{stats_name}）"
