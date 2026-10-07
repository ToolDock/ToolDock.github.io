"""記録達成カウントダウン（/milestone/）を作る。

現役選手（最新のシーズンに一軍に出場した選手）の、デビューからの通算成績で
「2000安打まであと何本」「200勝まであと何勝」を並べ、今のペースでいつ届くかを見積もる。

- 通算：2004年以前はNPB公式の選手ページの記録（npb/data/player_profiles.json）、
  2005年以降は npb/data/season_<年>.json の成績（選手ページと同じ）
- 名球会の3記録（2000安打・200勝・250セーブ）は日米通算。メジャー経験者のMLBでの通算は
  npb/data/mlb_totals.json に手で入れてある
- 毎日更新（シーズン中は数字が毎日変わる）

    python npb/build_milestone.py --data npb/data --league war/league.json --out milestone
"""

from __future__ import annotations

import argparse
import html
import json
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_players as bp  # noqa: E402

JST = timezone(timedelta(hours=9))

# (項目, 表示名, 単位, 打撃か投球か, 節目, 名球会の節目)
RECORDS = [
    ("h", "安打", "本", "bat", [1000, 1500, 2000, 2500], 2000),
    ("hr", "本塁打", "本", "bat", [100, 150, 200, 250, 300, 400, 500], None),
    ("rbi", "打点", "打点", "bat", [500, 1000, 1500], None),
    ("sb", "盗塁", "盗塁", "bat", [100, 200, 300], None),
    ("g", "出場試合", "試合", "bat", [1000, 1500, 2000], None),
    ("w", "勝利", "勝", "pit", [100, 150, 200], 200),
    ("sv", "セーブ", "セーブ", "pit", [100, 200, 250], 250),
    ("hld", "ホールド", "ホールド", "pit", [100, 150, 200, 250, 300], None),
    ("so", "奪三振", "奪三振", "pit", [1000, 1500, 2000], None),
    ("g", "登板", "登板", "pit", [500, 600, 700, 800, 1000], None),
]

# 一覧に出す範囲：次の節目の、この割合以上に来ている選手だけ（騒がれ始めるころから）。
# 2000安打なら1760本、250セーブなら220セーブ、200勝なら176勝から
NEAR = 0.88
# 来季以降の見込みに使う「1シーズンの量」は、直近この年数の平均（出場した年だけ）
PACE_YEARS = 3
SEASON_MONTHS = ["4月", "5月", "6月", "7月", "8月", "9月"]
# これより先の見込みは「○シーズン以上先」とまとめる（出場が減っている選手のペースで割ると、数十年先と出てしまう）
MAX_SEASONS = 5


def esc(s):
    return html.escape(str(s), quote=True)


def load_mlb(data_dir):
    p = data_dir / "mlb_totals.json"
    if not p.exists():
        return {}
    d = json.loads(p.read_text(encoding="utf-8"))
    return {k: v for k, v in d.items() if not k.startswith("_")}


