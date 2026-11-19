#!/usr/bin/env python3
"""埼玉・千葉の内申点ツールに、学校ごとのデータ（scripts/naishin/*.json）を書き込む。

  python3 scripts/build_naishin.py

ページの中の「/*DATA*/ … /*/DATA*/」の間を置き換える。
データの出典：
  埼玉 … 県教育委員会「令和9年度埼玉県公立高等学校入学者選抜における各高等学校の選抜実施内容（確定版）」の概要一覧
  千葉 … 県教育委員会「令和9年度千葉県公立高等学校入学者選抜実施要項」付表2（K の値）・付表4（傾斜の倍率）
"""
import json, re, pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent


def saitama():
    rows = json.loads((ROOT / "scripts/naishin/saitama.json").read_text(encoding="utf-8"))
    out = []
    for r in rows:
        st = [["".join(map(str, s["r"])), s["gk"], "".join(k + str(v) for k, v in s["kei"].items()), s["ch"], s["m"], s["t"]] for s in r["st"]]
        out.append([r["s"], r["c"], r["g"], r["typ"], r["p"][0], r["p"][1], r["sel"], r["how"], r["own"], r["ex"], st[0], st[1]])
    return out


def chiba():
    rows = json.loads((ROOT / "scripts/naishin/chiba.json").read_text(encoding="utf-8"))
    return [[r["no"], r["s"], r["g"], r["K"], r["test"], "".join(k for k in r["mul"]), r["riyu"] == "有"] for r in rows]


def write(path, data):
    p = ROOT / path
    s = p.read_text(encoding="utf-8")
    js = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    s2, n = re.subn(r"/\*DATA\*/.*?/\*/DATA\*/", lambda m: "/*DATA*/" + js + "/*/DATA*/", s, flags=re.S)
    assert n == 1, path
    p.write_text(s2, encoding="utf-8")
    print(path, len(data), "rows")


if __name__ == "__main__":
    write("naishin/saitama/index.html", saitama())
    write("naishin/chiba/index.html", chiba())
