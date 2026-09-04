"""GitHub Pages 用の静的ダッシュボードを書き出す。

Streamlit はPythonのサーバーが要るのでGitHub Pagesでは動かない。
そこで、DBの内容を market.json に固めて、素のHTML/CSS/JSから読ませる。
チャートの描画はブラウザ側（board.js + Chart.js）が行う。
ここが書き出すのは数値と系列だけで、図そのものは持たない。

    python build_static.py                        # dist/ に書き出し
    python build_static.py --refresh              # 先にデータを取得してから書き出し
    python build_static.py --out docs/us-market   # 出力先を変える

GitHub Actions 向け:

    python build_static.py --refresh --strict --out docs/us-market

--strict はデータが欠けていたら書き出さずに終了する（公開中のページを壊さないため）。
DBは持ち回らなくてよい。毎回、日足を5年ぶん取り直している。

出力:
    dist/index.html   ページの骨組み（web/index.html のコピー）
    dist/board.css    見た目（web/board.css のコピー）
    dist/board.js     market.json を読んで描画（web/board.js のコピー）
    dist/market.json  数値と系列（このスクリプトが生成）
"""

import argparse
import json
import shutil
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

import collect_us_market as collector
from utils import us_market as um

ROOT = Path(__file__).resolve().parent
WEB_DIR = ROOT / "web"
STATIC_FILES = ["index.html", "board.css", "board.js"]

SOURCES = [
    "指数・為替・金利・コモディティ・BTC・個別銘柄: Yahoo Finance",
    "Fear & Greed: CNN Business",
    "円建てS&P500: 上記のS&P500とドル円から当方で計算",
]
DISCLAIMER = ("本ページは市況の把握を目的とした情報提供であり、"
              "特定の銘柄・商品の売買を勧めるものではありません。")


def slug(symbol):
    """^GSPC → gspc、JPY=X → jpy-x。HTMLのidに使う。"""
    return "".join(c if c.isalnum() else "-" for c in symbol.lower()).strip("-")


# ── 各パートのデータ ──────────────────────────────────────────
# タイルの期間切り替えに渡す日足の長さ（日数）。
# 本数で切ると、毎日動くBTCだけ1年に届かない（週5日の市場と本数が違う）。
# 400日あれば、1年ぶんと、年初来の起点になる前年末の終値が必ず入る
DAILY_WINDOW_DAYS = 400


def _round(value, digits):
    """表示桁で丸める。JSONを無駄に長くしないため。"""
    return round(value, digits) if digits else round(value)


def weekly_closes(rows):
    """各週の最終営業日の終値だけを残す。

    5年ぶんを日足のまま渡すと market.json が3倍近くに膨らむが、
    小さな図では点が潰れて日足と週足の区別がつかない。
    """
    last = {}
    for day, close in rows:
        year, week, _ = date.fromisoformat(day).isocalendar()
        last[(year, week)] = (day, close)
    return [last[key] for key in sorted(last)]


def history_payload(symbol, digits, session=None, close=None):
    """期間切り替え用の系列。直近1年は日足、5年は週足。

    1ヶ月・年初来・1年は daily を切って使う。
    年初来の起点には前年末の終値が要るので、daily は1年ぶん持たせてある。

    末尾は日足をそのまま使わず、基準日より前で打ち切って、
    基準日ぶんはタイルの値で置き直す。Yahooの日足は当日ぶんの扱いが
    銘柄によって違うため。実際に返ってきたもの（2026-09-04 07:34 UTC 時点、
    基準日は9/3）:

      ^GSPC   … 9/2 まで。9/3 の足がまだ無い
      JPY=X   … 9/4 まで。取得した瞬間の、まだ途中の値が入っている
      GC=F    … 9/2 の次が 9/4。9/3 が飛んでいる

    このまま渡すと、図の右端がタイルの数字と合わない。
    タイルの値（5分足から取った基準日の終値）に合わせておけば、
    どの銘柄でも右端が必ず一致する。
    """
    rows = um.load_daily(symbol, days=None)
    if len(rows) < 30:
        return None, None

    if session and close is not None:
        rows = [r for r in rows if r[0] < session] + [(session, close)]

    first = date.fromisoformat(rows[-1][0]) - timedelta(days=DAILY_WINDOW_DAYS)
    year = [r for r in rows if date.fromisoformat(r[0]) >= first]
    week = weekly_closes(rows)
    return (
        {"dates": [d for d, _ in year], "values": [_round(v, digits) for _, v in year]},
        {"dates": [d for d, _ in week], "values": [_round(v, digits) for _, v in week]},
    )


