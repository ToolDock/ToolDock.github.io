#!/usr/bin/env python3
"""NPB公式の勝敗表を取得し、マジックナンバーのページを静的HTMLとして書き出す。

    python3 npb/build_magic.py --out magic
    python3 npb/build_magic.py --html-dir _probe --year 2026 --out /tmp/magic   # 手元のHTMLで試す

外部ライブラリは使わない（標準ライブラリのみ）。
GitHub Actions（.github/workflows/update-npb.yml）から毎日呼ばれる。
"""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
import time
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from magic import Team, analyze  # noqa: E402

HERE = Path(__file__).resolve().parent
TEMPLATE = HERE / "template.html"
JST = timezone(timedelta(hours=9))

URL = "https://npb.jp/bis/{year}/stats/std_{lg}.html"

# 1シーズンの試合数。リーグ内は同一カード25試合、交流戦18試合（計143）
PER_OPPONENT = 25
INTERLEAGUE = 18
CS_SLOTS = 3

# 勝率が並んだとき、勝利数の多いほうを上位にするリーグ（セ・リーグのみ）
LEAGUES = [("c", "セ・リーグ", "central"), ("p", "パ・リーグ", "pacific")]
WINS_TIEBREAK = {"c": True, "p": False}

# 正式名 → 表示名・勝敗表の見出しの1文字
TEAMS = {
    "阪神タイガース": ("阪神", "神"),
    "読売ジャイアンツ": ("巨人", "巨"),
    "横浜DeNAベイスターズ": ("DeNA", "デ"),
    "東京ヤクルトスワローズ": ("ヤクルト", "ヤ"),
    "広島東洋カープ": ("広島", "広"),
    "中日ドラゴンズ": ("中日", "中"),
    "福岡ソフトバンクホークス": ("ソフトバンク", "ソ"),
    "埼玉西武ライオンズ": ("西武", "西"),
    "北海道日本ハムファイターズ": ("日本ハム", "日"),
    "オリックス・バファローズ": ("オリックス", "オ"),
    "千葉ロッテマリーンズ": ("ロッテ", "ロ"),
    "東北楽天ゴールデンイーグルス": ("楽天", "楽"),
}


# ---------------------------------------------------------------- 取得・解析

def fetch(url, tries=4):
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (compatible; ToolDock/1.0; +https://tooldock.github.io/)"})
    for i in range(tries):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.read().decode("utf-8", "replace")
        except Exception as e:  # noqa: BLE001
            if i == tries - 1:
                raise
            print(f"retry {url}: {e}", file=sys.stderr)
            time.sleep(2 ** (i + 1))


def _cell(s):
    s = re.sub(r"(?i)<br\s*/?>", " ", s)
    s = re.sub(r"<[^>]+>", "", s)
    return html.unescape(s).strip()


def _record(s):
    """'11-10 (1)' → (11, 10, 1)。'***' は None。"""
    m = re.match(r"(\d+)-(\d+)(?:\s*\((\d+)\))?", s)
    if not m:
        return None
    return int(m.group(1)), int(m.group(2)), int(m.group(3) or 0)


def parse_standings(page):
    """std_c.html / std_p.html → (as_of, [Team...]) 順位順。"""
    as_of = None
    m = re.search(r"(\d{4})年(\d{1,2})月(\d{1,2})日\s*現在", page)
    if m:
        as_of = f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"

    start = page.index("チーム勝敗表")
    table = re.search(r"<table.*?</table>", page[start:], re.S).group(0)

    heads = [_cell(h) for h in re.findall(r"<th[^>]*>(.*?)</th>", table, re.S)]
    rows = []
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", table, re.S):
        tds = [_cell(td) for td in re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)]
        if tds:
            rows.append(dict(zip(heads, tds)))

    abbr_to_short = {v[1]: v[0] for v in TEAMS.values()}
    teams = []
    for r in rows:
        name = r["チーム"]
        if name not in TEAMS:
            raise ValueError(f"知らない球団名: {name}")
        short = TEAMS[name][0]
        t = Team(name, short, int(r["勝利"]), int(r["敗北"]), int(r["引分"]))
        t.gb = r.get("差", "")
        played = 0
        for h, v in r.items():
            if h.startswith("対") and h[1:] in abbr_to_short:
                rec = _record(v)
                if rec is None:
                    continue
                opp = abbr_to_short[h[1:]]
                n = sum(rec)
                t.rem[opp] = PER_OPPONENT - n
                played += n
        inter = _record(r.get("交流戦", "")) or (0, 0, 0)
        t.rem_out = INTERLEAGUE - sum(inter)
        played += sum(inter)
        if played != t.games:
            raise ValueError(f"{short}: 対戦成績の合計 {played} と試合数 {t.games} が合わない")
        teams.append(t)

    # 対戦の残りは双方で一致するはず
    by = {t.short: t for t in teams}
    for t in teams:
        for o, n in t.rem.items():
            if by[o].rem.get(t.short) != n or n < 0:
                raise ValueError(f"{t.short}-{o} の残り試合数が合わない")
    return as_of, teams


