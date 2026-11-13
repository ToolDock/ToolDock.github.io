#!/usr/bin/env python3
"""
栄冠ナイン 金特ページ（/eikan-kintoku/）の「金特から入手方法を探す」と「転生選手の一覧」を書き込む。

データ
  - 金特の一覧と、国際大会で取れるもの：このファイルの KINTOKU / KOKUSAI
  - 転生選手（OB・プロ・コラボ）で金特を持つ選手：eikan-kintoku/tensei.tsv
    列は 都道府県（コラボは作品名）・選手名・ポジション・☆・年度（コラボは -）・金特（カンマ区切り）
    名前に「（DLC）」が付いたものは歴代レジェンドDLCの選手

金特本は、マイライフの能力研究所にある金特（/kintoku/）と、精神的支柱などマイライフに無い8つがすべて出る（持ち主の確認、2026-11）。

使い方
    python3 scripts/build_eikan_kintoku.py
ページの <!-- KT-LIST --> と <!-- TENSEI-TABLE --> の区間を書き換える。
"""
import html
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PAGE = ROOT / "eikan-kintoku" / "index.html"
TSV = ROOT / "eikan-kintoku" / "tensei.tsv"
KINTOKU_PAGE = ROOT / "kintoku" / "index.html"

COLLAB = {"にじさんじ", "ダイヤのA"}

# 表示順・種類（p=投手 b=野手 a=どちらも）・元になる青特（"-" は元の青特が無く金特だけのもの）
KINTOKU = [
    # 野手：打撃
    ("安打製造機", "b", "アベレージヒッター"), ("アーチスト", "b", "パワーヒッター"),
    ("広角砲", "b", "広角打法"), ("引っ張り屋", "b", "プルヒッター"), ("芸術的流し打ち", "b", "流し打ち"),
    ("勝負師", "b", "チャンスA"), ("恐怖の満塁男", "b", "満塁男"), ("伝説のサヨナラ男", "b", "サヨナラ男"),
    ("代打の神様", "b", "代打〇"), ("切り込み隊長", "b", "チャンスメーカー"), ("大番狂わせ", "b", "意外性"),
    ("火事場の馬鹿力", "b", "逆境〇"), ("メッタ打ち", "b", "固め打ち"), ("一球入魂", "b", "初球〇"),
    ("左腕キラー", "b", "対左投手A"), ("ストレートキラー", "b", "対ストレート〇"), ("おかわり", "b", "マルチ弾"),
    ("高球必打", "b", "ハイボールヒッター"), ("低球必打", "b", "ローボールヒッター"),
    ("内角必打", "b", "インコースヒッター"), ("外角必打", "b", "アウトコースヒッター"),
    ("精神的支柱", "b", "ムード〇"), ("トリックスター", "b", "かく乱"),
    # 野手：走塁
    ("電光石火", "b", "盗塁A"), ("高速ベースラン", "b", "走塁A"), ("ロケットスタート", "b", "内野安打〇"),
    ("重戦車", "b", "ホーム突入"), ("気迫ヘッド", "b", "ヘッドスライディング"),
    # 野手：守備・捕手
    ("魔術師", "b", "守備職人"), ("高速レーザー", "b", "レーザービーム"), ("ストライク送球", "b", "送球A"),
    ("バズーカ送球", "b", "-"), ("球界の頭脳", "b", "キャッチャーA"), ("鉄の壁", "b", "ホーム死守"),
    ("ささやき戦術", "b", "-"),
    # どちらも
    ("鉄人", "a", "ケガしにくさA"),
    # 投手
    ("怪物球威", "p", "重い球"), ("ドクターK", "p", "奪三振"), ("変幻自在", "p", "緩急〇"),
    ("精密機械", "p", "低め〇"), ("驚異の切れ味", "p", "キレ〇"), ("怪童", "p", "ノビA"),
    ("強心臓", "p", "対ピンチA"), ("不屈の魂", "p", "打たれ強さA"), ("鉄腕", "p", "投手調子安定"),
    ("ガソリンタンク", "p", "回復A"), ("本塁打厳禁", "p", "逃げ球"), ("走者釘付", "p", "クイックA"),
    ("左キラー", "p", "対左打者A"), ("内角無双", "p", "内角攻め"), ("ハイスピンジャイロ", "p", "ジャイロボール"),
    ("闘魂", "p", "闘志"), ("勝利の星", "p", "勝ち運"), ("ギアチェンジ", "p", "-"), ("クロスキャノン", "p", "クロスファイヤー"),
    ("威圧感", "p", "存在感"),
]

