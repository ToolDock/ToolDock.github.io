#!/usr/bin/env python3
"""トップページのツール一覧を、生のHTMLとして index.html に書き込む。

これまで一覧は tool-data.js からJSで組み立てていた。JSを動かさないと
リンクが1本も存在しないので、Googlebot がツールのページを見つけるのが
レンダリング待ちのぶんだけ遅れる。新しく足したページほど影響を受ける。

情報源は tool-data.js のままで、そこから生成してHTMLに焼く。
ツールを足したら、これを走らせること。

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
        got = {k: re.search(k + r':\s*"([^"]*)"', block) for k in
               ("title", "url", "category")}
        if all(got.values()):
            tools.append({k: v.group(1) for k, v in got.items()})
    return categories, tools


def render(categories, tools):
    out = [BEGIN]
    for key, label in categories:
        items = [t for t in tools if t["category"] == key]
        if not items:
            continue
        out.append(f"  <h2>{html.escape(label)}</h2>")
        out.append("  <ul>")
        for t in items:
            out.append(f'    <li><a href="{html.escape(t["url"])}">'
                       f'{html.escape(t["title"])}</a></li>')
        out.append("  </ul>")
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
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
