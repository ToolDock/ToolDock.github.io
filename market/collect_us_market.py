"""米国市場ダッシュボード用のデータ収集。

データ源:
- Yahoo Finance chart API（無料・キー不要）→ 主要指数・為替・金利・コモディティの
  日中5分足と直近クオート、および日足5年ぶん
- CNN Business Fear & Greed Index

取得結果は investment_ai.db にキャッシュし、再実行時は不足分だけ取りに行く。

    python collect_us_market.py

■ 基準価額をやめた経緯（2026-09）

以前は三菱UFJアセットマネジメントのファンド情報WEB-APIから
eMAXIS Slim 米国株式（S&P500）の基準価額を取っていたが、
2026-08-31 から 403 が返り続けるようになった。
ランナーから確かめたところ、トップページも含めてドメイン全体が403で、
ブラウザ相当のヘッダーを全部つけても変わらなかった。
GitHub Actions の出口は米国のデータセンター（確認時は Phoenix, Arizona）で、
そこが弾かれている。ヘッダーで抜けられる類ではない。

代わりに、円建てS&P500を自前で計算している（build_static.py の yen_index）。
S&P500（配当込み）とドル円を掛け合わせたもので、実際の基準価額とは
信託報酬や反映時刻のぶんだけずれるが、手元の実績403日ぶんと
突き合わせたところ、ずれはおおむね1%台に収まっていた。
"""

import io
import json
import time
from datetime import date, datetime, timezone
from pathlib import Path

import requests

from db import get_connection

# ── 取得対象 ────────────────────────────────────────────────
# digits: 表示小数桁 / unit: 単位 / change: 前日比の見せ方（pct=%、bp=ベーシスポイント）
SYMBOLS = {
    "^GSPC":   {"label": "S&P500",         "digits": 2, "unit": "",   "change": "pct"},
    "^NDX":    {"label": "NASDAQ100",      "digits": 2, "unit": "",   "change": "pct"},
    "^NYFANG": {"label": "NYSE FANG+",     "digits": 2, "unit": "",   "change": "pct"},
    "JPY=X":   {"label": "ドル円",          "digits": 3, "unit": "円", "change": "pct"},
    "GC=F":    {"label": "ゴールド",         "digits": 2, "unit": "$", "change": "pct"},
    "^TNX":    {"label": "米国債10年利回り",  "digits": 3, "unit": "%", "change": "bp"},
    "BTC-USD": {"label": "BTC/USD",        "digits": 0, "unit": "$",  "change": "pct"},
    "^SOX":    {"label": "SOX指数",         "digits": 2, "unit": "",   "change": "pct"},
    "^VIX":    {"label": "VIX",            "digits": 2, "unit": "",   "change": "pct"},
}

# 日足を取る銘柄。タイルの期間切り替え（1ヶ月・年初来・1年・5年）と、
# VIX／S&P500の1年チャートに使う。5分足とは別のテーブルに入れる
# ^SP500TR は配当込みのS&P500。円建てS&P500の計算に使う。
# 配当を含まない ^GSPC で作ると、実際のファンドより年0.7%ほど下に離れていく。
# タイルには出さないので SYMBOLS には入れない。取れなければ ^GSPC に落とす
DAILY_SYMBOLS = list(SYMBOLS) + ["^SP500TR"]
DAILY_RANGE = "5y"

YAHOO_HOST = "https://query2.finance.yahoo.com"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")