# 国際大会：金特 → (確定で取れる評価, MVPで出ることがあるか)
KOKUSAI = {
    "安打製造機": ("大会首位打者", True), "アーチスト": ("大会最多本塁打", True),
    "電光石火": ("大会最多盗塁", True), "勝負師": ("大会最多打点", True),
    "魔術師": ("大会最優秀守備選手", True), "強心臓": ("大会の最優秀防御率", True),
    "怪物球威": ("", True), "ドクターK": ("", True), "変幻自在": ("", True), "精密機械": ("", True),
}

SIDE = {"p": ("投手", "p"), "b": ("野手", "b"), "a": ("投手・野手", "n")}
e = html.escape


def book_kintoku():
    """マイライフの能力研究所にある金特（マイナスのものを除く）＝金特本で出る金特"""
    s = KINTOKU_PAGE.read_text(encoding="utf-8")
    names = re.findall(r'<h3 class="skill-name">([^<]+)</h3>', s)
    # マイライフに無い金特でも、栄冠ナインでは金特本で出るもの（持ち主の確認、2026-11）
    extra = {"精神的支柱", "闘魂", "ささやき戦術", "勝利の星", "ギアチェンジ", "バズーカ送球", "トリックスター", "クロスキャノン"}
    return (set(names) | extra) - {"ガラスのハート", "ノミの心臓", "扇風機"}


def load_tensei():
    rows = []
    for line in TSV.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        pref, name, pos, star, year, kins = line.split("\t")
        dlc = "（DLC）" in name
        rows.append({
            "pref": pref, "name": name.replace("（DLC）", "").strip(), "dlc": dlc, "pos": pos,
            "star": int(star), "year": year, "kins": [k.strip() for k in kins.split(",") if k.strip()],
            "collab": pref in COLLAB,
        })
    return rows


def kana(s):
    """検索用：ひらがなをカタカナにそろえる"""
    return "".join(chr(ord(c) + 0x60) if "ぁ" <= c <= "ゖ" else c for c in s)


def who(r):
    if r["collab"]:
        return f'{e(r["name"])}<span class="wk">（{e(r["pref"])}・{e(r["pos"])}・☆{r["star"]}）</span>'
    tag = '<span class="dlc">歴代レジェンド</span>' if r["dlc"] else ""
    return f'{e(r["name"])}{tag}<span class="wk">（{e(r["pref"])}・{r["year"]}年度・{e(r["pos"])}・☆{r["star"]}）</span>'


def build_list(rows, book):
    known = {k for k, _, _ in KINTOKU}
    missing = sorted({k for r in rows for k in r["kins"]} - known)
    if missing:
        sys.exit(f"KINTOKU に無い金特が表にあります: {missing}")
    out = []
    for name, side, base in KINTOKU:
        lab, cls = SIDE[side]
        ways, q = [], [name, "" if base == "-" else base]
        if name in book:
            ways.append(("book", "金特本", "甲子園のOBの祝いの品・アイテム業者"))
        if name in KOKUSAI:
            fixed, mvp = KOKUSAI[name]
            t = (f"<strong>{e(fixed)}</strong>で確定" if fixed else "") + ("、" if fixed and mvp else "") + \
                (f"大会MVP（{'野手' if side == 'b' else '投手'}）でランダム" if mvp else "")
            ways.append(("kok", "国際大会", t))
        if name == "威圧感":
            ways.append(("kok", "国際大会", "大会最優秀救援投手（存在感との2択）"))
            ways.append(("train", "特訓・合宿", "ほかの青特と同じように取れる（金特の例外）"))
        ob = [r for r in rows if name in r["kins"] and not r["collab"]]
        co = [r for r in rows if name in r["kins"] and r["collab"]]
        if ob:
            ways.append(("ten", "転生", "、".join(who(r) for r in ob)))
            q += [r["name"] for r in ob]
        if co:
            ways.append(("col", "コラボ", "、".join(who(r) for r in co)))
            q += [r["name"] for r in co] + sorted({r["pref"] for r in co})
        if name not in book and name != "威圧感":
            ways.insert(0, ("none", "金特本", "マイライフに無い金特のため未確認"))
        keys = " ".join(sorted({w[0] for w in ways if w[0] != "none"}))
        if name in book and not is_kok(name) and not ob and not co:
            keys += " only"   # 金特本でしか取れない
        lis = "\n".join(f'      <li><span class="w w-{k}">{e(lab2)}</span><span class="wd">{d}</span></li>' for k, lab2, d in ways)
        base_html = ('<span class="kt-base">元の青特：なし（金特だけの特殊能力）</span>' if base == "-"
                     else f'<span class="kt-base">元の青特：{e(base)}</span>' if base else "")
        qtxt = kana(" ".join(x for x in q if x)).lower().replace(" ", "")
        out.append(
            f'  <div class="kt" id="kt-{e(name)}" data-side="{side}" data-ways="{keys}" data-q="{e(qtxt)}">\n'
            f'    <h3 class="kt-name">{e(name)} <span class="badge {cls}">{lab}</span></h3>{base_html}\n'
            f'    <ul class="kt-ways">\n{lis}\n    </ul>\n  </div>'
        )
    return "\n".join(out)


