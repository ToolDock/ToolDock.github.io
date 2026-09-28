#!/usr/bin/env python3
"""サイトマップ（sitemap.xml）を作る。

各ページの index.html に書いてある <link rel="canonical"> を集めて並べるだけ。
ツールを足したときも、ドラフト答え合わせの年別ページ（/draft/2025/ など）が
増えたときも、ここを直さずにそのまま載る。

- noindex のページは載せない
- 同じ canonical を指すページ（market/web → /us-market/）は1つにまとめる
- lastmod は付けない（CIの取り出しではファイルの日時が当てにならないため）

    python3 scripts/build_sitemap.py
    python3 scripts/build_sitemap.py --check   # ずれていたら終了コード1
"""

import re
import sys
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "sitemap.xml"
SITE = "https://tooldock.github.io"
SKIP_DIRS = {".git", ".github", "node_modules", "npb", "scripts", "_probe"}


def pages():
    urls = set()
    for f in ROOT.rglob("index.html"):
        if SKIP_DIRS & set(f.relative_to(ROOT).parts):
            continue
        head = f.read_text(encoding="utf-8", errors="replace")
        if re.search(r'<meta[^>]+name="robots"[^>]+noindex', head, re.I):
            continue
        m = re.search(r'<link rel="canonical" href="([^"]+)"', head)
        if m and m.group(1).startswith(SITE + "/"):
            urls.add(m.group(1))
    # トップ → 浅い階層 → 名前順（/draft/ の直後に /draft/2005/ 〜 が並ぶ）
    return sorted(urls, key=lambda u: (u != SITE + "/", u.rstrip("/").count("/"), u))


def render(urls):
    rows = "\n".join(f"  <url><loc>{escape(u)}</loc></url>" for u in urls)
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
            f"{rows}\n</urlset>\n")


def main(argv):
    urls = pages()
    xml = render(urls)
    if "--check" in argv:
        old = OUT.read_text(encoding="utf-8") if OUT.exists() else ""
        if old != xml:
            print("sitemap.xml が古い。python3 scripts/build_sitemap.py を実行すること", file=sys.stderr)
            return 1
        print(f"サイトマップは最新（{len(urls)}件）")
        return 0
    OUT.write_text(xml, encoding="utf-8")
    print(f"sitemap.xml に {len(urls)}件を書き込み")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