def tile_payload(tile):
    change_text, sign = um.format_change(tile)
    daily, weekly = history_payload(tile["symbol"], tile["digits"],
                                    tile["session"], tile["price"])
    return {
        "symbol": tile["symbol"],
        "slug": slug(tile["symbol"]),
        "label": tile["label"],
        "session": tile["session"],
        "price": tile["price"],
        "price_text": um.format_price(tile),
        "prev_close": tile["prev_close"],
        "change": tile["change"],
        "change_pct": tile["change_pct"],
        "change_bp": tile["change_bp"],
        "change_mode": tile["change_mode"],
        "change_text": change_text,
        "direction": sign,
        "arrow": "▲" if sign > 0 else ("▼" if sign < 0 else "―"),

        # 日中足そのもの。描画はブラウザ側（Chart.js）で行う。
        # 時刻は "HH:MM" だけあれば足りる（日付はタイルの session が持っている）
        "digits": tile["digits"],
        "times": [str(t)[11:16] for t in tile["times"]],
        "values": tile["values"],

        # 期間切り替え用。1ヶ月・年初来・1年は daily を、5年は weekly を切って使う。
        # 取れていなければ null で、その期間のボタンはブラウザ側が引っ込める
        "daily": daily,
        "weekly": weekly,
    }


def yenspx_payload(stats, parts, source):
    """円建てS&P500の年初来。

    値そのもの（S&P500 × ドル円）に意味は無いので、率で見せる。
    図は年初＝100 に正規化して渡す。
    """
    ytd = round(stats["ytd_pct"], 2)
    return {
        "title": "円建てS&P500（参考値）",
        "year": stats["year"],
        "source": source,
        "dividends": source == um.SPX_TOTAL_RETURN,
        "date": stats["date"].isoformat(),
        "date_text": f"{stats['date'].year}年{stats['date'].month}月{stats['date'].day}日",
        "ytd_pct": ytd,
        "ytd_text": f"{ytd:+.2f}%",

        # 前日比はここでは出さない。日足のドル円は取引時間の区切りが
        # タイルと1日ずれることがあり、出すと上の
        # 「S&P500 +1.06%」「ドル円 -1.68%」と突き合わない数字になる。
        # 日々の増減は上のタイルが持っているので、ここは年単位の話に絞る
        "start_date": stats["start_date"].isoformat(),
        "start_date_text": f"{stats['start_date'].month}月{stats['start_date'].day}日",
        "from_peak_pct": round(stats["from_peak_pct"], 2),
        "from_peak_text": f"{stats['from_peak_pct']:+.2f}%",

        # 円建ての騰落は (1+株) × (1+為替) - 1 にきれいに分かれる。
        # 「上がったのは株か円安か」を1行で見せる
        "parts": None if not parts else {
            "stock_pct": round(parts["stock_pct"], 2),
            "fx_pct": round(parts["fx_pct"], 2),
            # 「米国株 +12.97%」で1かたまり。狭いときは
            # かたまりの境目で折り返してほしいので、分けて渡す
            "stock_text": f"米国株 {parts['stock_pct']:+.2f}%",
            "fx_text": f"為替 {parts['fx_pct']:+.2f}%",
        },

        "note": ("S&P500" + ("（配当込み）" if source == um.SPX_TOTAL_RETURN else "")
                 + "とドル円を掛け合わせた参考値です。"
                 "実際の投資信託の基準価額ではなく、信託報酬や、"
                 "株価と為替を反映する時刻の違いのぶんだけずれます。"
                 "eMAXIS Slim 米国株式（S&P500）の実績403日ぶんと突き合わせたところ、"
                 "ずれはおおむね1%台に収まっていました。"),
    }


