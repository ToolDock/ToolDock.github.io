#!/usr/bin/env python3
"""トップページのツール一覧を、生のHTMLとして index.html に書き込む。

これまで一覧は tool-data.js からJSで組み立てていた。JSを動かさないと
リンクが1本も存在しないので、Googlebot がツールのページを見つけるのが
レンダリング待ちのぶんだけ遅れる。新しく足したページほど影響を受ける。

情報源は tool-data.js のままで、そこから生成してHTMLに焼く。
ツールを足したら、これを走らせること（サイトマップ sitemap.xml も作り直す）。

    python3 scripts/build_index.py
    python3 scripts/build_index.py --check   # ずれていたら終了コード1
"""

import html
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INDEX = ROOT / "index.html"
DATA = ROOT / "js" / "tool-data.js"

BEGIN = "  <!-- ここから scripts/build_index.py が生成する。手で書き換えない -->"
END = "  <!-- ここまで -->"


def parse_tools():
    js = DATA.read_text(encoding="utf-8")

    names = re.search(r"window\.CATEGORY_NAMES\s*=\s*\{(.*?)\};", js, re.S)
    categories = re.findall(r"(\w+)\s*:\s*\"([^\"]+)\"", names.group(1))

    tools = []
    body = js[js.index("window.TOOLS"):]
    for block in re.findall(r"\{[^{}]*?id:\s*\"[^\"]+\"[\s\S]*?\n  \}", body):
        if re.search(r"hidden:\s*true", block):
            continue
        got = {k: re.search(r"\b" + k + r':\s*"([^"]*)"', block) for k in
               ("id", "title", "desc", "url", "category")}
        if all(got.values()):
            tool = {k: v.group(1) for k, v in got.items()}
            pop = re.search(r"popularity:\s*(\d+)", block)
            tool["popularity"] = int(pop.group(1)) if pop else 0
            tools.append(tool)
    return categories, tools


# トップの「よく使われているツール」に出す数（tool-data.js の popularity の大きい順）
POPULAR = 6


def card(t, rank=None):
    """ツール1件のカード。一覧は <div id="tool-list"> の中に置くので </div> は使わない"""
    badge = f'<span class="tc-rank">{rank}</span>' if rank else ""
    return (f'    <li><a class="tool-card c-{html.escape(t["category"])}" '
            f'href="{html.escape(t["url"])}">{badge}'
            f'<span class="tc-title">{html.escape(t["title"])}</span>'
            f'<span class="tc-desc">{html.escape(t["desc"])}</span></a></li>')


def render(categories, tools):
    labels = dict(categories)
    out = [BEGIN]

    # カテゴリへのジャンプ
    out.append('  <nav class="cat-jump" aria-label="カテゴリ">')
    for key, label in categories:
        n = sum(t["category"] == key for t in tools)
        if n:
            out.append(f'    <a class="c-{key}" href="#cat-{key}">'
                       f'{html.escape(label)}<span>{n}</span></a>')
    out.append("  </nav>")

    popular = sorted((t for t in tools if t["popularity"] > 0),
                     key=lambda t: -t["popularity"])[:POPULAR]
    if popular:
        out.append('  <section class="cat" id="popular">')
        out.append("  <h2>よく使われているツール</h2>")
        out.append('  <ul class="tool-grid">')
        for rank, t in enumerate(popular, 1):
            out.append(card(t, rank))
        out.append("  </ul>")
        out.append("  </section>")

    for key, label in categories:
        items = [t for t in tools if t["category"] == key]
        if not items:
            continue
        out.append(f'  <section class="cat c-{key}" id="cat-{key}">')
        out.append(f'  <h2>{html.escape(labels[key])}'
                   f'<span class="cat-n">{len(items)}</span></h2>')
        out.append('  <ul class="tool-grid">')
        for t in items:
            out.append(card(t))
        out.append("  </ul>")
        out.append("  </section>")
    out.append(END)
    return "\n".join(out)


def main(argv):
    categories, tools = parse_tools()
    listing = render(categories, tools)

    page = INDEX.read_text(encoding="utf-8")
    block = re.compile(r'(<div id="tool-list">)(.*?)(</div>)', re.S)
    if not block.search(page):
        print('index.html に <div id="tool-list"> が見つからない', file=sys.stderr)
        return 1

    updated = block.sub(
        lambda m: m.group(1) + "\n" + listing + "\n" + m.group(3), page)
    updated = re.sub(r'(<strong id="tool-count">)[^<]*(</strong>)',
                     rf"\g<1>{len(tools)}\g<2>", updated)

    if "--check" in argv:
        if updated != page:
            print("index.html の一覧が tool-data.js とずれている。"
                  "python3 scripts/build_index.py を実行すること", file=sys.stderr)
            return 1
        print(f"一覧は最新（{len(tools)}件）")
        return 0

    INDEX.write_text(updated, encoding="utf-8")
    print(f"index.html にツール {len(tools)}件を書き込み")
    # ツールを足したらサイトマップにも載せる
    import build_sitemap
    return build_sitemap.main([])


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