# ---------------------------------------------------------------- 表示

def pct_str(t):
    d = t.w + t.l
    if not d:
        return ".000"
    s = f"{t.w / d:.3f}"
    return s[1:] if s.startswith("0") else s


def status(r, done):
    """(優勝セルの文字, class), (CSセルの文字, class)"""
    if r["v_clinched"]:
        v = ("優勝", "win")
    elif r["magic_lit"]:
        v = (f"M{r['v_num']}", "magic")
    elif r["v_num"] is not None:
        v = (f"自力（{r['v_num']}勝）", "own")
    elif r["v_possible"]:
        v = ("他力", "other")
    else:
        v = ("消滅" if not done else "―", "out")

    if r["cs_clinched"]:
        c = ("確定", "win")
    elif r["cs_num"] is not None:
        c = (f"あと{r['cs_num']}勝", "own")
    elif r["cs_possible"]:
        c = ("他力", "other")
    else:
        c = ("消滅" if not done else "―", "out")
    return v, c


def headline(label, teams, res, done):
    by = {t.short: t for t in teams}
    champ = next((t.short for t in teams if res[t.short]["v_clinched"]), None)
    lit = next((t.short for t in teams if res[t.short]["magic_lit"]), None)

    if champ:
        big = f'<span class="hl-team">{html.escape(champ)}</span><span class="hl-num">優勝</span>'
        sub = "リーグ優勝が決まっています。"
        sentence = f"{label}は{champ}が優勝を決めています。"
    elif lit:
        r = res[lit]
        big = (f'<span class="hl-team">{html.escape(lit)}</span>'
               f'<span class="hl-label">優勝マジック</span>'
               f'<span class="hl-num">{r["v_num"]}</span>')
        sub = f"対象チーム：{html.escape(r['target'])}" if r["target"] else ""
        sentence = f"{label}は{lit}に優勝マジック{r['v_num']}が点灯しています。"
    else:
        own = [t.short for t in teams if res[t.short]["v_num"] is not None]
        big = '<span class="hl-none">マジック未点灯</span>'
        if own:
            sub = "自力優勝の可能性があるチーム：" + "・".join(html.escape(x) for x in own)
        else:
            sub = "どのチームも自力で優勝を決められない状態です（他力のみ）。"
        sentence = f"{label}はまだマジックが点灯していません。"

    cs_done = [t.short for t in teams if res[t.short]["cs_clinched"]]
    if cs_done and not done:
        cs = "CS進出確定：" + "・".join(html.escape(x) for x in cs_done)
    elif done:
        cs = "レギュラーシーズン終了"
    else:
        cs = ""
    del by
    return big, sub, cs, sentence


def league_block(key, label, teams, res):
    done = all(t.rem_total == 0 for t in teams)
    big, sub, cs, sentence = headline(label, teams, res, done)

    rows = []
    for i, t in enumerate(teams, 1):
        (vt, vc), (ct, cc) = status(res[t.short], done)
        rows.append(
            f'<tr><td class="rk">{i}</td>'
            f'<th scope="row" class="tm">{html.escape(t.short)}</th>'
            f'<td class="opt">{t.games}</td><td>{t.w}</td><td>{t.l}</td><td class="opt">{t.t}</td>'
            f'<td class="pct">{pct_str(t)}</td><td>{html.escape(t.gb or "")}</td>'
            f'<td>{t.rem_total}</td>'
            f'<td class="st st-{vc}">{html.escape(vt)}</td>'
            f'<td class="st st-{cc}">{html.escape(ct)}</td></tr>')

    shorts = [t.short for t in teams]
    mhead = "".join(f"<th scope=\"col\">{html.escape(s)}</th>" for s in shorts)
    mrows = []
    for t in teams:
        cells = []
        for o in shorts:
            if o == t.short:
                cells.append('<td class="self">―</td>')
            else:
                n = t.rem.get(o, 0)
                cells.append(f'<td class="{"zero" if n == 0 else ""}">{n}</td>')
        cells.append(f'<td class="{"zero" if t.rem_out == 0 else ""}">{t.rem_out}</td>')
        cells.append(f"<td class=\"sum\">{t.rem_total}</td>")
        mrows.append(f'<tr><th scope="row" class="tm">{html.escape(t.short)}</th>{"".join(cells)}</tr>')

    block = f"""
<section class="league league-{key}" id="{key}">
  <h2>{label}</h2>
  <div class="hl">
    <div class="hl-main">{big}</div>
    {f'<p class="hl-sub">{sub}</p>' if sub else ''}
    {f'<p class="hl-cs">{cs}</p>' if cs else ''}
  </div>

  <div class="tbl-wrap">
  <table class="std">
    <thead><tr><th scope="col">順位</th><th scope="col">チーム</th><th scope="col" class="opt">試合</th><th scope="col">勝</th><th scope="col">敗</th><th scope="col" class="opt">分</th><th scope="col">勝率</th><th scope="col">差</th><th scope="col">残り</th><th scope="col">優勝</th><th scope="col">CS</th></tr></thead>
    <tbody>
{chr(10).join(rows)}
    </tbody>
  </table>
  </div>

  <h3>残り試合の対戦カード</h3>
  <div class="tbl-wrap">
  <table class="rem">
    <thead><tr><th scope="col"></th>{mhead}<th scope="col">交流戦</th><th scope="col">計</th></tr></thead>
    <tbody>
{chr(10).join(mrows)}
    </tbody>
  </table>
  </div>
</section>"""
    return block, sentence, done


