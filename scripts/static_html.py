#!/usr/bin/env python3
"""JavaScriptで作っている部品のうち、SNSとGoogleに読ませたいものを、各ページのHTMLに書き込む。

SNS（X・LINEなど）はJavaScriptを動かさずにページを読み、Googleも最初はHTMLだけを読む
（JavaScriptを動かす2回目の読み込みは後回しにされやすい）。そこで次の3つを焼き込む。

- OGP（SNSの共有カード）            … scripts/static_ogp.py（head.js と同じ中身）
- パンくずリストと、その構造化データ … このファイル（head.js と同じ中身）
- 「同じカテゴリのツール」の欄      … scripts/static_related.py（related.js と同じ中身）

head.js・related.js は、HTMLにすでにあれば作らない。どれも印で囲み、次からはそこだけ
書き換える。中身が変わらないファイルは書き換えない（毎日の更新で差分を出さない）。

ツールを足したり、名前・説明を変えたりしたら実行する。毎日の自動更新でも、作り直した
ページに書き足すために実行している。

    python3 scripts/static_html.py
"""

import html
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import static_ogp  # noqa: E402
import static_related  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SITE = "https://tooldock.github.io"
SITE_NAME = "ToolDock"
BEGIN = "<!-- BREADCRUMB: scripts/static_html.py が書く。手で書き換えない -->"
END = "<!-- /BREADCRUMB -->"
BLOCK_RE = re.compile(re.escape(BEGIN) + r".*?" + re.escape(END) + r"\n?", re.S)
SKIP_DIRS = {".git", "node_modules", "scripts", "npb", "market"}


def category_names():
    js = (ROOT / "js" / "tool-data.js").read_text(encoding="utf-8")
    body = re.search(r"window\.CATEGORY_NAMES\s*=\s*\{(.*?)\};", js, re.S).group(1)
    return dict(re.findall(r"(\w+)\s*:\s*\"([^\"]+)\"", body))


def breadcrumb(page, tool, tid, cats):
    """head.js のパンくず（カテゴリの無い隠しツールでは出さない）"""
    extra = re.search(r'const BREADCRUMB_EXTRA = \{\s*name:\s*"([^"]*)",\s*url:\s*"([^"]*)"', page)
    label = cats.get(tool["category"], tool["category"])
    cat_url = "/category/?cat=" + tool["category"]
    e = html.escape
    sep = '<span class="bc-sep">›</span>'  # 前後の空白も head.js と同じ（区切りの間隔がそろう）
    links = [f'<a href="/">{SITE_NAME}</a>', f'<a href="{e(cat_url)}">{e(label)}</a>']
    items = [(SITE_NAME, SITE + "/"), (label, SITE + cat_url), (tool["title"], SITE + tool["url"])]
    if extra:
        links += [f'<a href="{e(tool["url"])}">{e(tool["title"])}</a>', f"<span>{e(extra.group(1))}</span>"]
        items.append((extra.group(1), SITE + extra.group(2)))
    else:
        links.append(f'<span>{e(tool["title"])}</span>')
    ld = {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [{"@type": "ListItem", "position": i + 1, "name": n, "item": u}
                            for i, (n, u) in enumerate(items)],
    }
    nav = (" " + sep + " ").join(links)
    return (f"{BEGIN}\n"
            f'<nav class="breadcrumb" aria-label="パンくずリスト">{nav}</nav>\n'
            f'<script type="application/ld+json">{json.dumps(ld, ensure_ascii=False)}</script>\n'
            f"{END}\n")


def write_breadcrumbs():
    tools = static_ogp.parse_tools()
    tools_full = {t["id"]: t for t in static_related.parse_tools()}
    cats = category_names()
    changed = same = 0
    for path in sorted(ROOT.rglob("index.html")):
        if SKIP_DIRS & set(path.relative_to(ROOT).parts):
            continue
        page = path.read_text(encoding="utf-8")
        m = re.search(r'const CURRENT_TOOL = "([^"]+)"', page)
        if not m or m.group(1) not in tools or tools[m.group(1)]["hidden"]:
            continue
        tid = m.group(1)
        tool = dict(tools_full[tid])
        rest = BLOCK_RE.sub("", page)
        body = re.search(r"<body[^>]*>\n?", rest)
        new = rest[:body.end()] + breadcrumb(rest, tool, tid, cats) + rest[body.end():]
        if new == page:
            same += 1
            continue
        path.write_text(new, encoding="utf-8")
        changed += 1
    print(f"パンくず: {changed}ページを書き換え、{same}ページは変化なし")


def main(argv):
    static_ogp.main(argv)
    write_breadcrumbs()
    static_related.main([])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
