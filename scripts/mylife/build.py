# -*- coding: utf-8 -*-
"""/mylife-start/index.html を組み立てる。データは data.py が唯一の情報源。"""
import io, pathlib
import data as d
import tables as t

HERE = pathlib.Path(__file__).resolve().parent
CSS = (HERE / "style.css.part").read_text(encoding="utf-8")
APP = (HERE / "app.js.part").read_text(encoding="utf-8")

TITLE = "パワプロ2026-2027 マイライフ 経歴とドラフト順位｜初期能力の計算"
DESC = ("パワプロ2026-2027のマイライフをプロ野球人生編で始めるときの、経歴・ドラフト順位・"
        "アピールポイント・ウィークポイントのまとめです。選ぶだけで初期能力を計算できるので、"
        "どの組み合わせがいちばん高くなるかをその場で比べられます。"
        "経歴とドラフト順位で決まる成長タイプと、衰えはじめる年齢の目安も載せています。")

FAQ = [
 ("マイライフの初期能力はどうやって決まりますか？",
  "経歴（高校卒・大学卒・社会人／独立リーグ）で決まる基礎値に、ドラフト順位ぶんの上乗せを足し、"
  "そこへアピールポイントとウィークポイントの増減を反映したものが初期能力になります。"
  "ドラフト1位と6位では、投手のコントロールとスタミナで30、野手の各能力で28の差がつきます。"),
 ("経歴とドラフト順位で成長タイプが変わりますか？",
  "プロ野球人生編では変わります。高卒ドラフト1〜2位が早め1、高卒3〜4位と大卒1〜2位が普通早2、"
  "高卒5〜6位・大卒3〜4位・社会人1〜2位が普通早1、大卒5〜6位と社会人3〜4位が普通、"
  "社会人5〜6位が普通遅1です。憧れ現役選手編とオリジナル選手編では、"
  "その選手にもともと設定されている成長タイプがそのまま反映されます。"),
 ("晩成型にするとデメリットはありますか？",
  "マイライフにはサクセスのような「成長期前」がほぼ無いため、晩成にしても若いうちに能力が上がりにくくなる、"
  "といったことは起きません。衰えはじめる年齢が後ろにずれるぶん、長く伸ばせます。"
  "尻尾を使えば成長タイプを晩成の側へ動かせるので、手に入れたそばから使って構いません。"),
 ("アピールポイントは何を選ぶのがおすすめですか？",
  "投手は変化球を伸ばすものです。鋭い変化球が無いと抑えるのが難しいためです。"
  "先発でいくなら、長いイニングを投げるためにスタミナを伸ばす「無類のタフネス」も有力です。"
  "野手は打撃がそのまま成績になるので、ミートかパワーを伸ばすものを選んでください。"),
 ("ウィークポイントは何を選ぶのがおすすめですか？",
  "能力が変わらない「これといってないです」が無難です。"
  "ただしマイライフは特殊能力を取りやすく、ウィークポイントで付いた赤特殊能力は後から簡単に消せます。"
  "プレイに自信があるなら、赤特殊能力は気にせず、能力値の上乗せが大きいものを選ぶ手もあります。"),
 ("マイライフの他のまとめもありますか？",
  "能力研究所の金特ミッション一覧、イベントクリスタルと万能クリスタルの入手方法、"
  "尻尾の入手方法をまとめています。尻尾は成長タイプを晩成の側へ動かせるので、"
  "このページと合わせて見てください。"),
 ("他モードで作った選手をマイライフで使う場合、成長タイプは何がいいですか？",
  "超晩成にしておくのがおすすめです。マイライフでは晩成のデメリットがほぼ無く、"
  "衰えはじめる年齢が遅いほど長く伸ばせるためです。超晩成は遅め1にあたり、35歳ごろまで衰えません。"),
]

def faq_html():
    out = []
    for q, a in FAQ:
        out.append(f"<h3>{q}</h3>\n<p>{a}</p>")
    return "\n\n".join(out)

