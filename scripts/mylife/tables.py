# -*- coding: utf-8 -*-
"""静的な表と、計算機が読むJSONを、data.py から作る。"""
import html, json, re
import data as d

def sign(v):
    if v is None or v == 0: return ""
    return f"＋{v}" if v > 0 else f"−{abs(v)}"

def cell(v, cls=""):
    c = f' class="{cls}"' if cls else ""
    return f"<td{c}>{v}</td>"

def num_cell(delta, key):
    v = delta.get(key)
    if not v: return '<td class="n zero">−</td>'
    return f'<td class="n {"up" if v > 0 else "down"}">{sign(v)}</td>'

# ── 成長タイプ ──────────────────────────────────────────
def growth_table():
    rows = []
    for name, pro, other, age in d.GROWTH:
        used = "" if (pro or other) else " class=\"dim\""
        rows.append(
            f"<tr{used}><th scope=\"row\">{name}</th>"
            f"<td>{html.escape(pro) or '−'}</td>"
            f"<td>{html.escape(other) or '−'}</td>"
            f"<td class=\"n\">{age}歳ごろ</td></tr>")
    return ("<table class=\"tbl growth\"><thead><tr>"
            "<th>成長タイプ</th><th>プロ野球人生編</th>"
            "<th>憧れ・オリジナル選手編</th><th>衰えはじめ</th>"
            "</tr></thead><tbody>" + "".join(rows) + "</tbody></table>")

# ── 初期能力 ────────────────────────────────────────────
def base_table(base, order, label):
    head = "".join(f"<th>{c}</th>" for c in d.CAREERS)
    rows = []
    for k in order:
        tds = "".join(f'<td class="n">{base[c][k]}</td>' for c in d.CAREERS)
        rows.append(f'<tr><th scope="row">{k}</th>{tds}</tr>')
    return (f'<table class="tbl"><caption>{label}</caption><thead><tr><th>能力</th>{head}</tr>'
            f'</thead><tbody>{"".join(rows)}</tbody></table>')

# ── ドラフト順位 ────────────────────────────────────────
def draft_pitcher_table():
    head = "".join(f"<th>{i}位</th>" for i in range(1, 7))
    rows = []
    for k in ["球速", "コントロール", "スタミナ", "変化球"]:
        tds = "".join(f'<td class="n">{sign(d.PITCHER_DRAFT[i][k]) or "±0"}</td>' for i in range(1, 7))
        rows.append(f'<tr><th scope="row">{k}</th>{tds}</tr>')
    return ('<table class="tbl"><caption>投手</caption><thead><tr><th>能力</th>'
            f'{head}</tr></thead><tbody>{"".join(rows)}</tbody></table>')

def draft_batter_table():
    head = "".join(f"<th>{i}位</th>" for i in range(1, 7))
    tds = "".join(f'<td class="n">{sign(d.BATTER_DRAFT_ALL[i]) or "±0"}</td>' for i in range(1, 7))
    rows = [f'<tr><th scope="row">{k}</th>{tds}</tr>' for k in d.BATTER_DRAFT_KEYS]
    return ('<table class="tbl"><caption>野手</caption><thead><tr><th>能力</th>'
            f'{head}</tr></thead><tbody>{"".join(rows)}</tbody></table>')

# ── アピール／ウィーク ──────────────────────────────────
P_KEYS = ["球速", "コントロール", "スタミナ", "変化球"]
B_KEYS = ["弾道", "ミート", "パワー", "走力", "肩力", "守備力", "捕球"]

def point_table_pitcher(items, caption):
    head = "".join(f"<th>{k}</th>" for k in P_KEYS)
    rows = []
    for name, delta, skill, fielder in items:
        tds = "".join(num_cell(delta, k) for k in P_KEYS)
        rows.append(f'<tr><th scope="row">{html.escape(name)}</th>{tds}'
                    f'<td>{html.escape(skill) or "−"}</td>'
                    f'<td>{html.escape(fielder) or "−"}</td></tr>')
    return (f'<p class="scroll-hint">※ 表は横にスクロールします</p>'
            f'<div class="scroll"><table class="tbl points"><caption>{caption}</caption>'
            f'<thead><tr><th>名前</th>{head}<th>特殊能力</th><th>野手能力</th></tr></thead>'
            f'<tbody>{"".join(rows)}</tbody></table></div>')