def is_kok(k):
    return k in KOKUSAI or k == "威圧感"


def paid(r):
    return r["dlc"] or r["pref"] == "ダイヤのA"


def kin_links(kins):
    """国際大会で取れない金特は太字にする"""
    return "、".join(
        f'<a href="#kt-{e(k)}"' + ("" if is_kok(k) else ' class="nk"') + f'>{e(k)}</a>' for k in kins)


def tag_html(r):
    if r["dlc"]:
        return '<span class="dlc">歴代レジェンド</span>'
    if r["pref"] == "ダイヤのA":
        return '<span class="dlc">DLC</span>'
    return ""


def build_table(rows):
    """選手から探す：検索・絞り込み・並べ替えつきの表"""
    out = []
    for n, r in enumerate(rows):
        tags = ["collab" if r["collab"] else "ob"]
        if len(r["kins"]) >= 2:
            tags.append("multi")
        if any(not is_kok(k) for k in r["kins"]):
            tags.append("nokok")
        if not paid(r):
            tags.append("free")
        year = "いつでも" if r["collab"] else f'{r["year"]}年度'
        yv = 9999 if r["collab"] else int(r["year"])
        co_cls = ' class="co"' if r["collab"] else ""
        q = kana(" ".join([r["name"], r["pref"], r["pos"]] + r["kins"] + (["歴代レジェンド", "dlc"] if r["dlc"] else []))).lower().replace(" ", "")
        out.append(
            f'<tr{co_cls} data-q="{e(q)}" data-tags="{" ".join(tags)}" data-co="{1 if r["collab"] else 0}" data-star="{r["star"]}" data-kin="{len(r["kins"])}" data-year="{yv}" data-order="{n}">'
            f'<td class="pn">{e(r["name"])}{tag_html(r)}</td><td>{e(r["pref"])}</td><td>{year}</td>'
            f'<td>{e(r["pos"])}</td><td class="r">{r["star"]}</td><td>{kin_links(r["kins"])}</td></tr>')
    return (
        '<div class="card pf" id="players">\n'
        '    <h2>金特を持つ選手から探す</h2>\n'
        '    <p class="lead">選手名・都道府県・作品名・金特・守備で探せます（例：イチロー、兵庫、にじさんじ、怪童、捕）。'
        '<b class="nk-legend">太字の金特</b>は国際大会では取れない金特です。</p>\n'
        '    <div class="kt-filter">\n'
        '        <input type="search" id="pq" placeholder="選手名・都道府県・作品・金特で検索" aria-label="選手名・都道府県・作品・金特で検索" autocomplete="off">\n'
        '        <select id="psort" aria-label="並べ替え"><option value="order">都道府県順</option><option value="star">☆が高い順</option>'
        '<option value="kin">金特が多い順</option><option value="year">年度が古い順</option></select>\n'
        '        <div class="kt-chips" id="pChips">\n'
        '            <label><input type="checkbox" value="multi"> 金特を2つ以上</label>\n'
        '            <label><input type="checkbox" value="nokok"> 国際大会で取れない金特を持つ</label>\n'
        '            <label><input type="checkbox" value="ob"> 転生OB・プロ</label>\n'
        '            <label><input type="checkbox" value="collab"> 転生コラボ</label>\n'
        '            <label><input type="checkbox" value="free"> DLCなしで仲間にできる</label>\n'
        '        </div>\n'
        f'        <span class="filter-count"><strong id="pCount">{len(rows)}</strong> 人を表示中</span>\n'
        '    </div>\n'
        '    <div class="scroll"><table class="tensei" id="pTable">\n'
        '    <thead><tr><th>選手</th><th>都道府県・作品</th><th>年度</th><th>守備</th><th class="r">☆</th><th>持っている金特</th></tr></thead>\n'
        '    <tbody>\n' + "\n".join(out) + '\n    </tbody></table></div>\n'
        '    <p class="empty" id="pEmpty" hidden>あてはまる選手がいません</p>\n'
        '</div>'
    )


