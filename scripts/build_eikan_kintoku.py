#!/usr/bin/env python3
"""
栄冠ナイン 金特ページ（/eikan-kintoku/）の「金特から入手方法を探す」と「転生選手の一覧」を書き込む。

データ
  - 金特の一覧と、国際大会で取れるもの：このファイルの KINTOKU / KOKUSAI
  - 転生選手（OB・プロ・コラボ）で金特を持つ選手：eikan-kintoku/tensei.tsv
    列は 都道府県（コラボは作品名）・選手名・ポジション・☆・年度（コラボは -）・金特（カンマ区切り）
    名前に「（DLC）」が付いたものは歴代レジェンドDLCの選手

金特本は、マイライフの能力研究所にある金特（/kintoku/）がすべて出る（持ち主の確認、2026-11）。

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

# 表示順・種類（p=投手 b=野手 a=どちらも）・元になる青特（分からないものは空）
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
    ("精神的支柱", "b", ""), ("トリックスター", "b", ""),
    # 野手：走塁
    ("電光石火", "b", "盗塁A"), ("高速ベースラン", "b", "走塁A"), ("ロケットスタート", "b", "内野安打〇"),
    ("重戦車", "b", "ホーム突入"), ("気迫ヘッド", "b", "ヘッドスライディング"),
    # 野手：守備・捕手
    ("魔術師", "b", "守備職人"), ("高速レーザー", "b", "レーザービーム"), ("ストライク送球", "b", "送球A"),
    ("バズーカ送球", "b", ""), ("球界の頭脳", "b", "キャッチャーA"), ("鉄の壁", "b", "ホーム死守"),
    ("ささやき戦術", "b", ""),
    # どちらも
    ("鉄人", "a", "ケガしにくさA"),
    # 投手
    ("怪物球威", "p", "重い球"), ("ドクターK", "p", "奪三振"), ("変幻自在", "p", "緩急〇"),
    ("精密機械", "p", "低め〇"), ("驚異の切れ味", "p", "キレ〇"), ("怪童", "p", "ノビA"),
    ("強心臓", "p", "対ピンチA"), ("不屈の魂", "p", "打たれ強さA"), ("鉄腕", "p", "投手調子安定"),
    ("ガソリンタンク", "p", "回復A"), ("本塁打厳禁", "p", "逃げ球"), ("走者釘付", "p", "クイックA"),
    ("左キラー", "p", "対左打者A"), ("内角無双", "p", "内角攻め"), ("ハイスピンジャイロ", "p", "ジャイロボール"),
    ("闘魂", "p", ""), ("勝利の星", "p", ""), ("ギアチェンジ", "p", ""), ("クロスキャノン", "p", ""),
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
    return set(names) - {"ガラスのハート", "ノミの心臓", "扇風機"}


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
        ways, q = [], [name, base]
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
        lis = "\n".join(f'      <li><span class="w w-{k}">{e(lab2)}</span><span class="wd">{d}</span></li>' for k, lab2, d in ways)
        base_html = f'<span class="kt-base">元の青特：{e(base)}</span>' if base else ""
        qtxt = kana(" ".join(x for x in q if x)).lower().replace(" ", "")
        out.append(
            f'  <div class="kt" id="kt-{e(name)}" data-side="{side}" data-ways="{keys}" data-q="{e(qtxt)}">\n'
            f'    <h3 class="kt-name">{e(name)} <span class="badge {cls}">{lab}</span></h3>{base_html}\n'
            f'    <ul class="kt-ways">\n{lis}\n    </ul>\n  </div>'
        )
    return "\n".join(out)


def build_table(rows):
    def tr(r):
        kins = "、".join(f'<a href="#kt-{e(k)}">{e(k)}</a>' for k in r["kins"])
        if r["collab"]:
            return (f'<tr><td>{e(r["name"])}</td><td>{e(r["pref"])}</td><td>いつでも</td>'
                    f'<td>{e(r["pos"])}</td><td class="r">{r["star"]}</td><td>{kins}</td></tr>')
        nm = e(r["name"]) + ('<span class="dlc">歴代レジェンド</span>' if r["dlc"] else "")
        return (f'<tr><td>{nm}</td><td>{e(r["pref"])}</td><td>{r["year"]}年度</td>'
                f'<td>{e(r["pos"])}</td><td class="r">{r["star"]}</td><td>{kins}</td></tr>')
    head = '<thead><tr><th>選手</th><th>{}</th><th>年度</th><th>守備</th><th class="r">☆</th><th>持っている金特</th></tr></thead>'
    ob = [r for r in rows if not r["collab"]]
    co = [r for r in rows if r["collab"]]
    return (
        '<h3 id="tensei-ob">転生OB・転生プロ（' + str(len(ob)) + '人）</h3>\n'
        '<div class="table-scroll"><table class="tensei">\n' + head.format("都道府県") + '\n<tbody>\n'
        + "\n".join(tr(r) for r in ob) + '\n</tbody></table></div>\n'
        '<h3 id="tensei-collab">転生コラボ（' + str(len(co)) + '人）</h3>\n'
        '<div class="table-scroll"><table class="tensei">\n' + head.format("作品") + '\n<tbody>\n'
        + "\n".join(tr(r) for r in co) + '\n</tbody></table></div>'
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
    PAGE.write_text(page, encoding="utf-8")
    print(f"金特 {len(KINTOKU)}種・転生選手 {len(rows)}人を書き込みました")


if __name__ == "__main__":
    main()
