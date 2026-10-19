#!/usr/bin/env python3
"""IndexNow で、変わったページのURLを検索エンジン（Bing など）に知らせる。

Bing・Yandex・Naver などが対応している（Google は対応していない）。
api.indexnow.org に送れば、対応している検索エンジンすべてに伝わる。

- 鍵はサイトの直下の <鍵>.txt に置いてある（中身は鍵そのもの）。検索エンジンはこれを見て、
  送ってきたのがサイトの持ち主だと確かめる
- 送るのはサイトマップに載っているURLだけ（noindex のページ・JSON などは送らない）
- 1回に送れるのは1万件まで。それより多いときは分けて送る

    python3 scripts/indexnow.py --range <前のコミット>..<後のコミット>   # その間に変わったページ
    python3 scripts/indexnow.py --all                                   # サイトマップの全部
    python3 scripts/indexnow.py --range A..B --dry-run                  # 送らずに一覧だけ出す
"""

import argparse
import json
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE = "https://tooldock.github.io"
HOST = "tooldock.github.io"
ENDPOINT = "https://api.indexnow.org/indexnow"
BATCH = 10000


def key():
    files = [p for p in ROOT.glob("*.txt") if len(p.stem) == 32 and p.read_text().strip() == p.stem]
    if len(files) != 1:
        sys.exit("IndexNow の鍵のファイル（<32文字の鍵>.txt）がサイトの直下に1つだけ必要")
    return files[0].stem


def sitemap_urls():
    return [u for u in (ROOT / "sitemap.txt").read_text(encoding="utf-8").split() if u]


def changed_urls(rev_range):
    """その間に変わった（増えた）index.html を、サイトマップのURLに直す"""
    out = subprocess.run(["git", "diff", "--name-only", "--diff-filter=AM", rev_range],
                         cwd=ROOT, check=True, capture_output=True, text=True).stdout.split("\n")
    known = set(sitemap_urls())
    urls = []
    for f in out:
        if f != "index.html" and not f.endswith("/index.html"):
            continue
        url = SITE + "/" + f[: -len("index.html")]
        if url in known:
            urls.append(url)
    return sorted(set(urls))


def send(urls, k):
    for i in range(0, len(urls), BATCH):
        body = json.dumps({
            "host": HOST,
            "key": k,
            "keyLocation": f"{SITE}/{k}.txt",
            "urlList": urls[i:i + BATCH],
        }).encode("utf-8")
        req = urllib.request.Request(ENDPOINT, data=body, method="POST",
                                     headers={"Content-Type": "application/json; charset=utf-8"})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                print(f"IndexNow: {len(urls[i:i + BATCH])}件を送信（{r.status}）")
        except urllib.error.HTTPError as e:
            # 400 形式の誤り / 403 鍵が確かめられない / 422 サイトと合わないURL / 429 送りすぎ
            print(f"IndexNow: 送信に失敗（{e.code}） {e.read()[:300]!r}", file=sys.stderr)
            return 1
    return 0


def main(argv):
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--range", help="git の範囲（例 abc123..def456）")
    g.add_argument("--all", action="store_true", help="サイトマップのURLを全部送る")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)

    k = key()
    urls = sitemap_urls() if a.all else changed_urls(a.range)
    if not urls:
        print("IndexNow: 変わったページなし")
        return 0
    for u in urls[:20]:
        print(" ", u)
    if len(urls) > 20:
        print(f"  …ほか{len(urls) - 20}件")
    if a.dry_run:
        return 0
    return send(urls, k)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