def who_short(r):
    sub = r["pref"] if r["collab"] else f'{r["pref"]}・{r["year"]}年度'
    body = f'{e(r["name"])}{tag_html(r)}<span class="wk">（{e(sub)}・☆{r["star"]}）</span>'
    return f'<span class="co-name">{body}</span>' if r["collab"] else body


def build_pickup(rows, book):
    # 転生コラボは例外の枠なので、いつも後ろにまとめる
    multi = sorted([r for r in rows if len(r["kins"]) >= 2], key=lambda r: (r["collab"], -len(r["kins"]), -r["star"]))
    def chip(k):
        cls = "chip" if is_kok(k) else "chip nk"
        return f'<a href="#kt-{e(k)}" class="{cls}">{e(k)}</a>'

    def card(r):
        sub = e(r["pref"]) + ("" if r["collab"] else "・" + r["year"] + "年度")
        return (f'<div class="pk{" co" if r["collab"] else ""}"><div class="pk-n">{e(r["name"])}{tag_html(r)}</div>'
                f'<div class="pk-s">{sub}・{e(r["pos"])}・☆{r["star"]}</div>'
                f'<div class="pk-k">{"".join(chip(k) for k in r["kins"])}</div></div>')
    cards = "\n".join(card(r) for r in multi)
    order = [k for k, _, _ in KINTOKU]
    nokok = [k for k in order if not is_kok(k) and any(k in r["kins"] for r in rows)]
    trs = []
    for k in nokok:
        holders = sorted([r for r in rows if k in r["kins"]], key=lambda r: r["collab"])
        other = "金特本" if k in book else '<span class="muted">金特本は未確認</span>'
        trs.append(f'<tr><td><a href="#kt-{e(k)}" class="nk">{e(k)}</a></td><td>{"、".join(who_short(r) for r in holders)}</td><td>{other}</td></tr>')
    return (
        f'<h3 id="multi">金特を2つ以上持つ選手（{len(multi)}人）</h3>\n'
        '<p>1人で金特を2つ・3つ持っている選手です。入部させるだけで、金特を一度に複数手に入れられます。</p>\n'
        f'<div class="pk-grid">\n{cards}\n</div>\n'
        f'<h3 id="nokok">国際大会では取れない金特を持つ選手（{len(nokok)}種）</h3>\n'
        '<p>国際大会で取れる金特は、野手5つ（安打製造機・アーチスト・電光石火・勝負師・魔術師）と投手5つ（強心臓・怪物球威・ドクターK・変幻自在・精密機械）、それに威圧感だけです。'
        'それ以外の金特を狙うなら、金特本を待つか、その金特を持つ転生選手を仲間にすることになります。</p>\n'
        '<div class="table-scroll"><table class="tensei">\n<thead><tr><th>金特</th><th>持っている選手</th><th>ほかの取り方</th></tr></thead>\n<tbody>\n'
        + "\n".join(trs) + '\n</tbody></table></div>'
    )


def build_book_only(rows, book):
    held = {k for r in rows for k in r["kins"]}
    only = [(k, side) for k, side, _ in KINTOKU if k in book and not is_kok(k) and k not in held]
    chips = "".join(f'<a href="#kt-{e(k)}" class="chip">{e(k)}</a>' for k, _ in only)
    return (
        f'<h3 id="book-only">金特本でしか取れない金特（{len(only)}種）</h3>\n'
        '<p>次の金特は、国際大会では取れず、持っている転生選手もいません（2026年11月時点で分かっている範囲）。'
        '栄冠ナインで付けるには、<strong>金特本が出るのを待つしかありません</strong>。'
        'OBの祝いの品とアイテム業者を毎回確かめておきましょう。</p>\n'
        f'<div class="chips">{chips}</div>'
    )


def replace(page, tag, body):
    pat = re.compile(rf"(<!-- {tag} -->\n).*?(<!-- /{tag} -->)", re.S)
    if not pat.search(page):
        sys.exit(f"ページに <!-- {tag} --> の区間がありません")
    return pat.sub(lambda m: m.group(1) + body + "\n" + m.group(2), page)


def main():
    rows = load_tensei()
    book = book_kintoku()
    page = PAGE.read_text(encoding="utf-8")
    page = replace(page, "KT-LIST", build_list(rows, book))
    page = replace(page, "TENSEI-TABLE", build_table(rows))
    page = replace(page, "PICKUP", build_pickup(rows, book))
    page = replace(page, "BOOK-ONLY", build_book_only(rows, book))
    PAGE.write_text(page, encoding="utf-8")
    print(f"金特 {len(KINTOKU)}種・転生選手 {len(rows)}人を書き込みました")


if __name__ == "__main__":
    main()
