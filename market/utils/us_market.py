"""米国市場ダッシュボードの表示用データを investment_ai.db から組み立てる。

収集は collect_us_market.py が担当。ここは DB を読んで、
タイル・チャート・メーターがそのまま使える形に整えるだけの層。
"""

import sqlite3
from datetime import date, datetime, timedelta, timezone

# collect_us_market と同じ定義を使う（循環importを避けるためこちらでは再定義しない）
from collect_us_market import FUND_CD, FUND_NAME, SYMBOLS  # noqa: E402
from db import DB_PATH  # noqa: E402

ROW1 = ["^GSPC", "^NDX", "^NYFANG", "JPY=X"]
ROW2 = ["GC=F", "^TNX", "BTC-USD", "^SOX"]

# ページ全体がどの取引日のものかを決める銘柄
ANCHOR_SYMBOL = "^GSPC"


def _conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# ── 指数・為替・金利・コモディティ ─────────────────────────────
def reference_session(conn=None):
    """ページ全体が指す取引日。米国株の最終セッションに合わせる。

    ドル円とBTCは24時間動いているので、素直に最新値を出すと
    「今まさに動いている今日」の値になり、米国株の終値と日付がずれる。
    このページを朝に見る日本のユーザーが知りたいのは昨夜引けた米国市場なので、
    24時間市場のほうを米国株の取引日に寄せる。
    """
    own = conn is None
    conn = conn or _conn()
    try:
        row = conn.execute("SELECT session FROM market_quote WHERE symbol = ?",
                           (ANCHOR_SYMBOL,)).fetchone()
        return row["session"] if row else None
    finally:
        if own:
            conn.close()


def _target_session(conn, symbol, wanted):
    """その銘柄で実際に使えるセッション日を返す。

    指定した日にデータが無いことがある（その市場だけ休場、
    取引所ローカル日付のずれ、取得漏れ）。その場合は指定日以前で
    いちばん新しい日に落とす。それも無ければ銘柄自身の最新日。
    """
    row = conn.execute(
        "SELECT session FROM market_intraday WHERE symbol = ? AND session <= ? "
        "ORDER BY session DESC LIMIT 1", (symbol, wanted)).fetchone()
    if row is None:
        row = conn.execute(
            "SELECT session FROM market_intraday WHERE symbol = ? "
            "ORDER BY session DESC LIMIT 1", (symbol,)).fetchone()
    return row["session"] if row else None


def load_tile(symbol, conn=None, session=None):
    """1銘柄ぶんの数値と日中チャート。データがなければ None。

    session を渡すと、その取引日の終値を返す。
    渡さなければ、その銘柄自身の最新セッションを使う。
    """
    own = conn is None
    conn = conn or _conn()
    try:
        quote = conn.execute("SELECT * FROM market_quote WHERE symbol = ?", (symbol,)).fetchone()
        if quote is None:
            return None

        # 日中足がまったく無くても、クオートだけでタイルは出せる
        # （グラフが空になるだけ）。ここで落とすと --strict が
        # 「タイルが欠けている」と見なして書き出しごと止めてしまう
        target = _target_session(conn, symbol, session or quote["session"]) \
            or quote["session"]

        points = conn.execute(
            "SELECT ts, value FROM market_intraday WHERE symbol = ? AND session = ? ORDER BY ts",
            (symbol, target)).fetchall()

        if target == quote["session"]:
            # その銘柄自身の最新セッション。
            # 取引所が出している正式な前セッション終値をそのまま使える
            price = quote["price"]
            prev = quote["prev_close"]
        else:
            # 過去のセッションに戻した場合（ドル円・BTCがこちらに来る）。
            # その日の最終値と、ひとつ前のセッションの最終値を突き合わせる
            price = points[-1]["value"] if points else None
            prev_row = conn.execute(
                "SELECT value FROM market_intraday WHERE symbol = ? AND session < ? "
                "ORDER BY session DESC, ts DESC LIMIT 1", (symbol, target)).fetchone()
            prev = prev_row["value"] if prev_row else None
    finally:
        if own:
            conn.close()

    if price is None:
        return None

    meta = SYMBOLS.get(symbol, {})
    offset = quote["tz_offset"] or 0

    # 前日比。金利だけは % ではなく bp（0.01%）で見るのが慣習。
    change = None if prev is None else price - prev
    change_pct = None if (change is None or not prev) else change / prev * 100
    change_bp = None if change is None else change * 100

    return {
        "symbol": symbol,
        "label": meta.get("label", symbol),
        "digits": meta.get("digits", 2),
        "unit": meta.get("unit", ""),
        "change_mode": meta.get("change", "pct"),
        "session": target,
        "price": price,
        "prev_close": prev,
        "change": change,
        "change_pct": change_pct,
        "change_bp": change_bp,
        "times": [datetime.fromtimestamp(r["ts"] + offset, timezone.utc).replace(tzinfo=None)
                  for r in points],
        "values": [r["value"] for r in points],
    }


