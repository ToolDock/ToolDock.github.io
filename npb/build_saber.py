#!/usr/bin/env python3
"""保存済みの個人成績から、選手ごとのセイバー指標を計算して /saber/ を作る。

    python3 npb/build_saber.py --data npb/data --league war/league.json --out saber

計算式は /war/ の計算ツールと同じ（DELTAの枠組み）。守備（UZR）と
盗塁以外の走塁（UBR）、球場補正は公開データでは出せないので入れない「簡易WAR」。

- 守備位置補正は個人守備成績の試合数から。外野手は左・中・右の区別がないので、3つの平均
- 指名打者の試合数は「打席 ÷ 4.2 − 守備に就いた試合」で推定する（代打の出場と区別できないため）
- 投手の先発・救援は、1登板あたりの投球回が3回以上なら先発として扱う
- シーズン途中の移籍は、名前でまとめて1人として数える
"""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_magic import JST  # noqa: E402
from people import People  # noqa: E402

HERE = Path(__file__).resolve().parent
TEMPLATE = HERE / "template_saber.html"

WOBA_SCALE = 1.24
POS_ADJ = {"捕手": 18.1, "一塁手": -14.1, "二塁手": 3.4, "三塁手": -4.8, "遊撃手": 10.3,
           "外野手": (-12.0 + 4.2 - 5.0) / 3, "指名打者": -15.1}
POS_SHORT = {"捕手": "捕", "一塁手": "一", "二塁手": "二", "三塁手": "三", "遊撃手": "遊",
             "外野手": "外", "指名打者": "指", "代打": "代"}
PA_PER_GAME = 4.2
SP_IP_PER_GAME = 3.0


def r(x, d):
    return None if x is None else round(x, d)


def div(a, b):
    return a / b if b else None


def season_rows(st):
    """その年の成績に出てくる (登録名, 球団名) の一覧（名簿との結びつけ用）"""
    bc = {c: i for i, c in enumerate(st["bat_cols"])}
    pc = {c: i for i, c in enumerate(st["pit_cols"])}
    rows = {(r[bc["name"]], st["teams"][r[bc["team"]]]["name"]) for r in st["bat"]}
    rows |= {(r[pc["name"]], st["teams"][r[pc["team"]]]["name"]) for r in st["pit"]}
    return sorted(rows)


