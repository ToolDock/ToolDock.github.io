"""NPB の勝敗表から、優勝マジック・クリンチナンバー・自力/他力を計算する。

考え方
------
「チーム A が残り試合で m 勝すれば、他の結果がどうなっても k 位以内が確定する」
ような最小の m を求める。k=1 が優勝マジック、k=3 がCS進出のクリンチナンバー。

判定は「A が m 勝（残りは全敗）したとき、A 以外の k チームが同時に
A の勝率以上になれる組み合わせが存在するか」を、最大流で調べる。
存在しなければ確定。1チームずつの最悪ケースを見るだけだと
3チームが同時に上回れるかを判定できないので、組ごとに流量で確かめている。

前提
----
- 残り試合に引き分けは起きないものとして計算する。
- 勝率が並んだ場合の順位決定方法
    セ：勝利数 → 当該球団間の対戦勝率 → リーグ内の勝率 → 前年順位
    パ：当該球団間の対戦勝率 → リーグ内の勝率 → 前年順位
  のうち、セの「勝利数」だけを反映する（wins_tiebreak=True）。
  勝率も勝利数も並ぶ場合と、パの同率は、上回られる可能性がある（安全側）として扱う。
  直接対決の勝率は残り試合の結果で変わり、3チーム以上が並ぶと当該球団間の
  合算になるため、確定を誤って早く出さないよう判定には使わない。
"""

from __future__ import annotations

from collections import deque
from fractions import Fraction
from itertools import combinations


class Team:
    def __init__(self, name, short, w, l, t):
        self.name = name        # 阪神タイガース
        self.short = short      # 阪神
        self.w, self.l, self.t = w, l, t
        self.rem = {}           # 相手（short）→ 残り試合数
        self.rem_out = 0        # 交流戦の残り

    @property
    def games(self):
        return self.w + self.l + self.t

    @property
    def rem_total(self):
        return sum(self.rem.values()) + self.rem_out

    @property
    def pct(self):
        d = self.w + self.l
        return Fraction(self.w, d) if d else Fraction(0)


# ---- 最大流（Edmonds-Karp）。ノードは数十個なのでこれで十分 ----

class Flow:
    def __init__(self):
        self.g = {}

    def add(self, u, v, c):
        if c <= 0:
            return
        self.g.setdefault(u, {}).setdefault(v, 0)
        self.g.setdefault(v, {}).setdefault(u, 0)
        self.g[u][v] += c

    def max_flow(self, s, t):
        total = 0
        while True:
            prev = {s: None}
            q = deque([s])
            while q and t not in prev:
                u = q.popleft()
                for v, c in self.g.get(u, {}).items():
                    if c > 0 and v not in prev:
                        prev[v] = u
                        q.append(v)
            if t not in prev:
                return total
            f, v = float("inf"), t
            while prev[v] is not None:
                f = min(f, self.g[prev[v]][v])
                v = prev[v]
            v = t
            while prev[v] is not None:
                u = prev[v]
                self.g[u][v] -= f
                self.g[v][u] += f
                v = u
            total += f


