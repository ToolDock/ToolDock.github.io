#!/usr/bin/env python3
"""「同じカテゴリのツール」の欄を、各ページのHTMLに直接書き込む。

これまでは js/related.js がページを開いたあとに作っていたので、Googleが最初に読む
HTMLにはリンクが無かった（JavaScriptを動かす2回目の読み込みは、後回しにされやすい）。
related.js と同じ中身（同じカテゴリの、隠していないツール。js/tool-data.js の順）を
`<div id="related-tools">` の中に焼き込む。related.js は、中身がすでにあれば何もしない。

- 書き込んだ部分は印で囲み、次からはそこだけ書き換える
- 中身が変わらないファイルは書き換えない
- ツールを足したり、名前・説明を変えたりしたら実行する

    python3 scripts/static_related.py
"""

import html
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BEGIN = "<!-- RELATED: scripts/static_related.py が書く。手で書き換えない -->"
END = "<!-- /RELATED -->"
CONTAINER_RE = re.compile(r'(<div id="related-tools">)(.*?)(</div>\s*<script src="/js/related\.js">)', re.S)
SKIP_DIRS = {".git", "node_modules", "scripts", "npb", "market"}


def js_string(m):
    return m.group(1).replace('\\"', '"').replace("\\\\", "\\") if m else None


def parse_tools():
    js = (ROOT / "js" / "tool-data.js").read_text(encoding="utf-8")
    body = js[js.index("window.TOOLS"):]
    tools = []
    for block in re.findall(r"\{[^{}]*?id:\s*\"[^\"]+\"[\s\S]*?\n  \}", body):
        get = lambda k: js_string(re.search(r"\b" + k + r':\s*"((?:[^"\\]|\\.)*)"', block))
        tools.append({
            "id": get("id"), "title": get("title"), "desc": get("desc"),
            "url": get("url"), "category": get("category"),
            "hidden": bool(re.search(r"hidden:\s*true", block)),
        })
    return tools


def render(current, tools):
    related = [t for t in tools if not t["hidden"] and t["category"] == current["category"] and t["id"] != current["id"]]
    if not related:
        return ""
    cards = "\n".join(
        f'<a href="{html.escape(t["url"])}" class="related-tool-card"><h3>{html.escape(t["title"])}</h3>'
        f'<p>{html.escape(t["desc"])}</p></a>'
        for t in related)
    return (f'{BEGIN}\n<section class="related-tools-section">\n<h2>同じカテゴリのツール</h2>\n'
            f'<div class="related-tools-grid">\n{cards}\n</div>\n</section>\n{END}')


def main(argv):
    tools = parse_tools()
    by_id = {t["id"]: t for t in tools}
    changed = same = 0
    for path in sorted(ROOT.rglob("index.html")):
        if SKIP_DIRS & set(path.relative_to(ROOT).parts):
            continue
        page = path.read_text(encoding="utf-8")
        m = re.search(r'const CURRENT_TOOL = "([^"]+)"', page)
        if not m or m.group(1) not in by_id or not CONTAINER_RE.search(page):
            continue
        block = render(by_id[m.group(1)], tools)
        new = CONTAINER_RE.sub(lambda c: c.group(1) + block + c.group(3), page, count=1)
        if new == page:
            same += 1
            continue
        path.write_text(new, encoding="utf-8")
        changed += 1
    print(f"関連ツール: {changed}ページを書き換え、{same}ページは変化なし")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