def compute_season(st, lg_consts, links=None, include_zero=False):
    """season_<年>.json → (打者のリスト, 投手のリスト)。各要素は dict。
    lg_consts: {"central": {...}, "pacific": {...}}（league.json のその年の値）
    links: {(登録名, 球団名): pid}（People.link_all のその年の分）。
      あれば、同じ人と確定した行だけを1人にまとめる（途中移籍・移籍で登録名が変わった選手）。
      別の球団の同じ登録名は別人のことがあるので、結びつかなかった行は球団ごとに分ける。
      なければ登録名でまとめる。
    include_zero: 打席0の野手（代走・守備固めだけ）・アウト0の投手も、数の成績だけの行として入れる
      （選手ページ・記録カウントダウンの通算用。率やWARは None / 0）"""
    bc = {c: i for i, c in enumerate(st["bat_cols"])}
    pc = {c: i for i, c in enumerate(st["pit_cols"])}
    teams = st["teams"]

    def ident(name, code):
        if links is None:
            return ("n", name)
        pid = links.get((name, teams[code]["name"]))
        return ("p", pid) if pid else ("t", name, code)

    # --- 守備：人ごと・位置ごとの試合数
    fld = {}
    for code, name, pos, g in st["fld"]:
        f = fld.setdefault(ident(name, code), {})
        f[pos] = f.get(pos, 0) + g

    # --- 打者：人ごとにまとめる（途中移籍）
    bat = {}
    for row in st["bat"]:
        name = row[bc["name"]]
        code = row[bc["team"]]
        b = bat.setdefault(ident(name, code), {"teams": [], "hand": row[bc["hand"]], "pa_by_team": {},
                                               "name_by_team": {}})
        b["name_by_team"][code] = name
        if code not in b["teams"]:
            b["teams"].append(code)
        b["pa_by_team"][code] = b["pa_by_team"].get(code, 0) + row[bc["打席"]]
        for k in st["bat_cols"][3:]:
            b[k] = b.get(k, 0) + row[bc[k]]

    batters = []
    for idt, b in bat.items():
        pa = b["打席"]
        if pa <= 0:
            if include_zero and b["試合"] > 0:
                main_team = max(b["pa_by_team"], key=b["pa_by_team"].get)
                fg = fld.get(idt, {})
                batters.append({
                    "name": b["name_by_team"][main_team], "pid": idt[1] if idt[0] == "p" else None,
                    "teams": [teams[c]["name"] for c in b["teams"]], "lg": teams[main_team]["league"],
                    "pos": POS_SHORT[max(fg, key=fg.get)] if fg else POS_SHORT["代打"], "hand": b["hand"],
                    "g": b["試合"], "pa": 0, "ab": 0, "h": 0, "hr": 0, "rbi": b["打点"], "sb": b["盗塁"],
                    "bb": 0, "so": 0, "d2": 0, "d3": 0, "hbp": 0, "sf": 0,
                    "r": b["得点"], "sh": 0, "cs": b["盗塁刺"], "ibb": 0, "gdp": 0,
                    "avg": None, "obp": None, "slg": None, "ops": None, "woba": None, "wrcp": None,
                    "iso": None, "babip": None, "kp": None, "bbp": None,
                    "wraa": 0, "wsb": 0, "posr": 0, "repl": 0, "war": 0.0, "qual": False, "zero": True})
            continue
        main_team = max(b["pa_by_team"], key=b["pa_by_team"].get)
        name = b["name_by_team"][main_team]
        lg = teams[main_team]["league"]
        L = lg_consts[lg]
        games = teams[main_team].get("games") or 143
        ab, h, d2, d3, hr = b["打数"], b["安打"], b["二塁打"], b["三塁打"], b["本塁打"]
        bb, ibb, hbp, sf, so = b["四球"], b["故意四"], b["死球"], b["犠飛"], b["三振"]
        sb, cs = b["盗塁"], b["盗塁刺"]
        s1 = h - d2 - d3 - hr
        avg = div(h, ab)
        obp = div(h + bb + hbp, ab + bb + hbp + sf)
        slg = div(s1 + 2 * d2 + 3 * d3 + 4 * hr, ab)
        woba = div(0.7 * (bb - ibb + hbp) + 0.9 * s1 + 1.3 * d2 + 1.6 * d3 + 2.0 * hr,
                   ab + bb - ibb + hbp + sf)
        wraa = (woba - L["woba"]) / WOBA_SCALE * pa if woba is not None else 0
        wrcp = ((wraa / pa + L["r_pa"]) / L["r_pa"]) * 100 if L["r_pa"] else None
        wsb = sb * 0.2 + cs * L["run_cs"] - L["wsb_rate"] * (s1 + bb + hbp - ibb)

        fg = dict(fld.get(idt, {}))
        fielded = sum(fg.values())
        dh = max(0, round(pa / PA_PER_GAME - fielded))
        dh = min(dh, max(0, b["試合"] - fielded))
        if dh:
            fg["指名打者"] = dh
        pos_runs = sum(POS_ADJ[p] * g / games for p, g in fg.items())
        main_pos = max(fg, key=fg.get) if fg else "代打"
        repl = (L["woba"] - 0.88 * L["woba"]) / WOBA_SCALE * pa
        war = (wraa + wsb + pos_runs + repl) / L["rpw"]

        batters.append({
            "name": name, "pid": idt[1] if idt[0] == "p" else None,
            "teams": [teams[c]["name"] for c in b["teams"]], "lg": lg,
            "pos": POS_SHORT[main_pos], "hand": b["hand"],
            "g": b["試合"], "pa": pa, "ab": ab, "h": h, "hr": hr, "rbi": b["打点"], "sb": sb,
            "bb": bb, "so": so, "d2": d2, "d3": d3, "hbp": hbp, "sf": sf,
            # 選手ページで使う（ランキングのJSONには出さない）
            "r": b["得点"], "sh": b["犠打"], "cs": cs, "ibb": ibb, "gdp": b["併殺打"],
            "avg": r(avg, 3), "obp": r(obp, 3), "slg": r(slg, 3),
            "ops": r(obp + slg, 3) if obp is not None and slg is not None else None,
            "woba": r(woba, 3), "wrcp": round(wrcp) if wrcp is not None else None,
            "iso": r(slg - avg, 3) if slg is not None and avg is not None else None,
            "babip": r(div(h - hr, ab - so - hr + sf), 3),
            "kp": r(div(so, pa), 3), "bbp": r(div(bb, pa), 3),
            "wraa": r(wraa, 1), "wsb": r(wsb, 1), "posr": r(pos_runs, 1), "repl": r(repl, 1),
            "war": r(war, 1),
            "qual": pa >= games * 3.1,
        })

    # --- 投手
    pit = {}
    for row in st["pit"]:
        name = row[pc["name"]]
        code = row[pc["team"]]
        p = pit.setdefault(ident(name, code), {"teams": [], "hand": row[pc["hand"]], "outs_by_team": {},
                                               "name_by_team": {}})
        p["name_by_team"][code] = name
        if code not in p["teams"]:
            p["teams"].append(code)
        p["outs_by_team"][code] = p["outs_by_team"].get(code, 0) + row[pc["outs"]]
        for k in st["pit_cols"][3:]:
            p[k] = p.get(k, 0) + row[pc[k]]

    pitchers = []
    for idt, p in pit.items():
        outs = p["outs"]
        if outs <= 0:
            if include_zero and p["登板"] > 0:
                main_team = p["teams"][0]
                pitchers.append({
                    "name": p["name_by_team"][main_team], "pid": idt[1] if idt[0] == "p" else None,
                    "teams": [teams[c]["name"] for c in p["teams"]], "lg": teams[main_team]["league"],
                    "role": "救援", "hand": p["hand"],
                    "g": p["登板"], "w": p["勝利"], "l": p["敗北"], "sv": p["セーブ"], "hld": p["ホールド"],
                    "ip": 0, "outs": 0, "so": p["三振"], "bb": p["四球"], "hr": p["本塁打"], "er": p["自責点"],
                    "ha": p["安打"], "ra": p["失点"], "hbp": p["死球"], "cg": 0, "bf": p["打者"],
                    "era": None, "fip": None, "whip": None, "kp": None, "bbp": None, "kbb": None, "hr9": None,
                    "war": 0.0, "qual": False, "zero": True})
            continue
        main_team = max(p["outs_by_team"], key=p["outs_by_team"].get)
        name = p["name_by_team"][main_team]
        lg = teams[main_team]["league"]
        L = lg_consts[lg]
        games = teams[main_team].get("games") or 143
        ip = outs / 3
        hr, bb, ibb, hbp, so = p["本塁打"], p["四球"], p["故意四"], p["死球"], p["三振"]
        bf, er, g = p["打者"], p["自責点"], p["登板"]
        fip = (13 * hr + 3 * (bb - ibb + hbp) - 2 * so) / ip + L["fip_const"]
        fip_ra = fip * (L["ra9"] / L["era"])
        role = "先発" if g and ip / g >= SP_IP_PER_GAME else "救援"
        base = 0.30 if role == "先発" else -0.55
        rar = (1.19 * L["ra9"] + base - fip_ra) / 9 * ip
        pitchers.append({
            "name": name, "pid": idt[1] if idt[0] == "p" else None,
            "teams": [teams[c]["name"] for c in p["teams"]], "lg": lg,
            "role": role, "hand": p["hand"],
            "g": g, "w": p["勝利"], "l": p["敗北"], "sv": p["セーブ"], "hld": p["ホールド"],
            "ip": r(ip, 1), "outs": outs, "so": so, "bb": bb, "hr": hr, "er": er,
            # 選手ページで使う（ランキングのJSONには出さない）
            "ha": p["安打"], "ra": p["失点"], "hbp": hbp, "cg": p["完投"], "bf": bf,
            "era": r(9 * er / ip, 2), "fip": r(fip, 2),
            "whip": r((p["安打"] + bb) / ip, 2),
            "kp": r(div(so, bf), 3), "bbp": r(div(bb, bf), 3),
            "kbb": r(div(so - bb, bf), 3), "hr9": r(9 * hr / ip, 2),
            "war": r(rar / L["rpw"], 1),
            "qual": ip >= games,
        })
    return batters, pitchers