def _ceil_div(a, b):
    return -(-a // b)


def _can_all_reach(teams, a, group, m, wins_tiebreak=False):
    """A が残り m 勝・残りは全敗のとき、group の全チームが同時に
    A の最終勝率「以上」になれる結果が存在するか。"""
    A = teams[a]
    dA = A.w + A.l + A.rem_total
    wA = A.w + m

    # A の勝ちは、group 以外との試合にできるだけ回す（group に最も不利な置き方）
    vs_group = sum(A.rem.get(x, 0) for x in group)
    non_group = A.rem_total - vs_group
    a_wins_vs_group = max(0, m - non_group)
    pool = vs_group - a_wins_vs_group     # group 側が A から取れる勝ち数の合計

    need = {}
    for x in group:
        X = teams[x]
        dX = X.w + X.l + X.rem_total
        # w / dX >= wA / dA を満たす最小の w
        req = _ceil_div(wA * dX, dA) if dA else 0
        # 勝率が並んでも、勝利数が少なければ下位（セ）。並ぶのが dX < dA のときだけ
        if wins_tiebreak and dA and (wA * dX) % dA == 0 and dX < dA:
            req += 1
        base = X.w + X.rem_out + sum(
            c for y, c in X.rem.items() if y != a and y not in group)
        need[x] = max(0, req - base)

    if sum(need.values()) == 0:
        return True

    fl = Flow()
    fl.add("S", "pool", pool)
    for x in group:
        fl.add("pool", x, teams[x].rem.get(a, 0))
        fl.add(x, "T", need[x])
    for x, y in combinations(group, 2):
        c = teams[x].rem.get(y, 0)
        if c:
            node = ("pair", x, y)
            fl.add("S", node, c)
            fl.add(node, x, c)
            fl.add(node, y, c)
    return fl.max_flow("S", "T") == sum(need.values())


def clinched_with(teams, a, k, m, wins_tiebreak=False):
    """A が残り m 勝で k 位以内が確定するか。"""
    others = [x for x in teams if x != a]
    return not any(_can_all_reach(teams, a, g, m, wins_tiebreak)
                   for g in combinations(others, k))


def clinch_number(teams, a, k, wins_tiebreak=False):
    """k 位以内を自力で確定させるのに必要な勝利数。無理なら None。"""
    for m in range(teams[a].rem_total + 1):
        if clinched_with(teams, a, k, m, wins_tiebreak):
            return m
    return None


def _can_finish_within(teams, b, k, wins_tiebreak=False):
    """B が k 位以内に入る結果がひとつでもあるか（同率は入れる扱い）。"""
    B = teams[b]
    dB = B.w + B.l + B.rem_total
    wB = B.w + B.rem_total             # B は全勝するのが最善
    others = [x for x in teams if x != b]

    for free in combinations(others, k - 1):
        bounded = [x for x in others if x not in free]
        cap = {}
        ok = True
        for x in bounded:
            X = teams[x]
            dX = X.w + X.l + X.rem_total
            # w / dX <= wB / dB を満たす最大の w
            limit = (wB * dX) // dB if dB else X.w
            # 勝率が並ぶと勝利数が B より多くなる（セでは B が下位）ときは、並ぶのも不可
            if wins_tiebreak and dB and (wB * dX) % dB == 0 and dX > dB:
                limit -= 1
            # B 戦・交流戦は落とし、free との試合も落とす。自分たち同士の試合だけ流す
            cap[x] = limit - X.w
            if cap[x] < 0:
                ok = False
                break
        if not ok:
            continue
        fl = Flow()
        total = 0
        for x, y in combinations(bounded, 2):
            c = teams[x].rem.get(y, 0)
            if c:
                node = ("pair", x, y)
                fl.add("S", node, c)
                fl.add(node, x, c)
                fl.add(node, y, c)
                total += c
        for x in bounded:
            fl.add(x, "T", cap[x])
        if fl.max_flow("S", "T") == total:
            return True
    return False


def analyze(teams, cs_slots=3, wins_tiebreak=False):
    """teams: short → Team（順位順）。各チームの状態を返す。
    wins_tiebreak: 勝率が並んだとき勝利数の多いほうを上位にする（セ・リーグ）"""
    tb = wins_tiebreak
    res = {}
    for a in teams:
        res[a] = {
            "v_num": clinch_number(teams, a, 1, tb),
            "cs_num": clinch_number(teams, a, cs_slots, tb),
            "v_possible": _can_finish_within(teams, a, 1, tb),
            "cs_possible": _can_finish_within(teams, a, cs_slots, tb),
        }

    # マジックの点灯は「自力優勝の可能性を持つのが1チームだけ」になったとき
    own = [a for a in teams if res[a]["v_num"] is not None]
    lit = own[0] if len(own) == 1 else None

    # マジック対象チーム：A が magic-1 勝で止まったとき、単独で A 以上になれる相手
    for a in teams:
        r = res[a]
        r["magic_lit"] = (a == lit)
        r["v_clinched"] = r["v_num"] == 0
        r["cs_clinched"] = r["cs_num"] == 0
        r["target"] = None
        if r["magic_lit"] and r["v_num"]:
            m = r["v_num"] - 1
            for x in teams:
                if x != a and _can_all_reach(teams, a, (x,), m, tb):
                    r["target"] = x
                    break
    return res