def load_tiles(symbols, session=None):
    conn = _conn()
    try:
        return [t for t in (load_tile(s, conn, session) for s in symbols) if t]
    finally:
        conn.close()


def format_price(tile):
    digits = tile["digits"]
    unit = tile["unit"]
    text = f"{tile['price']:,.{digits}f}"
    if unit == "$":
        return f"${text}"
    return f"{text}{unit}"


def format_change(tile):
    """(前日比の文字列, 上げ下げ符号) を返す。符号は色分けに使う。"""
    if tile["change"] is None:
        return "—", 0
    sign = 1 if tile["change"] > 0 else (-1 if tile["change"] < 0 else 0)
    if tile["change_mode"] == "bp":
        return f"{tile['change_bp']:+.1f}bp（{tile['change_pct']:+.2f}%）", sign
    digits = tile["digits"]
    return f"{tile['change']:+,.{digits}f}（{tile['change_pct']:+.2f}%）", sign


# ── eMAXIS Slim 米国株式（S&P500）の基準価額 ──────────────────
def load_nav_series(fund_cd=FUND_CD, start=None):
    """[(date, nav), ...] を日付昇順で返す。"""
    conn = _conn()
    try:
        sql = "SELECT date, nav, change_pct FROM fund_nav WHERE fund_cd = ? AND nav IS NOT NULL"
        args = [fund_cd]
        if start:
            sql += " AND date >= ?"
            args.append(start.isoformat() if hasattr(start, "isoformat") else start)
        sql += " ORDER BY date"
        return [(date.fromisoformat(r["date"]), r["nav"], r["change_pct"])
                for r in conn.execute(sql, args)]
    finally:
        conn.close()


def year_slice(series, year):
    return [row for row in series if row[0].year == year]


def ytd_stats(series, year):
    """年初来の騰落・前日比・直近値をまとめる。"""
    rows = year_slice(series, year)
    if not rows:
        return None
    first_date, first_nav, _ = rows[0]
    last_date, last_nav, last_chg = rows[-1]
    prev_nav = rows[-2][1] if len(rows) >= 2 else None
    peak = max(r[1] for r in rows)
    return {
        "year": year,
        "start_date": first_date,
        "start_nav": first_nav,
        "date": last_date,
        "nav": last_nav,
        "prev_nav": prev_nav,
        "change": None if prev_nav is None else last_nav - prev_nav,
        "change_pct": last_chg,
        "ytd_pct": (last_nav / first_nav - 1) * 100,
        "peak": peak,
        "from_peak_pct": (last_nav / peak - 1) * 100,
    }


def drawdown_series(series, year):
    """年初来ドローダウン。その年の最初の営業日を起点に、
    それまでの最高値からの下落率（%、0以下）を日ごとに返す。"""
    rows = year_slice(series, year)
    if not rows:
        return []
    out = []
    peak = rows[0][1]
    for day, nav, _ in rows:
        peak = max(peak, nav)
        out.append((day, (nav / peak - 1) * 100))
    return out


def max_drawdown(dd):
    if not dd:
        return None, None
    day, value = min(dd, key=lambda r: r[1])
    return value, day


def day_of_year(d):
    """今年・去年を重ねて比較するための横軸（1/1からの経過日数）。"""
    return (d - date(d.year, 1, 1)).days + 1


# ── Fear & Greed / VIX ──────────────────────────────────────
#
# 色はサイトの他のページ（/crystal/ /shippo/）と同じ系統でそろえている。
# 原色に近いマテリアル系（#c62828 #fbc02d #9ccc65）は彩度が高すぎて、
# 白いカードの上で浮いてしまうため使わない。
# 赤 → 橙 → 金 → 若草 → 緑 の落ち着いた5段にしてある。