# ---------------------------------------------------------------- ページ

def fmt3(x):
    if x is None:
        return "―"
    s = f"{x:.3f}"
    return s[1:] if s.startswith("0") else s


def top_table(rows, cols, n=10):
    head = "".join(f'<th scope="col">{c[0]}</th>' for c in cols)
    body = []
    for i, row in enumerate(rows[:n], 1):
        cells = "".join(f"<td>{c[1](row)}</td>" for c in cols)
        body.append(f'<tr><td class="rk">{i}</td>{cells}</tr>')
    return (f'<div class="tbl-wrap"><table class="lead"><thead><tr><th scope="col">順位</th>{head}</tr></thead>'
            f'<tbody>{"".join(body)}</tbody></table></div>')


def name_cell(row):
    nm = html.escape(row["name"].replace(chr(0x3000), " "))
    if row.get("id"):
        nm = f'<a href="/player/{row["id"]}/">{nm}</a>'
    return (f'<span class="nm">{nm}</span>'
            f'<span class="tm">{html.escape("・".join(row["teams"]))}</span>')


def render(year, as_of, final, batters, pitchers, years):
    blocks, summary = [], []
    for key, label in (("central", "セ・リーグ"), ("pacific", "パ・リーグ")):
        bq = sorted([b for b in batters if b["lg"] == key and b["qual"]], key=lambda b: -b["wrcp"])
        pq = sorted([p for p in pitchers if p["lg"] == key and p["qual"]], key=lambda p: p["fip"])
        wa = sorted([b for b in batters if b["lg"] == key] + [p for p in pitchers if p["lg"] == key],
                    key=lambda x: -(x["war"] or 0))
        if bq:
            summary.append(f"{label}のwRC+トップは{bq[0]['name'].replace(chr(0x3000), '')}（{bq[0]['wrcp']}）")
        blocks.append(f"""
<section class="lg-block">
  <h3>{label}：簡易WAR トップ10（野手・投手）</h3>
  {top_table(wa, [("選手", name_cell), ("区分", lambda x: "投手" if "fip" in x else "野手"), ("簡易WAR", lambda x: f'<b>{x["war"]:.1f}</b>')])}
  <h3>{label}：wRC+ トップ10（規定打席以上）</h3>
  {top_table(bq, [("選手", name_cell), ("wRC+", lambda x: f'<b>{x["wrcp"]}</b>'), ("wOBA", lambda x: fmt3(x["woba"])), ("OPS", lambda x: fmt3(x["ops"]))])}
  <h3>{label}：FIP トップ10（規定投球回以上）</h3>
  {top_table(pq, [("選手", name_cell), ("FIP", lambda x: f'<b>{x["fip"]:.2f}</b>'), ("防御率", lambda x: f'{x["era"]:.2f}'), ("K−BB%", lambda x: f'{x["kbb"] * 100:.1f}%')])}
</section>""")

    if as_of and not final:
        y, m, d = as_of.split("-")
        stamp = f"{int(y)}年{int(m)}月{int(d)}日終了時点"
    else:
        stamp = f"{year}年 最終成績"
    desc = (f"【{stamp}】" + "。".join(summary) + "。"
            "プロ野球の全選手のwOBA・wRC+・FIP・K−BB%・簡易WARを毎日自動で計算し、"
            "リーグ・球団・守備位置・規定到達で絞り込んで並べ替えられます。2005年以降の各シーズンに対応。")
    tpl = TEMPLATE.read_text(encoding="utf-8")
    opts = "".join(f'<option value="{y}">{y}年{"（シーズン中）" if y == year and not final else ""}</option>'
                   for y in sorted(years, reverse=True))
    return (tpl.replace("{{DESCRIPTION}}", html.escape(desc, quote=True))
               .replace("{{STAMP}}", html.escape(stamp))
               .replace("{{YEAR}}", str(year))
               .replace("{{YEAR_OPTIONS}}", opts)
               .replace("{{UPDATED}}", datetime.now(JST).strftime("%Y年%-m月%-d日 %H:%M"))
               .replace("{{TOP_TABLES}}", "\n".join(blocks)))