def when_text(need, per_season_now, left_ratio, per_season, final):
    """あと need を、今季の残り（今季ペース）→ 来季以降（1シーズンの量）で埋めると、いつ届くか"""
    if need <= 0:
        return "達成", 0
    rest_now = 0 if final else per_season_now * left_ratio
    if rest_now >= need:
        return "今季中に届くペース", 1
    if per_season <= 0:
        return "―", 9
    left = need - rest_now
    seasons = left / per_season
    if seasons <= 1:
        m = SEASON_MONTHS[min(len(SEASON_MONTHS) - 1, int(seasons * len(SEASON_MONTHS)))]
        return f"来季{m}ごろ", 2 + seasons
    if seasons > MAX_SEASONS:
        return f"{MAX_SEASONS}シーズン以上先", 3 + seasons
    return f"約{seasons:.0f}シーズン後", 3 + seasons


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--league", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args(argv)
    data = Path(args.data)
    league = json.loads(Path(args.league).read_text(encoding="utf-8"))["seasons"]
    people, by_pid, picks, profiles, stores, last_season, _ = bp.load(data, league)
    mlb = load_mlb(data)
    latest = max(stores)
    st = json.loads((data / f"season_{latest}.json").read_text(encoding="utf-8"))
    final = bool(st.get("final"))
    team_games = {t["name"]: t["games"] for t in st["teams"].values()}
    built_path = Path(args.out).parent / "player" / "built.json"
    has_page = set(json.loads(built_path.read_text(encoding="utf-8"))["pids"]) if built_path.exists() else set()

    # 今季の各球団の消化割合（残り試合の見込みに使う）
    SEASON_GAMES = 143

    rows = {rec: [] for rec in range(len(RECORDS))}
    for pid, seasons in by_pid.items():
        if not any(y == latest for y, _, _ in seasons) or pid.startswith("r") or pid not in people.by_pid:
            continue
        person = people.by_pid[pid]
        bat, pit = bp.seasons_of(pid, by_pid, profiles.get(pid))
        tot = {"bat": bp.totals(bat, bp.BAT_KEYS), "pit": bp.totals(pit, bp.PIT_KEYS)}
        now_rows = {"bat": [r for r in bat if r["y"] == latest], "pit": [r for r in pit if r["y"] == latest]}
        team = (now_rows["bat"] or now_rows["pit"])[0]["teams"][-1]
        played = team_games.get(team, SEASON_GAMES)
        left_ratio = max(0, SEASON_GAMES - played) / max(1, played)
        kind = bp.kind_of(bat, pit)
        for i, (k, label, unit, side, marks, meikyu) in enumerate(RECORDS):
            if side == "bat" and kind == "p":
                continue            # 投手の打撃成績は数えない
            if side == "pit" and not pit:
                continue
            rs = bat if side == "bat" else pit
            v = tot[side][k]
            now = sum(r[k] for r in now_rows[side])
            recent = sorted({r["y"] for r in rs if r["y"] < latest}, reverse=True)[:PACE_YEARS]
            per = [sum(r[k] for r in rs if r["y"] == y) for y in recent]
            per_season = now / max(1e-9, played / SEASON_GAMES) if played else 0
            if per:
                per_season = (sum(per) + per_season) / (len(per) + 1)
            extra = mlb.get(pid, {}).get(k, 0) if meikyu else 0
            for m in marks:
                # 名球会の節目は日米通算で見る。それ以外はNPBだけ
                cur = v + extra if m == meikyu else v
                if cur >= m:
                    continue
                if cur < m * NEAR:
                    break
                txt, order = when_text(m - cur, now, left_ratio, per_season, final)
                rows[i].append({"pid": pid, "name": person["name"], "team": team, "v": v, "cur": cur,
                                "m": m, "need": m - cur, "now": now, "when": txt, "order": order,
                                "mlb": extra if m == meikyu else 0, "unit": unit, "meikyu": m == meikyu})
                break

    def name_cell(e):
        n = bp.disp(e["name"])
        return f'<a href="/player/{e["pid"]}/">{esc(n)}</a>' if e["pid"] in has_page else esc(n)

    sections, nav, count = [], [], 0
    for i, (k, label, unit, side, marks, meikyu) in enumerate(RECORDS):
        es = sorted(rows[i], key=lambda e: (-e["m"], e["need"]))
        slug = f"{side}-{k}"
        if not es:
            continue
        count += len(es)
        nav.append(f'<a href="#{slug}">{esc(label)}</a>')
        has_mlb = any(e["mlb"] for e in es)
        head = ('<tr><th class="nm">選手</th><th class="mk">節目</th><th>通算</th><th>あと</th>'
                f'<th class="opt">{latest}年</th><th>見込み</th></tr>')
        body = "".join(
            f'<tr><th class="nm">{name_cell(e)}<span class="tm">{esc(e["team"])}</span></th>'
            f'<td class="mk">{e["m"]}{unit}</td>'
            f'<td class="cur">{e["cur"]}' + (f'<span class="sub">NPB {e["v"]}＋MLB {e["mlb"]}</span>' if e["mlb"] else "")
            + f'<span class="prog" title="節目の{100 * e["cur"] / e["m"]:.1f}%"><i style="width:{min(100, 100 * e["cur"] / e["m"]):.1f}%"></i></span>'
            f'<span class="pct">{100 * e["cur"] / e["m"]:.1f}%</span></td>'
            f'<td class="need">{e["need"]}<span class="sub m-only">{e["m"]}{unit}まで</span></td>'
            f'<td class="opt">{e["now"]}</td>'
            f'<td class="when w{min(3, int(e["order"]))}">{esc(e["when"])}</td></tr>' for e in es)
        badge = f'<span class="badge">名球会 {meikyu}{unit}（日米通算）</span>' if meikyu else ""
        sections.append(f'<section class="rec" id="{slug}"><h2>{esc(label)}{badge}</h2>'
                        f'<p class="marks">節目：{"・".join(f"{m}{unit}" for m in marks)}</p>'
                        f'<div class="tbl-wrap"><table class="std"><thead>{head}</thead><tbody>{body}</tbody></table></div></section>')

    as_of = st.get("as_of") or ""
    try:
        d = datetime.strptime(as_of, "%Y-%m-%d")
        as_of_text = f"{d.year}年{d.month}月{d.day}日" + ("（シーズン終了）" if final else "終了時点")
    except ValueError:
        as_of_text = f"{latest}年"
    # 説明文には、名球会に近い選手を3人まで
    tops = sorted((e for v in rows.values() for e in v if e["meikyu"]), key=lambda e: e["need"])
    lead_bits = [f'{bp.disp(e["name"])}（{e["m"]}{e["unit"]}まであと{e["need"]}）' for e in tops[:3]]
    desc = (f"プロ野球の現役選手が、2000本安打・200勝・250セーブ（名球会）や300本塁打・1500奪三振などの節目の記録まであと何本かを毎日更新。"
            + (f"{'、'.join(lead_bits)}など。" if lead_bits else "")
            + "今のペースでいつ届くかの見込みも出しています。")
    now = datetime.now(JST)
    template = (Path(__file__).resolve().parent / "template_milestone.html").read_text(encoding="utf-8")
    rep = {"{{DESCRIPTION}}": esc(desc), "{{AS_OF}}": esc(as_of_text),
           "{{UPDATED}}": f"{now.year}年{now.month}月{now.day}日 {now.hour}:{now.minute:02d}",
           "{{NAV}}": "".join(nav), "{{SECTIONS}}": "\n".join(sections), "{{YEAR}}": str(latest),
           "{{NEAR}}": str(round(NEAR * 100)), "{{COUNT}}": str(count), "{{PACE_YEARS}}": str(PACE_YEARS)}
    page = template
    for a, b in rep.items():
        page = page.replace(a, b)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "index.html").write_text(page, encoding="utf-8")
    print(f"milestone: {latest}年 {count}件")
    return 0


if __name__ == "__main__":
    sys.exit(main())
