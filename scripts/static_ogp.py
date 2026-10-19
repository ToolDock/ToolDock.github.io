#!/usr/bin/env python3
"""SNSの共有カード（OGP）を、各ページのHTMLに直接書き込む。

これまでOGPは js/head.js が document.write で書いていたが、X・LINE・Facebook などは
JavaScriptを動かさずにページを読むので、共有してもカードが出なかった。
head.js と同じ中身（タイトル・説明・URL・画像）を <head> に焼き込む。
head.js は og:image がすでにあるページでは書かない。

- 対象は `const CURRENT_TOOL = "<id>"` を持つ index.html
- 書く中身（head.js と同じ決め方）
    - ツールの本体ページ: タイトルは「seoTitle（無ければ title） | ToolDock」、説明は seoDesc（無ければ desc）
    - canonical がツールのURLと違うページ（選手ページ・年ごとのページなど）と、一覧などの隠しツール:
      そのページの <title> と description
    - 画像: /ogp/<id>.png（一覧などの隠しツールはサイト共通の /ogp.png）
- 書き込んだ部分は印で囲み、次からはそこだけ書き換える。印の無い og:image を
  手で書いたページ（能力画像ジェネレーターなど）はそのままにする
- 中身が変わらないファイルは書き換えない（毎日の更新で差分を出さない）

    python3 scripts/static_ogp.py                 # サイト全体
    python3 scripts/static_ogp.py player draft    # このフォルダの下だけ
"""

import html
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE = "https://tooldock.github.io"
SITE_NAME = "ToolDock"
BEGIN = "<!-- OGP: scripts/static_ogp.py が書く（SNSはJavaScriptを動かさないため）。手で書き換えない -->"
END = "<!-- /OGP -->"
BLOCK_RE = re.compile(re.escape(BEGIN) + r".*?" + re.escape(END) + r"\n?", re.S)
SKIP_DIRS = {".git", "node_modules", "scripts", "npb", "market"}


def js_string(m):
    return m.group(1).replace('\\"', '"').replace("\\\\", "\\") if m else None


def parse_tools():
    js = (ROOT / "js" / "tool-data.js").read_text(encoding="utf-8")
    body = js[js.index("window.TOOLS"):]
    tools = {}
    for block in re.findall(r"\{[^{}]*?id:\s*\"[^\"]+\"[\s\S]*?\n  \}", body):
        get = lambda k: js_string(re.search(r"\b" + k + r':\s*"((?:[^"\\]|\\.)*)"', block))
        tid = get("id")
        tools[tid] = {
            "title": get("seoTitle") or get("title"),
            "desc": get("seoDesc") or get("desc"),
            "url": get("url"),
            "hidden": bool(re.search(r"hidden:\s*true", block)),
        }
    return tools


def attr(s):
    return html.escape(html.unescape(s), quote=True)


def build_block(page, tool, tid):
    canon = re.search(r'<link rel="canonical" href="([^"]+)"', page)
    title = re.search(r"<title>(.*?)</title>", page, re.S)
    desc = re.search(r'<meta name="description" content="([^"]*)"', page)
    tool_url = SITE + tool["url"]
    url = canon.group(1) if canon else tool_url
    sub = url != tool_url or tool["hidden"]  # 一覧などの隠しツールも、ページ自身の文言を使う
    og_title = title.group(1).strip() if sub and title else f"{tool['title']} | {SITE_NAME}"
    og_desc = desc.group(1) if sub and desc else tool["desc"]
    image = f"{SITE}/ogp.png" if tool["hidden"] else f"{SITE}/ogp/{tid}.png"
    return "\n".join([
        BEGIN,
        '<meta property="og:type" content="website">',
        f'<meta property="og:site_name" content="{SITE_NAME}">',
        f'<meta property="og:title" content="{attr(og_title)}">',
        f'<meta property="og:description" content="{attr(og_desc)}">',
        f'<meta property="og:url" content="{attr(url)}">',
        f'<meta property="og:image" content="{image}">',
        '<meta property="og:image:width" content="1200">',
        '<meta property="og:image:height" content="630">',
        '<meta property="og:locale" content="ja_JP">',
        '<meta name="twitter:card" content="summary_large_image">',
        END,
    ]) + "\n"


def process(path, tools):
    page = path.read_text(encoding="utf-8")
    m = re.search(r'const CURRENT_TOOL = "([^"]+)"', page)
    if not m or m.group(1) not in tools:
        return None
    tid = m.group(1)
    rest = BLOCK_RE.sub("", page)
    if 'property="og:image"' in rest:
        return None  # 手で書いたOGPがある
    block = build_block(rest, tools[tid], tid)
    # head.js より前に置く（head.js が og:image の有無を見るため）
    at = rest.rindex("<script", 0, rest.index("const CURRENT_TOOL"))
    at = rest.rindex("\n", 0, at) + 1
    new = rest[:at] + block + rest[at:]
    if new == page:
        return False
    path.write_text(new, encoding="utf-8")
    return True


def main(argv):
    tools = parse_tools()
    roots = [ROOT / a for a in argv] or [ROOT]
    changed = same = 0
    for root in roots:
        for path in sorted(root.rglob("index.html")):
            if SKIP_DIRS & set(path.relative_to(ROOT).parts):
                continue
            r = process(path, tools)
            if r is True:
                changed += 1
            elif r is False:
                same += 1
    print(f"OGP: {changed}ページを書き換え、{same}ページは変化なし")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