def pack(year, st, batters, pitchers):
    # id：選手ページ（/player/<id>/）がある選手だけ。無ければ null
    bcols = ["name", "teams", "lg", "pos", "hand", "g", "pa", "h", "hr", "rbi", "sb", "avg", "obp", "slg",
             "ops", "woba", "wrcp", "iso", "babip", "kp", "bbp", "war", "qual",
             "ab", "bb", "so", "wraa", "wsb", "posr", "repl", "id"]
    pcols = ["name", "teams", "lg", "role", "hand", "g", "w", "l", "sv", "hld", "ip", "so", "era", "fip",
             "whip", "kp", "bbp", "kbb", "hr9", "war", "qual", "outs", "bb", "hr", "id"]
    return {"year": year, "as_of": st.get("as_of"), "final": bool(st.get("final")),
            "bcols": bcols, "bat": [[b[c] for c in bcols] for b in batters],
            "pcols": pcols, "pit": [[p[c] for c in pcols] for p in pitchers]}



def apply_names(people, batters, pitchers):
    """登録名が本名と違う選手は「岡田 貴弘（T-岡田）」のように表示する。
    同じ年に同じ登録名の別人がいれば（西武とソフトバンクの「カブレラ」）、名簿の表記で見分ける"""
    who = {}
    for x in batters + pitchers:
        who.setdefault(x["name"], set()).add(x["pid"] or tuple(x["teams"]))
    for x in batters + pitchers:
        if not x["pid"]:
            continue
        if len(who[x["name"]]) > 1:
            x["name"] = people.by_pid[x["pid"]]["name"]
        else:
            x["name"] = people.registered_name(x["pid"], x["name"])


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--league", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args(argv)

    league = json.loads(Path(args.league).read_text(encoding="utf-8"))["seasons"]
    out = Path(args.out)
    (out / "data").mkdir(parents=True, exist_ok=True)
    reg = Path(args.data) / "register.json"
    people = People(reg) if reg.exists() else None

    stores = {}
    for f in sorted(Path(args.data).glob("season_*.json")):
        st = json.loads(f.read_text(encoding="utf-8"))
        if str(st["year"]) in league:
            stores[st["year"]] = st
    links = people.link_all({y: season_rows(st) for y, st in stores.items()}) if people else {}
    seasons = [(y, st) + compute_season(st, league[str(y)], links.get(y)) for y, st in stores.items()]

    # 選手ページ（npb/build_players.py が作る）がある選手には、名前にリンクを付ける
    built = out.parent / "player" / "built.json"
    has_page = set(json.loads(built.read_text(encoding="utf-8"))["pids"]) if built.exists() else set()
    years, latest = [], None
    for y, st, batters, pitchers in seasons:
        for x in batters + pitchers:
            x["id"] = x["pid"] if x["pid"] in has_page else None
        if people:
            apply_names(people, batters, pitchers)
        (out / "data" / f"{y}.json").write_text(
            json.dumps(pack(y, st, batters, pitchers), ensure_ascii=False, separators=(",", ":")) + "\n",
            encoding="utf-8")
        years.append(y)
        latest = (y, st, batters, pitchers)

    y, st, batters, pitchers = latest
    page = render(y, st.get("as_of"), st.get("final"), batters, pitchers, years)
    (out / "index.html").write_text(page, encoding="utf-8")
    print(f"saber: {years[0]}〜{years[-1]}年、最新 {y}年 打者{len(batters)} 投手{len(pitchers)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