# ── テーブル定義 ─────────────────────────────────────────────
def init_tables():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS market_intraday (
            symbol TEXT,
            session TEXT,   -- 取引所ローカル日付 YYYY-MM-DD
            ts INTEGER,     -- UNIX秒（UTC）
            value REAL,
            PRIMARY KEY (symbol, session, ts)
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS market_quote (
            symbol TEXT PRIMARY KEY,
            session TEXT,        -- 最新セッションの取引所ローカル日付
            price REAL,          -- 直近値
            prev_close REAL,     -- 前セッション終値（YahooのpreviousClose）
            market_time INTEGER, -- 直近値のUNIX秒
            tz_offset INTEGER,   -- 取引所ローカル時刻へのオフセット（秒）
            fetched_at TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS market_daily (
            symbol TEXT,
            date TEXT,      -- 取引所ローカル日付 YYYY-MM-DD
            close REAL,
            PRIMARY KEY (symbol, date)
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS heatmap (
            symbol TEXT PRIMARY KEY,
            session TEXT,
            price REAL,
            prev_close REAL,
            change_pct REAL,
            fetched_at TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS fear_greed (
            date TEXT,
            type TEXT,
            value REAL,
            classification TEXT,
            PRIMARY KEY (date, type)
        )
    """)
    conn.commit()
    conn.close()


# ── Yahoo Finance ───────────────────────────────────────────
_session = None


def _http():
    global _session
    if _session is None:
        _session = requests.Session()
        _session.headers.update({"User-Agent": UA, "Accept": "application/json,text/plain,*/*"})
    return _session


def fetch_chart(symbol, rng, interval, retries=4):
    """Yahoo chart APIを叩く。連続アクセスすると429が返るので指数バックオフで粘る。"""
    url = f"{YAHOO_HOST}/v8/finance/chart/{requests.utils.quote(symbol)}"
    params = {"range": rng, "interval": interval}
    last = None
    for attempt in range(retries):
        res = _http().get(url, params=params, timeout=30)
        if res.status_code == 200:
            result = res.json()["chart"]["result"]
            if not result:
                raise RuntimeError(f"{symbol}: 空のレスポンス")
            return result[0]
        last = f"{res.status_code} {res.text[:80]}"
        time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"{symbol}: 取得失敗 ({last})")


def _series(result):
    """(timestamp, close) の欠損なしリストを返す。"""
    stamps = result.get("timestamp") or []
    closes = result["indicators"]["quote"][0].get("close") or []
    return [(t, c) for t, c in zip(stamps, closes) if c is not None]


def refresh_symbol(symbol):
    """直近5営業日の5分足と、最新のクオートを1リクエストで取得・保存。

    range=1d は週末に空を返す銘柄（先物など）があるため、常に5dで取って
    最終セッションだけを使う。前日比の基準は meta.previousClose（＝取引所の
    正式な前セッション終値）を採用する。
    """
    result = fetch_chart(symbol, "5d", "5m")
    meta = result["meta"]
    offset = meta.get("gmtoffset") or 0

    rows = []
    for stamp, value in _series(result):
        session = datetime.fromtimestamp(stamp + offset, timezone.utc).date().isoformat()
        rows.append((symbol, session, stamp, value))
    if not rows:
        raise RuntimeError(f"{symbol}: 5分足が空")

    latest_session = rows[-1][1]
    price = meta.get("regularMarketPrice")
    if price is None:
        price = rows[-1][3]
    prev_close = meta.get("previousClose")
    if prev_close is None:
        # 前セッションの最終値で代用
        prev = [r for r in rows if r[1] < latest_session]
        prev_close = prev[-1][3] if prev else None

    conn = get_connection()
    conn.executemany(
        "INSERT OR REPLACE INTO market_intraday (symbol, session, ts, value) VALUES (?,?,?,?)",
        rows)
    conn.execute(
        "INSERT OR REPLACE INTO market_quote "
        "(symbol, session, price, prev_close, market_time, tz_offset, fetched_at) "
        "VALUES (?,?,?,?,?,?,?)",
        (symbol, latest_session, price, prev_close, meta.get("regularMarketTime"), offset,
         datetime.now(timezone.utc).isoformat(timespec="seconds")))
    conn.commit()
    conn.close()
    return len(rows), latest_session


def refresh_daily(symbol, rng=DAILY_RANGE):
    """日足を取得して保存する。タイルの期間切り替えと1年チャート用。

    5分足（refresh_symbol）とは別のテーブルに入れる。
    こちらは1銘柄1リクエストで済むので、負荷はほとんど変わらない。
    """
    result = fetch_chart(symbol, rng, "1d")
    offset = result["meta"].get("gmtoffset") or 0

    rows = []
    for stamp, value in _series(result):
        day = datetime.fromtimestamp(stamp + offset, timezone.utc).date().isoformat()
        rows.append((symbol, day, value))
    if not rows:
        raise RuntimeError(f"{symbol}: 日足が空")

    conn = get_connection()
    conn.executemany(
        "INSERT OR REPLACE INTO market_daily (symbol, date, close) VALUES (?,?,?)", rows)
    conn.commit()
    conn.close()
    return len(rows)


def refresh_dailies(symbols=DAILY_SYMBOLS, pause=0.8, verbose=False):
    failed = []
    for symbol in symbols:
        try:
            count = refresh_daily(symbol)
            if verbose:
                print(f"  {symbol:9s} 日足 {count}件")
        except Exception as e:
            failed.append((symbol, str(e)))
            if verbose:
                print(f"  {symbol:9s} 日足 失敗: {e}")
        time.sleep(pause)
    return failed


def refresh_market(symbols=None, pause=0.8, verbose=False):
    """全シンボルを更新。失敗したものの一覧を返す。"""
    failed = []
    for symbol in (symbols or SYMBOLS):
        try:
            count, session = refresh_symbol(symbol)
            if verbose:
                print(f"  {symbol:9s} {count}件 最終セッション={session}")
        except Exception as e:
            failed.append((symbol, str(e)))
            if verbose:
                print(f"  {symbol:9s} 失敗: {e}")
        time.sleep(pause)
    return failed


# ── ヒートマップ（S&P500の主要銘柄） ──────────────────────────
MEMBERS_PATH = Path(__file__).resolve().parent / "data" / "sp500_members.json"


def load_members():
    """銘柄・セクター・ウェイトの表を読む。

    ウェイトはタイルの面積を決めるためだけの概算値で、画面には出さない。
    銘柄の入れ替えは年に数回あるので、この表はときどき見直すこと。
    """
    with io.open(MEMBERS_PATH, encoding="utf-8") as f:
        return json.load(f)


def refresh_heatmap(pause=1.0, verbose=False, limit=None):
    """各銘柄の前日比を取得して保存する。

    1銘柄1リクエストなので、他の取得よりずっと重い。
    Yahoo は非公式APIで、まとめて叩くと429を返すことがある。
    ここが失敗してもダッシュボード本体は成り立つので、
    build 側では欠けていても中止しない扱いにしてある。
    """
    members = load_members()
    if limit:
        members = members[:limit]

    rows, failed = [], []
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")

    for member in members:
        symbol = member["symbol"]
        try:
            result = fetch_chart(symbol, "5d", "1d")
            meta = result["meta"]
            series = _series(result)
            price = meta.get("regularMarketPrice") or (series[-1][1] if series else None)
            prev = meta.get("previousClose")
            if prev is None and len(series) >= 2:
                prev = series[-2][1]
            if price is None or not prev:
                raise RuntimeError("価格が取れない")

            offset = meta.get("gmtoffset") or 0
            session = datetime.fromtimestamp(
                (series[-1][0] if series else 0) + offset, timezone.utc).date().isoformat()
            rows.append((symbol, session, price, prev,
                         round((price - prev) / prev * 100, 2), now))
            if verbose:
                print(f"  {symbol:6s} {rows[-1][4]:+.2f}%")
        except Exception as e:
            failed.append((symbol, str(e)))
            if verbose:
                print(f"  {symbol:6s} 失敗: {e}")
        time.sleep(pause)

    if rows:
        conn = get_connection()
        conn.executemany(
            "INSERT OR REPLACE INTO heatmap "
            "(symbol, session, price, prev_close, change_pct, fetched_at) VALUES (?,?,?,?,?,?)",
            rows)
        conn.commit()
        conn.close()
    return len(rows), failed


# ── Fear & Greed ───────────────────────────────────────────
def refresh_fear_greed():
    """CNNのFear & Greed Index（当日値＋ヒストリカル）を保存。"""
    res = requests.get(
        "https://production.dataviz.cnn.io/index/fearandgreed/graphdata",
        headers={"User-Agent": UA, "Referer": "https://edition.cnn.com/",
                 "Origin": "https://edition.cnn.com"},
        timeout=30,
    )
    res.raise_for_status()
    data = res.json()
    current = data["fear_and_greed"]

    rows = []
    for point in data.get("fear_and_greed_historical", {}).get("data", []):
        day = datetime.fromtimestamp(point["x"] / 1000, timezone.utc).date().isoformat()
        rows.append((day, "stock", round(float(point["y"]), 1), point.get("rating")))
    rows.append((date.today().isoformat(), "stock",
                 round(float(current["score"]), 1), current["rating"]))

    conn = get_connection()
    conn.executemany("INSERT OR REPLACE INTO fear_greed (date, type, value, classification) "
                     "VALUES (?,?,?,?)", rows)
    conn.commit()
    conn.close()
    return round(float(current["score"]), 1), current["rating"], len(rows)


# ── まとめて更新 ─────────────────────────────────────────────
def refresh_all(verbose=False):
    """ダッシュボード表示前の通常更新。"""
    init_tables()
    failed = refresh_market(verbose=verbose)
    failed += refresh_dailies(verbose=verbose)
    try:
        refresh_fear_greed()
    except Exception as e:
        failed.append(("fear_greed", str(e)))

    # ヒートマップは86リクエストと重く、Yahooに弾かれることもある。
    # ここが取れなくてもダッシュボード本体は成り立つので、
    # 失敗しても failed には積まず、警告だけ出す
    try:
        count, hm_failed = refresh_heatmap(verbose=verbose)
        if verbose:
            print(f"  ヒートマップ {count}件取得"
                  + (f"（{len(hm_failed)}件失敗）" if hm_failed else ""))
    except Exception as e:
        print(f"  ヒートマップの取得に失敗しました（本体には影響しません）: {e}")
    return failed


if __name__ == "__main__":
    init_tables()

    print("■ 指数・為替・金利・コモディティ")
    failures = refresh_market(verbose=True)

    print("■ 日足（期間切り替えと円建てS&P500に使う）")
    failures += refresh_dailies(verbose=True)

    print("■ Fear & Greed")
    try:
        score, rating, n = refresh_fear_greed()
        print(f"  今日: {score} ({rating}) / ヒストリカル{n}件")
    except Exception as e:
        print(f"  失敗: {e}")

    if failures:
        print("\n取得できなかったもの:")
        for item in failures:
            print("  ", item)