def point_table_batter(items, caption):
    head = "".join(f"<th>{k}</th>" for k in B_KEYS)
    rows = []
    for name, delta, skill in items:
        tds = "".join(num_cell(delta, k) for k in B_KEYS)
        rows.append(f'<tr><th scope="row">{html.escape(name)}</th>{tds}'
                    f'<td>{html.escape(skill) or "−"}</td></tr>')
    return (f'<p class="scroll-hint">※ 表は横にスクロールします</p>'
            f'<div class="scroll"><table class="tbl points"><caption>{caption}</caption>'
            f'<thead><tr><th>名前</th>{head}<th>特殊能力</th></tr></thead>'
            f'<tbody>{"".join(rows)}</tbody></table></div>')

# ── 計算機が読むデータ ──────────────────────────────────
def payload():
    return json.dumps({
        "careers": d.CAREERS,
        "pitcher": {
            "base": d.PITCHER_BASE, "order": d.PITCHER_ORDER, "draft": d.PITCHER_DRAFT,
            "appeal": [{"name": n, "d": dl, "s": s, "f": f} for n, dl, s, f in d.P_APPEAL],
            "weak":   [{"name": n, "d": dl, "s": s, "f": f} for n, dl, s, f in d.P_WEAK],
        },
        "batter": {
            "base": d.BATTER_BASE, "order": d.BATTER_ORDER,
            "draftAll": d.BATTER_DRAFT_ALL, "draftKeys": d.BATTER_DRAFT_KEYS,
            "appeal": [{"name": n, "d": dl, "s": s} for n, dl, s in d.B_APPEAL],
            "weak":   [{"name": n, "d": dl, "s": s} for n, dl, s in d.B_WEAK],
        },
        "growthMap": {f"{c}|{r}": g for (c, r), g in d.GROWTH_MAP.items()},
        "growthAge": {n: a for n, _, _, a in d.GROWTH},
    }, ensure_ascii=False, separators=(",", ":"))


# ── おすすめ編成 ────────────────────────────────────────
def _find(items, name):
    for it in items:
        if it[0] == name:
            return it
    raise KeyError(name)

def build_stats(kind, career, rank, appeal_name, weak_name):
    """計算機と同じ足し算を Python 側でもやる。表の数字を手で書かないため。"""
    if kind == "pitcher":
        base, order = d.PITCHER_BASE[career], ["球速", "コントロール", "スタミナ", "変化球"]
        draft = d.PITCHER_DRAFT[rank]
        ap, wk = _find(d.P_APPEAL, appeal_name), _find(d.P_WEAK, weak_name)
    else:
        base, order = d.BATTER_BASE[career], d.BATTER_ORDER
        draft = {k: d.BATTER_DRAFT_ALL[rank] for k in d.BATTER_DRAFT_KEYS}
        ap, wk = _find(d.B_APPEAL, appeal_name), _find(d.B_WEAK, weak_name)

    vals = {}
    for k in order:
        vals[k] = base.get(k, 0) + draft.get(k, 0) + ap[1].get(k, 0) + wk[1].get(k, 0)

    skills = [x for x in (ap[2], wk[2]) if x and x != "変化なし"]
    kinds = 2
    for s in skills:
        m = re.search(r"球種最大＋(\d)", s)
        if m:
            kinds += int(m.group(1))
    return vals, order, "／".join(skills), kinds

def _build_card(title, setup, memo, pairs, extra=""):
    chips = "".join(
        f'<div class="stat"><div class="stat__k">{html.escape(k)}</div>'
        f'<div class="stat__v">{v}</div></div>' for k, v in pairs)
    tail = f'<p class="build__extra">{extra}</p>' if extra else ""
    return (f'<div class="build"><p class="build__name">{html.escape(title)}</p>'
            f'<p class="build__setup">{html.escape(setup)}</p>'
            f'<div class="stats">{chips}</div>{tail}'
            f'<p class="build__memo">{html.escape(memo)}</p></div>')

def builds_batter():
    out = []
    for career, rank, ap, wk, memo in d.BUILDS_BATTER:
        vals, order, _, _ = build_stats("batter", career, rank, ap, wk)
        out.append(_build_card(
            ap, f"{career}ドラフト{rank}位／ウィークポイント {wk}", memo,
            [(k, vals[k]) for k in order]))
    return "".join(out)

def builds_pitcher():
    keys = ["球速", "コントロール", "スタミナ", "変化球"]
    out = []
    for career, rank, ap, wk, memo in d.BUILDS_PITCHER:
        vals, _, skills, kinds = build_stats("pitcher", career, rank, ap, wk)
        extra = f"最大球種 {kinds}" + (f"／特殊能力 {html.escape(skills)}" if skills else "")
        out.append(_build_card(
            ap, f"{career}ドラフト{rank}位／ウィークポイント {wk}", memo,
            [(k, vals[k]) for k in keys], extra))
    return "".join(out)
