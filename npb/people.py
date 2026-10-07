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


# 苗字の1文字目を比べるときに同じとみなす字（名簿と成績で表記が揺れる）
SAME_FIRST = [set("斉斎齊齋"), set("辺邊邉"), set("沢澤"), set("浜濱濵"), set("高髙"), set("崎﨑")]


def same_first(a, b):
    return a == b or any(a in g and b in g for g in SAME_FIRST)


def given_name(name):
    """「加藤　拓也」→「拓也」（姓と名の間に空白がある名前だけ）"""
    parts = [x for x in re.split(r"[\s\u3000]+", name.strip()) if x]
    return key(parts[1]) if len(parts) == 2 else None


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
        # 「拓也|2026|ヤクルト」のように年と球団を付けると、その年・その球団の行だけに使う
        # （「拓也」は2016年のソフトバンクでは甲斐拓也の登録名だった）
        # 名簿の名前の代わりに「#選手ID」を書くと、同姓同名がいてもその人に決める
        def target(v):
            return v if v.startswith("#") else key(v)
        self.manual = {key(k): target(v) for k, v in manual.items() if not k.startswith("_") and "|" not in k}
        self.manual_at = {}
        for k, v in manual.items():
            if "|" in k:
                n, y, t = k.split("|")
                self.manual_at[(key(n), int(y), t)] = target(v)
        for i, p in enumerate(self.players):
            p["pid"] = p["id"] or f"r{i}"
            # 「（読み方）かく・しゅんりん」のような、読み方だけの変更は名前として扱わない
            # 「（読み方）～17かく・しゅんりん」のように年が付いたものもある
            p["alias"] = [a for a in p["alias"] if "読み方" not in a and not re.fullmatch(r"[ぁ-んー・（）()]+", a)]
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
        # 名簿の最後の年の秋のドラフトで指名された新人の名前（今シーズンの結びつけで、同姓同名の昔の選手と取り違えないため）
        draft = Path(register_path).with_name(f"draft_{self.max_year}.json")
        self.rookie_keys = {key(x["name"]) for x in json.loads(draft.read_text(encoding="utf-8"))["picks"]} \
            if draft.exists() else set()
        self.seen_names = defaultdict(list)     # pid → 成績に出てきた登録名
        self.hint = defaultdict(set)            # (球団, 登録名) → 別の年に結びついた pid
        self._load_rosters(Path(register_path).parent)

    def _load_rosters(self, data_dir):
        """球団の選手一覧（npb/data/roster_<年度>.json）を読む。
        - 名簿にまだ載っていない年度の (登録名, 球団) → 選手ID を、その年の結びつけに最初に使う
          （新外国人・新人・シーズン途中の加入。名簿に無いので、ほかの手がかりでは結べない）
        - 名簿に無い人は、選手一覧の名前で「人」を足す（在籍はその年度の球団だけ）
        - 最新の年度の一覧に今いる人（退団・移籍していない人）を self.current に入れる：{pid: (球団, 育成か)}"""
        self.on_roster = {}                     # (年度, 登録名キー, 球団) → pid
        self.current, self.current_year = {}, None
        files = sorted(data_dir.glob("roster_*.json"))
        for f in files:
            ro = json.loads(f.read_text(encoding="utf-8"))
            y = ro["year"]
            if y <= self.max_year:
                continue                        # 名簿に載った年度は名簿で足りる
            for x in ro["players"]:
                pid = x["id"]
                self.on_roster[(y, key(x["name"]), x["team"])] = pid
                if pid not in self.by_pid:
                    p = {"id": pid, "pid": pid, "name": x["name"], "alias": [],
                         "spans": [], "keys": {key(x["name"])}, "from_roster": True}
                    self.players.append(p)
                    self.by_pid[pid] = p
                    self.by_key[key(x["name"])].append(p)
                p = self.by_pid[pid]
                if p.get("from_roster"):
                    span = [y, x["team"], "育" if x["ikusei"] else ""]
                    if span not in p["spans"]:
                        p["spans"].append(span)
        if files:
            ro = json.loads(files[-1].read_text(encoding="utf-8"))
            self.current_year = ro["year"]
            self.current = {x["id"]: (x["team"], x["ikusei"]) for x in ro["players"] if not x["left"]}

    def _in(self, p, year, teams, ikusei=False):
        year = min(year, self.max_year)
        return any(y == year and t in teams and (is_player(k) or (ikusei and k == "育"))
                   for y, t, k in p["spans"])

    def _active(self, p, year, ikusei=False):
        """その年（名簿にまだ無い年は名簿の最後の年）に、どこかの球団に選手として在籍していたか"""
        year = min(year, self.max_year)
        return any(y == year and (is_player(k) or (ikusei and k == "育")) for y, _, k in p["spans"])

    @staticmethod
    def _base(k):
        """外国人選手の頭文字を外す（'Aラミレス' → 'ラミレス'）"""
        return re.sub(r"^[A-Za-z]{1,2}(?=[^A-Za-z])", "", k)

    def _score(self, name_key, p, raw=None):
        # 登録名が名前（下の名前）か苗字だけ：颯（中川 颯）、康介（加藤 康介）
        parts = [key(x) for x in re.split(r"[\s\u3000]+", p["name"]) if x]
        if len(parts) == 2 and name_key in parts:
            return 1.9
        best = 0.0
        # 下の名前が同じ：改姓（加藤 拓也 → 矢崎 拓也）
        if raw and given_name(raw) and given_name(raw) == given_name(p["name"]):
            best = 1.2
        for pk in p["keys"]:
            for other in (pk, self._base(pk)):
                if name_key == other:
                    return 2.0
                if name_key and other and (name_key in other or other in name_key):
                    ratio = difflib.SequenceMatcher(None, name_key, other).ratio()
                    best = max(best, 1.5 + ratio / 10)
                elif name_key and other and same_first(name_key[0], other[0]):
                    # 似ているだけのときは、苗字の1文字目が同じものに限る
                    # （重信慎之介 と 小笠原慎之介 のような、下の名前だけ同じ別人を避ける）
                    best = max(best, difflib.SequenceMatcher(None, name_key, other).ratio())
        return best

    def link_season(self, year, rows):
        """rows: [(登録名, 球団名)] → {(登録名, 球団名): pid}

        登録名は球団の中では重ならないが、別の球団には同じ登録名の別人がいる
        （2020年「エスコバー」＝DeNAの投手と、ヤクルトの内野手）ので、球団ごとに結びつける"""
        out = {}
        pending = []
        for name, team in rows:
            k = key(name)
            # 球団の選手一覧に、その年度・その球団・その登録名の人がいれば、その人（選手IDつきの公式の一覧）
            if (year, k, team) in self.on_roster:
                out[(name, team)] = self.on_roster[(year, k, team)]
                continue
            to = self.manual_at.get((k, year, team)) or self.manual.get(k, k)
            if to.startswith("#") and to[1:] in self.by_pid:
                out[(name, team)] = to[1:]
                continue
            ps = self.by_key.get(to, [])
            cands = [p for p in ps if self._in(p, year, {team})] or \
                    [p for p in ps if self._in(p, year, {team}, ikusei=True)]
            if not cands and year > self.max_year:
                # 今シーズン：オフに移籍した選手は、前年にどこかで在籍（育成を含む）していれば同じ人
                cands = [p for p in ps if self._active(p, year)] or \
                        [p for p in ps if self._active(p, year, ikusei=True)]
            if len(cands) == 1:
                out[(name, team)] = cands[0]["pid"]
            else:
                pending.append((name, team))

        # 名簿にまだ載っていない今シーズンは、前年の在籍で代用しているだけで、
        # 今年入った選手（新人・新外国人）と取り違えやすいので、似た名前での照らし合わせはしない。
        # 前のシーズンまでの結びつきを手がかりに、はっきり決まるものだけ結ぶ
        if year > self.max_year:
            self._link_current(pending, out)
            pending = []

        # 同じ年・同じ球団で、まだ誰とも結びついていない人と照らし合わせる
        used = set(out.values())
        names_by_team = defaultdict(list)
        for name, team in pending:
            names_by_team[team].append(name)
        for team, names in names_by_team.items():
            left = {p["pid"]: p for p, kind in self.roster.get((year, team), [])
                    if is_player(kind) and p["pid"] not in used}
            pairs = []
            for n in names:
                scored = sorted(((self._score(key(n), p, n), pid) for pid, p in left.items()), reverse=True)
                scored = [x for x in scored if x[0] >= 0.5]
                if len(scored) > 1 and scored[0][0] == scored[1][0]:
                    # 同じくらい似た人が2人いる（阪神の「俊介」＝藤川俊介・石川俊介）。
                    # 別の年に同じ球団・同じ登録名で結びついた人がその中にいれば、その人
                    tied = {pid for sc, pid in scored if sc == scored[0][0]}
                    h = self.hint.get((team, key(n)), set()) & tied
                    if len(h) == 1:
                        pairs.append((scored[0][0], n, h.pop()))
                    continue
                pairs += [(sc, n, pid) for sc, pid in scored]
            # 似ている組から順に確定させる
            for sc, n, pid in sorted(pairs, key=lambda x: -x[0]):
                if (n, team) in out or pid in used:
                    continue
                out[(n, team)] = pid
                used.add(pid)
            rest_n = [n for n in names if (n, team) not in out]
            rest_p = [pid for pid in left if pid not in used]
            if len(rest_n) == 1 and len(rest_p) == 1:
                out[(rest_n[0], team)] = rest_p[0]
                used.add(rest_p[0])

        # それでも残った名前は、シーズン途中に移籍して球団ごとに登録名が違う選手かもしれない
        # （2020年 広島「ＤＪ．ジョンソン」→ 楽天「ジョンソン」）。別の球団の行ですでに
        # 結びついた人も候補に戻すが、同じ球団ではまだ使われていない人で、名前がはっきり一致するときだけ
        used_by_team = defaultdict(set)
        for (name, team), pid in out.items():
            used_by_team[team].add(pid)
        for team, names in names_by_team.items():
            for n in names:
                if (n, team) in out:
                    continue
                cands = {p["pid"] for p, kind in self.roster.get((year, team), [])
                         if is_player(kind) and p["pid"] not in used_by_team[team]
                         and self._score(key(n), p, n) >= 1.5}
                if len(cands) == 1:
                    pid = cands.pop()
                    out[(n, team)] = pid
                    used_by_team[team].add(pid)

        for (name, team), pid in out.items():
            if key(name) not in {key(n) for n in self.seen_names[pid]}:
                self.seen_names[pid].append(name)
            self.hint[(team, key(name))].add(pid)
        return out

    def _link_current(self, pending, out):
        """今シーズン（名簿にまだ無い年）の、名前が完全一致しなかった行を結ぶ。

        1. 前のシーズンに同じ球団・同じ登録名で結びつき、名簿の最後の年もその球団にいた人
           （大勢、愛斗、マルティネス）。または名簿の最後の年にその球団にいた、同じ名前の人
           （育成から支配下に上がった巨人のティマ）
        2. 名簿の最後の年に別の球団で同じ登録名だった人（オフに移籍：阪神→DeNAのデュプランティエ）。
           ただし名簿にその名前（外国人選手は頭文字を除いた名前）の人が1人しかいないときだけ。
           ガルシア・ロドリゲスのような多い名前は、新しく来た別人のことがある
           （2026年 阪神のガルシアは、2025年 西武のＡ．ガルシアとは別人）
        3. フルネームが名簿でただ1人の人（メジャー帰りの前田健太・小笠原慎之介）。
           ただし直前のドラフトで同じ名前の新人が指名されていれば決めない
        どれも候補がちょうど1人のときだけ。同じ人を2つの行に結ばない"""
        used = set(out.values())
        last = self.max_year
        same_name = defaultdict(set)    # 名前（頭文字を除く）→ 名簿や成績でその名前を使った人
        for p in self.players:
            for x in p["keys"]:
                same_name[self._base(x)].add(p["pid"])
        for (team, k), pids in self.hint.items():  # 成績の登録名（日隈モンテル → 「モンテル」）
            same_name[k] |= pids

        def on_team(pid, team):
            return any(y == last and t == team and (is_player(k) or k == "育")
                       for y, t, k in self.by_pid[pid]["spans"])

        def take(row, cands):
            cands = {pid for pid in cands if pid not in used}
            if len(cands) == 1:
                out[row] = cands.pop()
                used.add(out[row])
                return True
            return False

        last_names = defaultdict(set)   # 名簿の最後の年にその登録名で結びついた人
        for (team, k), pids in self.hint.items():
            for pid in pids:
                if on_team(pid, team):
                    last_names[k].add(pid)
        rest = []
        for name, team in pending:
            k = key(name)
            if take((name, team), {pid for pid in self.hint.get((team, k), set()) if on_team(pid, team)}):
                continue
            # 名簿の最後の年に同じ球団にいた、同じ名前（頭文字を除く）の人。
            # 育成から支配下に上がった選手は、それまで一軍の成績が無いので上の手がかりが無い（巨人のティマ）
            if take((name, team), {p["pid"] for p, kind in self.roster.get((last, team), [])
                                   if (is_player(kind) or kind == "育")
                                   and k in {self._base(x) for x in p["keys"]} | p["keys"]}):
                continue
            rest.append((name, team))
        for name, team in rest:
            k = key(name)
            if len(same_name.get(k, ())) == 1 and take((name, team), last_names.get(k, set())):
                continue
            ps = self.by_key.get(k, [])
            if re.search(r"[\s\u3000]", name.strip()) and len(ps) == 1 and k not in self.rookie_keys:
                take((name, team), {ps[0]["pid"]})

    def link_all(self, rows_by_year):
        """全シーズンをまとめて結びつける → {年: {(登録名, 球団名): pid}}。
        1回目で決まった結びつきを手がかりに、2回目で同点だった名前を決める"""
        for y in sorted(rows_by_year):
            self.link_season(y, rows_by_year[y])
        self.seen_names = defaultdict(list)
        return {y: self.link_season(y, rows_by_year[y]) for y in sorted(rows_by_year)}

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