def monthly_payload(symbol="^GSPC", months=13):
    """S&P500の月ごとの騰落。各月の最終営業日の終値どうしを比べる。

    日々の値動きだと荒く見えても、月単位だと様子が違うことがある。
    直近の月は途中なので、その旨を持たせる。
    """
    daily = um.load_daily(symbol, days=None)
    if len(daily) < 40:
        return None

    # 月ごとの最終営業日
    last = {}
    for day, close in daily:
        last[day[:7]] = (day, close)

    keys = sorted(last)[-months:]
    rows = []
    for i in range(1, len(keys)):
        day, close = last[keys[i]]
        prev_close = last[keys[i - 1]][1]
        diff = close - prev_close
        pct = diff / prev_close * 100
        year, month = keys[i].split("-")
        rows.append({
            "key": keys[i],
            "label": f"{int(month)}月",
            "year": int(year),
            "date": day,
            "close": round(close, 2),
            "close_text": f"{close:,.2f}",
            "diff": round(diff, 2),
            "diff_text": f"{diff:+,.2f}pt",
            "pct": round(pct, 2),
            "pct_text": f"{pct:+.2f}%",
            "direction": 1 if diff > 0 else (-1 if diff < 0 else 0),
        })

    rows.reverse()                      # 新しい月を上に

    # いちばん上の月が「まだ途中」かどうか。
    # 最新の日付より後に、その月の平日がまだ残っていれば途中とみなす。
    # 単に「最新データがその月にある」で判定すると、
    # 月末営業日まで来ていても途中扱いになってしまう
    if rows:
        latest = date.fromisoformat(daily[-1][0])
        day = latest + timedelta(days=1)
        remaining = 0
        while day.month == latest.month:
            if day.weekday() < 5:
                remaining += 1
            day += timedelta(days=1)
        rows[0]["partial"] = rows[0]["key"] == daily[-1][0][:7] and remaining > 0

    up = sum(1 for r in rows if r["direction"] > 0)
    return {
        "title": "S&P500の月ごとの騰落",
        "note": ("各月の最終営業日の終値どうしを比べたもの。"
                 "日々の値動きだけを見ていると荒く感じても、"
                 "月単位でならしてみると印象が変わることがあります。"
                 "いちばん上の月は、まだ途中の場合があります。"),
        "summary": f"直近{len(rows)}か月のうち {up}か月が上昇、{len(rows) - up}か月が下落",
        "up": up,
        "down": len(rows) - up,
        "rows": rows,
    }


def heatmap_payload():
    """S&P500の主要銘柄を、セクターごとにまとめて返す。

    タイルの面積はウェイト、色は前日比。
    取得できていないときは None を返す（その節ごと出さない）。
    """
    rows = um.load_heatmap()
    if not rows:
        return None

    sectors = {}
    for row in rows:
        sectors.setdefault(row["sector"], []).append(row)

    out = []
    for name, items in sectors.items():
        items.sort(key=lambda x: -x["weight"])
        out.append({
            "name": name,
            "weight": round(sum(x["weight"] for x in items), 3),
            "items": [{
                "symbol": x["symbol"],
                "name": x["name"],
                "name_ja": x.get("name_ja") or "",
                "weight": x["weight"],
                "change_pct": x["change_pct"],
                "change_text": f"{x['change_pct']:+.2f}%",
            } for x in items],
        })
    out.sort(key=lambda s: -s["weight"])

    changes = [x["change_pct"] for x in rows]
    up = sum(1 for c in changes if c > 0)
    down = sum(1 for c in changes if c < 0)
    return {
        "title": "S&P500 主要銘柄のヒートマップ",
        "note": ("面積は時価総額のおおよその比率、色はその日の騰落率。"
                 "緑が上げ、赤が下げ。S&P500の主要86銘柄を、セクターごとにまとめています。"),
        "session": rows[0]["session"],
        "count": len(rows),
        "up": up,
        "down": down,
        "sectors": out,
    }