def to_json(teams, res):
    out = []
    for t in teams:
        r = res[t.short]
        out.append({
            "team": t.short, "w": t.w, "l": t.l, "t": t.t, "remaining": t.rem_total,
            "magic": r["v_num"] if r["magic_lit"] else None,
            "own_v": r["v_num"], "own_cs": r["cs_num"],
            "v_possible": r["v_possible"], "cs_possible": r["cs_possible"],
            "v_clinched": r["v_clinched"], "cs_clinched": r["cs_clinched"],
            "target": r["target"],
        })
    return out


# ---------------------------------------------------------------- 本体

def load_year(year, html_dir):
    pages = {}
    for lg, _, _ in LEAGUES:
        if html_dir:
            pages[lg] = (Path(html_dir) / f"std_{lg}.html").read_text(encoding="utf-8")
        else:
            pages[lg] = fetch(URL.format(year=year, lg=lg))
            time.sleep(1)
    return pages


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--year", type=int)
    ap.add_argument("--html-dir")
    args = ap.parse_args(argv)

    now = datetime.now(JST)
    year = args.year or now.year

    try:
        pages = load_year(year, args.html_dir)
        parsed = {lg: parse_standings(p) for lg, p in pages.items()}
        if all(t.games == 0 for _, ts in parsed.values() for t in ts):
            raise ValueError("まだ試合がない")
    except Exception as e:  # 開幕前は前年の最終成績を出す
        if args.year or args.html_dir:
            raise
        print(f"{year}年が使えないので前年にする: {e}", file=sys.stderr)
        year -= 1
        pages = load_year(year, None)
        parsed = {lg: parse_standings(p) for lg, p in pages.items()}

    blocks, sentences, data = [], [], {}
    as_of = None
    all_done = True
    for lg, label, key in LEAGUES:
        d, teams = parsed[lg]
        as_of = as_of or d
        by = {t.short: t for t in teams}
        res = analyze(by, CS_SLOTS, WINS_TIEBREAK[lg])
        block, sentence, done = league_block(key, label, teams, res)
        all_done &= done
        blocks.append(block)
        sentences.append(sentence)
        data[key] = to_json(teams, res)

    if as_of:
        y, m, d = as_of.split("-")
        as_of_jp = f"{int(y)}年{int(m)}月{int(d)}日終了時点"
    else:
        as_of_jp = f"{year}年 レギュラーシーズン最終成績"
    if all_done:
        as_of_jp = f"{year}年 レギュラーシーズン最終成績"

    summary = "".join(sentences)
    desc = (f"【{as_of_jp}】{summary}"
            "セ・パ両リーグの順位表と、優勝マジック・CS進出のクリンチナンバー・"
            "自力優勝の有無を毎日自動で計算して掲載しています。")

    tpl = TEMPLATE.read_text(encoding="utf-8")
    page = (tpl.replace("{{DESCRIPTION}}", html.escape(desc, quote=True))
               .replace("{{AS_OF}}", html.escape(as_of_jp))
               .replace("{{YEAR}}", str(year))
               .replace("{{SUMMARY}}", html.escape(summary))
               .replace("{{UPDATED}}", now.strftime("%Y年%-m月%-d日 %H:%M"))
               .replace("{{LEAGUES}}", "\n".join(blocks)))

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "index.html").write_text(page, encoding="utf-8")

    payload = {"year": year, "as_of": as_of, "final": all_done, **data}
    (out / "data.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    # マジックの推移を残しておく（日付ごとに上書き）
    hist_path = out / "history.json"
    try:
        hist = json.loads(hist_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, ValueError):
        hist = {}
    if as_of:
        hist[as_of] = {k: {r["team"]: r["magic"] for r in v if r["magic"] is not None}
                       for k, v in data.items()}
    hist_path.write_text(json.dumps(hist, ensure_ascii=False, indent=1, sort_keys=True) + "\n",
                         encoding="utf-8")

    print(summary)
    return 0


if __name__ == "__main__":
    sys.exit(main())
