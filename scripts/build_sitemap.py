#!/usr/bin/env python3
"""サイトマップ（sitemap.xml）を作る。

各ページの index.html に書いてある <link rel="canonical"> を集めて並べるだけ。
ツールを足したときも、ドラフト答え合わせの年別ページ（/draft/2025/ など）が
増えたときも、ここを直さずにそのまま載る。

- noindex のページは載せない
- 同じ canonical を指すページ（market/web → /us-market/）は1つにまとめる
- lastmod は、ページの中身が変わった日（日本時間）。CIの取り出しではファイルの日時が当てに
  ならないので、ページごとの中身のハッシュと日付を sitemap-lastmod.json に持っておき、
  ハッシュが変わったときだけ日付を今日にする。「最終更新」の時刻だけの違いは数えない
- 同じ中身のテキスト形式 sitemap.txt も書く

    python3 scripts/build_sitemap.py
    python3 scripts/build_sitemap.py --check   # ずれていたら終了コード1
"""

import hashlib
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "sitemap.xml"
TXT = ROOT / "sitemap.txt"
STATE = ROOT / "sitemap-lastmod.json"
JST = timezone(timedelta(hours=9))
SITE = "https://tooldock.github.io"
SKIP_DIRS = {".git", ".github", "node_modules", "npb", "scripts", "_probe"}


def pages(files=None):
    return sorted(files or page_files(), key=lambda u: (u != SITE + "/", u.rstrip("/").count("/"), u))


def page_files():
    """URL → そのURLを canonical に持つ index.html（同じURLが複数あれば、URLと同じ場所のもの）"""
    files = {}
    for f in ROOT.rglob("index.html"):
        if SKIP_DIRS & set(f.relative_to(ROOT).parts):
            continue
        head = f.read_text(encoding="utf-8", errors="replace")
        if re.search(r'<meta[^>]+name="robots"[^>]+noindex', head, re.I):
            continue
        m = re.search(r'<link rel="canonical" href="([^"]+)"', head)
        if m and m.group(1).startswith(SITE + "/"):
            url = m.group(1)
            rel = f.parent.relative_to(ROOT).as_posix()
            own = SITE + "/" + ("" if rel == "." else rel + "/")
            if url not in files or own == url:
                files[url] = f
    # 並びは pages() で、トップ → 浅い階層 → 名前順（/draft/ の直後に /draft/2005/ 〜 が並ぶ）
    return files


def content_hash(path):
    """「最終更新」の時刻だけが変わった日は、中身が変わったと数えない"""
    text = path.read_text(encoding="utf-8", errors="replace")
    text = "\n".join(line for line in text.split("\n") if "最終更新" not in line)
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:16]


def lastmods(files):
    """URL → [中身が変わった日, ハッシュ]。前回からハッシュが変わったページだけ今日の日付にする"""
    state = json.loads(STATE.read_text(encoding="utf-8")) if STATE.exists() else {}
    today = datetime.now(JST).strftime("%Y-%m-%d")
    out = {}
    for url, path in files.items():
        h = content_hash(path)
        old = state.get(url)
        out[url] = [old[0], h] if old and old[1] == h else [today, h]
    return out


def render_state(mods, urls):
    # 1行に1ページ（差分が読みやすいように）
    return "{\n" + ",\n".join(f"{json.dumps(u)}: {json.dumps(mods[u])}" for u in urls) + "\n}\n"


def render(urls, mods):
    rows = "\n".join(f"  <url><loc>{escape(u)}</loc><lastmod>{mods[u][0]}</lastmod></url>" for u in urls)
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
            f"{rows}\n</urlset>\n")


def main(argv):
    files = page_files()
    urls = pages(files)
    mods = lastmods(files)
    xml = render(urls, mods)
    if "--check" in argv:
        old = OUT.read_text(encoding="utf-8") if OUT.exists() else ""
        old_txt = TXT.read_text(encoding="utf-8") if TXT.exists() else ""
        if old != xml or old_txt != "\n".join(urls) + "\n":
            print("sitemap.xml が古い。python3 scripts/build_sitemap.py を実行すること", file=sys.stderr)
            return 1
        print(f"サイトマップは最新（{len(urls)}件）")
        return 0
    OUT.write_text(xml, encoding="utf-8")
    STATE.write_text(render_state(mods, urls), encoding="utf-8")
    # 同じ中身のテキスト形式（1行に1つのURL）。Googleが正式に対応している形式で、
    # Search ConsoleでXMLの送信が「取得できませんでした」になるときの代わりに送れる
    TXT.write_text("\n".join(urls) + "\n", encoding="utf-8")
    print(f"sitemap.xml・sitemap.txt に {len(urls)}件を書き込み")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