def drawdown_payload(series, years):
    out = {}
    for year in years:
        dd = um.drawdown_series(series, year)
        if not dd:
            continue
        worst, worst_day = um.max_drawdown(dd)
        out[str(year)] = {
            "dates": [d.isoformat() for d, _ in dd],
            "values": [round(v, 3) for _, v in dd],
            "max": round(worst, 2),
            "max_date": worst_day.isoformat(),
        }
    return out


def sentiment_payload(fg, vix):
    fg_out = None
    if fg:
        fg_out = {
            "value": fg["value"],
            "value_text": f"{fg['value']:.0f}",
            "label_en": fg["label_en"],
            "label_ja": fg["label_ja"],
            "color": fg["color"],
            "date": fg["date"].isoformat(),
            "history": [
                {"label": "前営業日", "value": fg["prev"]},
                {"label": "1週間前", "value": fg["week_ago"]},
                {"label": "1ヶ月前", "value": fg["month_ago"]},
            ],
            "note": (f"出典: CNN Business Fear & Greed Index（{fg['date']}）"
                     f"　0=極度の恐怖／100=極度の強欲"),
        }

    vix_out = None
    if vix:
        change_text, sign = um.format_change(vix)
        vix_out = {
            "value": vix["price"],
            "value_text": f"{vix['price']:,.2f}",
            "change_text": change_text,
            "direction": sign,
            "session": vix["session"],
            "band_label": vix["band_label"],
            "band_color": vix["band_color"],
            "note": (f"S&P500オプションが織り込む今後30日の予想変動率（年率%）。"
                     f"{vix['session']} のセッション　20超で警戒、30超で極度の警戒。"),
        }
    return fg_out, vix_out


# ── 組み立て ────────────────────────────────────────────────
def build_payload(today=None):
    today = today or date.today()
    this_year, last_year = today.year, today.year - 1

    # 円建てS&P500。去年ぶんもドローダウンの比較用に要る
    series, spx_source = um.yen_spx_series(date(last_year, 1, 1))
    stats = um.ytd_stats(series, this_year)
    fg = um.load_fear_greed()

    # ページ全体を米国株の最終セッションにそろえる。
    # そうしないと、24時間動いているドル円とBTCだけが「今この瞬間」の値になり、
    # 米国株の終値と日付が食い違う
    ref = um.reference_session()

    vix = um.load_vix(ref)
    fg_out, vix_out = sentiment_payload(fg, vix)

    rows = []
    for title, symbols in (("主要指数・為替", um.ROW1),
                           ("コモディティ・金利・暗号資産・半導体", um.ROW2)):
        tiles = [tile_payload(tile) for tile in um.load_tiles(symbols, ref)]
        rows.append({"title": title, "tiles": tiles})

    # VIX と S&P500 の1年チャート。日付をそろえて2本重ねる
    vix_daily = dict(um.load_daily("^VIX"))
    spx_daily = dict(um.load_daily("^GSPC"))
    shared = sorted(set(vix_daily) & set(spx_daily))
    vix_chart = {
        "dates": shared,
        "vix": [vix_daily[d] for d in shared],
        "sp500": [spx_daily[d] for d in shared],
    } if len(shared) >= 30 else None

    # Fear & Greed の1年チャート
    fg_hist = um.load_fg_history()
    fg_chart = {
        "dates": [d for d, _ in fg_hist],
        "values": [v for _, v in fg_hist],
    } if len(fg_hist) >= 30 else None

    # 円建てS&P500の年初来。値そのもの（S&P500 × ドル円）に意味は無いので、
    # 年初からの騰落率にして渡す
    yenspx_series = None
    parts = None
    if stats:
        year_rows = um.year_slice(series, this_year)
        base = year_rows[0][1]
        yenspx_series = {
            "dates": [r[0].isoformat() for r in year_rows],
            "values": [round((r[1] / base - 1) * 100, 3) for r in year_rows],
        }
        parts = um.yen_spx_parts(year_rows[0][0], year_rows[-1][0])

    generated = datetime.now().astimezone()
    ref_date = date.fromisoformat(ref) if ref else None
    return {
        # 見出しはHTML側に置いてある（web/index.html）。
        # ここから流し込むと、データの更新が回るまで古い見出しが残る
        "session": ref,
        "session_text": (f"{ref_date.year}年{ref_date.month}月{ref_date.day}日"
                         if ref_date else ""),
        "generated_at": generated.isoformat(timespec="seconds"),
        "generated_at_text": generated.strftime("%Y-%m-%d %H:%M"),
        "rows": rows,
        "yenspx": yenspx_payload(stats, parts, spx_source) if stats else None,
        "yenspx_chart_title": f"円建てS&P500の{this_year}年（年初からの騰落）",
        "drawdown": {
            "title": f"年初来ドローダウンの推移（{this_year}年 と {last_year}年）",
            "note": ("その年の年初からの最高値を更新するたびに基準を引き上げ、"
                     "そこからの下落率を日ごとに描いたもの。"
                     "0%の線に張り付いているときは高値圏、"
                     "下に伸びているときは高値から下げている局面。"),
            "years": drawdown_payload(series, [this_year, last_year]),
        },
        "fear_greed": fg_out,
        "vix": vix_out,
        "yenspx_series": yenspx_series,
        "vix_chart": vix_chart,
        "fg_chart": fg_chart,
        "heatmap": heatmap_payload(),
        "sp500_monthly": monthly_payload(),
        "bands": {"fear_greed": [list(b) for b in um.FG_BANDS],
                  "vix": [list(b) for b in um.VIX_BANDS]},
        "sources": SOURCES,
        "disclaimer": DISCLAIMER,
    }


