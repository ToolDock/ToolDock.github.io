"""GitHub Pages 用の静的ダッシュボードを書き出す。

Streamlit はPythonのサーバーが要るのでGitHub Pagesでは動かない。
そこで、DBの内容を market.json に固めて、素のHTML/CSS/JSから読ませる。
チャートの描画はブラウザ側（board.js + Chart.js）が行う。
ここが書き出すのは数値と系列だけで、図そのものは持たない。

    python build_static.py                        # dist/ に書き出し
    python build_static.py --refresh              # 先にデータを取得してから書き出し
    python build_static.py --out docs/us-market   # 出力先を変える

GitHub Actions など、DBを持ち回らない環境向け:

    python build_static.py --refresh --strict --nav-csv data/fund_nav.csv --out docs/us-market

--nav-csv は基準価額の履歴をCSVで読み書きする（毎回400件以上を取り直さないため）。
--strict はデータが欠けていたら書き出さずに終了する（公開中のページを壊さないため）。

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
from datetime import date, datetime
from pathlib import Path

import collect_us_market as collector
from utils import us_market as um

ROOT = Path(__file__).resolve().parent
WEB_DIR = ROOT / "web"
STATIC_FILES = ["index.html", "board.css", "board.js"]

SOURCES = [
    "指数・為替・金利・コモディティ・BTC: Yahoo Finance",
    "基準価額: 三菱UFJアセットマネジメント ファンド情報API",
    "Fear & Greed: CNN Business",
]
DISCLAIMER = ("本ページは市況の把握を目的とした情報提供であり、"
              "特定の銘柄・商品の売買を勧めるものではありません。")


def slug(symbol):
    """^GSPC → gspc、JPY=X → jpy-x。HTMLのidに使う。"""
    return "".join(c if c.isalnum() else "-" for c in symbol.lower()).strip("-")


# ── 各パートのデータ ──────────────────────────────────────────
def tile_payload(tile):
    change_text, sign = um.format_change(tile)
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
    }


def fund_payload(stats):
    change = stats["change"]
    sign = 1 if (change or 0) > 0 else (-1 if (change or 0) < 0 else 0)
    return {
        "name": um.FUND_NAME,
        "fund_cd": um.FUND_CD,
        "year": stats["year"],
        "date": stats["date"].isoformat(),
        "date_text": f"{stats['date'].year}年{stats['date'].month}月{stats['date'].day}日",
        "nav": stats["nav"],
        "nav_text": f"{stats['nav']:,.0f}",
        "change": change,
        "change_pct": stats["change_pct"],
        "change_text": "—" if change is None else
                       f"{change:+,.0f}円（{stats['change_pct']:+.2f}%）",
        "direction": sign,
        "arrow": "▲" if sign > 0 else ("▼" if sign < 0 else "―"),
        "start_date": stats["start_date"].isoformat(),
        "start_date_text": f"{stats['start_date'].month}月{stats['start_date'].day}日",
        "start_nav": stats["start_nav"],
        "ytd_pct": round(stats["ytd_pct"], 2),
        "peak": stats["peak"],
        "from_peak_pct": round(stats["from_peak_pct"], 2),
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

    series = um.load_nav_series()
    stats = um.ytd_stats(series, this_year)
    fg = um.load_fear_greed()
    vix = um.load_vix()
    fg_out, vix_out = sentiment_payload(fg, vix)

    rows = []
    for title, symbols in (("主要指数・為替", um.ROW1),
                           ("コモディティ・金利・暗号資産・半導体", um.ROW2)):
        tiles = [tile_payload(tile) for tile in um.load_tiles(symbols)]
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

    # 基準価額の年初来。日付と値だけ渡し、描画はブラウザ側に任せる
    fund_series = None
    if stats:
        year_rows = um.year_slice(series, this_year)
        fund_series = {
            "dates": [r[0].isoformat() for r in year_rows],
            "values": [r[1] for r in year_rows],
        }

    generated = datetime.now().astimezone()
    return {
        "title": "今日の米国市場",
        "generated_at": generated.isoformat(timespec="seconds"),
        "generated_at_text": generated.strftime("%Y-%m-%d %H:%M"),
        "rows": rows,
        "fund": fund_payload(stats) if stats else None,
        "fund_chart_title": f"{um.FUND_NAME}（円建て・基準価額）",
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
        "fund_series": fund_series,
        "vix_chart": vix_chart,
        "fg_chart": fg_chart,
        "heatmap": heatmap_payload(),
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
    for key, label in (("fund", "基準価額"), ("fear_greed", "Fear & Greed"), ("vix", "VIX")):
        if not payload.get(key):
            problems.append(label)
    if not payload["drawdown"]["years"]:
        problems.append("ドローダウン")
    return problems


def build(out_dir="dist", refresh=False, nav_csv=None, strict=False):
    if nav_csv:
        # CIではDBを持ち回らないので、リポジトリのCSVから履歴を復元してから取得する
        collector.init_tables()
        restored = collector.import_nav_csv(nav_csv)
        print(f"基準価額の履歴を読み込み: {restored}件（{nav_csv}）")

    if refresh:
        failures = collector.refresh_all(verbose=True)
        if failures:
            print("取得できなかったもの:", failures)

    if nav_csv:
        saved = collector.export_nav_csv(nav_csv)
        print(f"基準価額の履歴を書き出し: {saved}件（{nav_csv}）")

    payload = build_payload()
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
    parser.add_argument("--nav-csv", help="基準価額の履歴CSV。読み込んでから取得し、最後に書き戻す")
    parser.add_argument("--strict", action="store_true",
                        help="データが欠けていたら書き出さずに終了（自動更新向け）")
    args = parser.parse_args(argv)

    result = build(out_dir=args.out, refresh=args.refresh,
                   nav_csv=args.nav_csv, strict=args.strict)
    return 0 if result else 1


if __name__ == "__main__":
    sys.exit(main())