FG_BANDS = [
    (0, 25, "Extreme Fear", "極度の恐怖", "#b91c1c"),
    (25, 45, "Fear", "恐怖", "#cf6a4a"),
    (45, 55, "Neutral", "中立", "#c9a227"),
    (55, 75, "Greed", "強欲", "#6f9e4c"),
    (75, 100, "Extreme Greed", "極度の強欲", "#15803d"),
]

# VIX は上の5段のうち4色を、落ち着き→警戒の向きで使う
VIX_BANDS = [
    (0, 15, "落ち着き", "#15803d"),
    (15, 20, "やや不安", "#6f9e4c"),
    (20, 30, "警戒", "#c9a227"),
    (30, 50, "極度の警戒", "#b91c1c"),
]


def load_daily(symbol, days=400):
    """日足の終値を古い順に返す。1年チャート用。"""
    conn = _conn()
    try:
        rows = conn.execute(
            "SELECT date, close FROM market_daily WHERE symbol=? ORDER BY date", (symbol,)
        ).fetchall()
    except Exception:
        return []
    finally:
        conn.close()
    out = [(r["date"], r["close"]) for r in rows if r["close"] is not None]
    return out[-days:] if days else out


def load_fg_history(days=400):
    """Fear & Greed の日次履歴を古い順に返す。CNNのヒストリカルを保存したもの。"""
    conn = _conn()
    rows = conn.execute(
        "SELECT date, value FROM fear_greed WHERE type='stock' ORDER BY date"
    ).fetchall()
    conn.close()
    out = [(r["date"], r["value"]) for r in rows if r["value"] is not None]
    return out[-days:] if days else out


def load_heatmap():
    """ヒートマップの各銘柄を、銘柄表（セクター・ウェイト）と突き合わせて返す。"""
    import json
    from pathlib import Path
    path = Path(__file__).resolve().parent.parent / "data" / "sp500_members.json"
    with open(path, encoding="utf-8") as f:
        members = json.load(f)

    conn = _conn()
    try:
        rows = {r["symbol"]: r for r in conn.execute(
            "SELECT symbol, session, change_pct FROM heatmap").fetchall()}
    except Exception:
        return []
    finally:
        conn.close()

    out = []
    for m in members:
        row = rows.get(m["symbol"])
        if not row or row["change_pct"] is None:
            continue
        out.append({**m, "change_pct": row["change_pct"], "session": row["session"]})
    return out


def fg_band(value):
    for low, high, label_en, label_ja, color in FG_BANDS:
        if low <= value <= high:
            return label_en, label_ja, color
    return FG_BANDS[-1][2], FG_BANDS[-1][3], FG_BANDS[-1][4]


def vix_band(value):
    for low, high, label, color in VIX_BANDS:
        if low <= value < high:
            return label, color
    return VIX_BANDS[-1][2], VIX_BANDS[-1][3]


def load_fear_greed():
    """最新のFear & Greedと、1週間前・1ヶ月前の値。"""
    conn = _conn()
    try:
        rows = conn.execute(
            "SELECT date, value, classification FROM fear_greed WHERE type = 'stock' "
            "ORDER BY date DESC LIMIT 40").fetchall()
    finally:
        conn.close()
    if not rows:
        return None
    latest = rows[0]
    by_date = {date.fromisoformat(r["date"]): r["value"] for r in rows}
    today = date.fromisoformat(latest["date"])

    def nearest(target):
        candidates = [d for d in by_date if d <= target]
        return by_date[max(candidates)] if candidates else None

    value = latest["value"]
    label_en, label_ja, color = fg_band(value)
    return {
        "date": today,
        "value": value,
        "label_en": label_en,
        "label_ja": label_ja,
        "color": color,
        "prev": rows[1]["value"] if len(rows) > 1 else None,
        "week_ago": nearest(today - timedelta(days=7)),
        "month_ago": nearest(today - timedelta(days=30)),
    }


def load_vix(session=None):
    tile = load_tile("^VIX", session=session)
    if not tile or tile["price"] is None:
        return None
    label, color = vix_band(tile["price"])
    tile["band_label"] = label
    tile["band_color"] = color
    return tile


def last_updated():
    conn = _conn()
    try:
        row = conn.execute("SELECT MAX(fetched_at) AS t FROM market_quote").fetchone()
    finally:
        conn.close()
    if not row or not row["t"]:
        return None
    return datetime.fromisoformat(row["t"]).astimezone()