def missing_parts(payload):
    """公開に足りないものを挙げる。--strict のときはこれが空でないと書き出さない。"""
    problems = []
    got = {tile["symbol"] for row in payload["rows"] for tile in row["tiles"]}
    for symbol in um.ROW1 + um.ROW2:
        if symbol not in got:
            problems.append(f"タイル {symbol}")
    for key, label in (("yenspx", "円建てS&P500"), ("fear_greed", "Fear & Greed"),
                       ("vix", "VIX")):
        if not payload.get(key):
            problems.append(label)
    if not payload["drawdown"]["years"]:
        problems.append("ドローダウン")
    return problems


def build(out_dir="dist", refresh=False, strict=False):
    if refresh:
        failures = collector.refresh_all(verbose=True)
        if failures:
            print("取得できなかったもの:", failures)

    payload = build_payload()

    yenspx = payload.get("yenspx")
    if yenspx and not yenspx["dividends"]:
        print(f"！配当込み指数（{um.SPX_TOTAL_RETURN}）が取れず、"
              f"配当なしの {um.SPX_PRICE} で円建てS&P500を作りました。"
              "実際のファンドより年0.7%ほど低めに出ます")

    problems = missing_parts(payload)
    if problems:
        print("欠けているデータ: " + "、".join(problems))
        if strict:
            print("--strict のため書き出しを中止しました（公開中のページはそのまま残ります）")
            return None

    out = ROOT / out_dir
    out.mkdir(parents=True, exist_ok=True)
    for name in STATIC_FILES:
        shutil.copyfile(WEB_DIR / name, out / name)
    (out / "market.json").write_text(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    print(f"書き出し先: {out}")
    for name in STATIC_FILES + ["market.json"]:
        print(f"  {name:14s} {(out / name).stat().st_size:,} bytes")
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(description="GitHub Pages 用の静的ダッシュボードを書き出す")
    parser.add_argument("--out", default="dist", help="出力先ディレクトリ（既定: dist）")
    parser.add_argument("--refresh", action="store_true", help="先に最新データを取得する")
    parser.add_argument("--strict", action="store_true",
                        help="データが欠けていたら書き出さずに終了（自動更新向け）")
    args = parser.parse_args(argv)

    result = build(out_dir=args.out, refresh=args.refresh, strict=args.strict)
    return 0 if result else 1


if __name__ == "__main__":
    sys.exit(main())