def faq_jsonld():
    import json
    return json.dumps({
        "@context": "https://schema.org", "@type": "FAQPage",
        "mainEntity": [{"@type": "Question", "name": q,
                        "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in FAQ],
    }, ensure_ascii=False, indent=2)

PAGE = f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">

<!-- 検索結果で切られる先頭30字ほどに、探している語を入れる。
     サイト名は付けない（この長さでは席がもったいない） -->
<title>{TITLE}</title>
<meta name="description" content="{DESC}">
<link rel="canonical" href="https://tooldock.github.io/mylife-start/">

<script> const CURRENT_TOOL = "mylife-start"; </script>
<script src="/js/tool-data.js"></script>
<script src="/js/head.js"></script>
<script src="/js/analytics.js"></script>

<!-- Google AdSense -->
<script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-8349615939902537" crossorigin="anonymous"></script>

<style>
{CSS}</style>
</head>
<body>

<header>
    <div class="page-wrapper">
        <h1>パワプロ2026-2027 マイライフ 経歴とドラフト順位の選び方</h1>
        <p>プロ野球人生編。選ぶだけで初期能力と成長タイプが出ます</p>
    </div>
</header>

<div class="page-wrapper">

<main>

<h2>初期能力シミュレーター</h2>

<p>
経歴・ドラフト順位・アピールポイント・ウィークポイントを選ぶと、
その組み合わせで始めたときの初期能力が出ます。
下の数字の小さいほうは「基礎値と、そこからの増減」です。
</p>

<div class="sim">
    <div class="seg" role="group" aria-label="投手か野手か">
        <button type="button" data-kind="pitcher" aria-pressed="true">投手</button>
        <button type="button" data-kind="batter" aria-pressed="false">野手</button>
    </div>

    <div class="sim__form">
        <div class="field">
            <label for="career">経歴</label>
            <select id="career"></select>
        </div>
        <div class="field">
            <label for="rank">ドラフト順位</label>
            <select id="rank"></select>
        </div>
        <div class="field">
            <label for="appeal">アピールポイント</label>
            <select id="appeal"></select>
        </div>
        <div class="field">
            <label for="weak">ウィークポイント</label>
            <select id="weak"></select>
        </div>
    </div>

    <div class="result">
        <p class="result__head">
            <span>成長タイプ <b id="growth">−</b></span>
            <span>衰えはじめ <b id="decline">−</b></span>
        </p>
        <div class="stats" id="stats"></div>
        <p class="skills" id="skills"></p>
        <p class="note">
            弾道・肩力・走力・守備力・捕球には、ドラフト順位の上乗せが入らないものがあります。
            表のとおりに計算しています。
        </p>
    </div>
</div>

<h2>経歴とドラフト順位で決まる成長タイプ</h2>

<p>
プロ野球人生編では、経歴とドラフト順位の組み合わせで成長タイプが決まります。
憧れ現役選手編とオリジナル選手編では、その選手にもともと設定されている成長タイプが反映されます。
</p>

<div class="scroll">{t.growth_table()}</div>

<p class="note">
灰色の行は、プロ野球人生編でも憧れ現役選手編・オリジナル選手編でも選べないものです。
尻尾や早熟チョコで動かした先として存在します。
</p>

<h2>経歴ごとの初期能力</h2>

<p>ドラフト順位やアピールポイントを足す前の、経歴だけで決まる基礎値です。</p>

<div class="scroll">{t.base_table(d.PITCHER_BASE, d.PITCHER_ORDER, "投手")}</div>
<div class="scroll">{t.base_table(d.BATTER_BASE, d.BATTER_ORDER, "野手")}</div>

<h2>ドラフト順位による上乗せ</h2>

<p>
上位ほど大きく上乗せされます。投手のコントロールとスタミナは1位と6位で30、
野手は6つの能力すべてが1位と6位で28ちがいます。ここがいちばん差の付くところです。
</p>

<div class="scroll">{t.draft_pitcher_table()}</div>
<div class="scroll">{t.draft_batter_table()}</div>

<h2>アピールポイント・ウィークポイント（投手）</h2>

{t.point_table_pitcher(d.P_APPEAL, "アピールポイント")}
{t.point_table_pitcher(d.P_WEAK, "ウィークポイント")}

<h2>アピールポイント・ウィークポイント（野手）</h2>

{t.point_table_batter(d.B_APPEAL, "アピールポイント")}
{t.point_table_batter(d.B_WEAK, "ウィークポイント")}

</main>

<article class="tool-article">

<h2>選び方</h2>

<h3>ドラフト順位は上位ほど得</h3>

<p>
初期能力でいちばん差が付くのはドラフト順位です。
投手ならコントロールとスタミナが1位と6位で30ちがい、野手は6つの能力すべてで28ちがいます。
経歴による基礎値の差（投手のコントロールで高校卒19、社会人27）より大きいので、
まず順位を上げることを考えてください。
</p>

<h3>成長タイプは、あとから動かせる</h3>

<p>
経歴とドラフト順位で決まる成長タイプは、あとから変えられます。
マイライフで手に入る<a href="/shippo/">尻尾</a>を使うと晩成の側へ動き、
ショッピングモールで買える早熟チョコを使うと早熟の側へ動きます。
</p>

<p>
マイライフにはサクセスのような「成長期前」がほぼ無いので、
<strong>晩成にすることのデメリットはありません</strong>。
若いうちに能力が上がりにくくなる、といったことは起きず、
衰えはじめる年齢が後ろにずれるぶん、長く伸ばせます。
尻尾は手に入れたそばから使って構いません。
</p>

<p>
他モードで作った選手をマイライフに持ち込む場合も同じで、
<strong>超晩成</strong>にしておくのがおすすめです。表の遅め1にあたり、35歳ごろまで衰えません。
</p>

<h3>アピールポイントは、投手なら変化球</h3>

<p>
投手は、鋭い変化球を持っていないと抑えるのが難しくなります。
変化球を伸ばせるものを選んでください。
先発でいくなら、長いイニングを投げるためのスタミナも要るので、
「無類のタフネス」でスタミナを21伸ばすのも有力です。
</p>

<p>
野手は打撃がそのまま成績になるので、ミートかパワーを伸ばすものを選びます。
「抜群のバットコントロール」はミートを21、「圧倒的なパワー」はパワーを21伸ばします。
</p>

<h3>ウィークポイントは「これといってないです」が無難</h3>

<p>
能力の増減が無い「これといってないです」を選んでおけば、余計なものが付きません。
</p>

<p>
ただし<strong>マイライフは特殊能力を取りやすく、赤特殊能力は後から簡単に消せます</strong>。
プレイに自信があるなら、赤特殊能力は気にせず、能力値の上乗せが大きいものを選ぶ手もあります。
たとえば投手の「ノミの心臓」はコントロールが8上がり、代わりに対ピンチFが付きます。
</p>

<h2>マイライフの他のまとめ</h2>

<ul>
<li><a href="/kintoku/">能力研究所の金特ミッション一覧</a></li>
<li><a href="/crystal/">イベントクリスタル（小）（大）の入手方法</a></li>
<li><a href="/crystal-banno/">万能クリスタル（小）（大）の入手方法</a></li>
<li><a href="/shippo/">尻尾の入手方法</a>｜成長タイプを晩成の側へ動かせます</li>
</ul>

<h2>よくある質問</h2>

{faq_html()}

</article>

</div>

<script>
window.__MYLIFE__ = {t.payload()};
</script>

<script>
{APP}</script>

<script type="application/ld+json">
{faq_jsonld()}
</script>

<div id="related-tools"></div>
<script src="/js/related.js"></script>

</body>
</html>
"""

def main():
    out = HERE.parent.parent.parent  # 使わない。呼び出し側でパスを渡す
    return PAGE

if __name__ == "__main__":
    import sys
    dest = pathlib.Path(sys.argv[1])
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(PAGE, encoding="utf-8")
    print(f"{dest} に {len(PAGE):,} bytes")
