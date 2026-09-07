# -*- coding: utf-8 -*-
"""静的な表と、計算機が読むJSONを、data.py から作る。"""
import html, json
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
