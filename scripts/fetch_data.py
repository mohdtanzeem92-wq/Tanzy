"""
fetch_data.py
--------------
Runs on a GitHub Actions schedule. Pulls:
  1. Bulk / Block deals            -> web/data/bulk_deals.json
  2. Delivery % (rising delivery)  -> web/data/delivery.json
  3. FII / DII daily activity      -> web/data/fii_dii.json   (market-level, not per-stock -
                                       NSE/SEBI do not publish per-stock FII/DII daily;
                                       per-stock institutional holding only exists in the
                                       quarterly shareholding pattern, refreshed separately)
  4. Price/volume snapshot (yfinance) -> web/data/prices.json

NSE does not offer an official API. The endpoints below are the same ones
nseindia.com's own website calls. They require a browser-like session:
you must hit the homepage first to receive cookies, then reuse that
session for the API calls, or NSE returns 401/403.

These endpoints can change or rate-limit without notice - if a run fails,
the workflow still commits whatever data it successfully fetched.
"""

import json
import os
import time
import datetime as dt

import requests

try:
    import yfinance as yf
except ImportError:
    yf = None

OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "web", "data")
os.makedirs(OUT_DIR, exist_ok=True)

NSE_BASE = "https://www.nseindia.com"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.nseindia.com/",
}

# Watchlist used for delivery %/price snapshot. Extend as needed.
WATCHLIST = [
    "RELIANCE", "TCS", "HDFCBANK", "INFY", "ICICIBANK", "SBIN",
    "BHARTIARTL", "ITC", "LT", "KOTAKBANK", "AXISBANK", "MARUTI",
    "SUNPHARMA", "TATAMOTORS", "TATASTEEL", "WIPRO", "ADANIENT",
    "ADANIPORTS", "HINDUNILVR", "BAJFINANCE",
]


def nse_session():
    """Warm up a session with NSE so subsequent API calls are accepted."""
    s = requests.Session()
    s.headers.update(HEADERS)
    s.get(NSE_BASE, timeout=10)
    time.sleep(1)
    s.get(f"{NSE_BASE}/market-data/securities-with-large-deals", timeout=10)
    return s


def fetch_bulk_block_deals(s):
    """Latest bulk & block deals (large trades reported to the exchange)."""
    out = {"as_of": dt.datetime.now().isoformat(), "bulk_deals": [], "block_deals": []}
    for kind, key in (("bulk_deals", "bulk_deals"), ("block_deals", "block_deals")):
        try:
            r = s.get(
                f"{NSE_BASE}/api/live-analysis-large-deals",
                params={"index": key},
                timeout=10,
            )
            r.raise_for_status()
            payload = r.json()
            rows = payload.get(key, payload if isinstance(payload, list) else [])
            out[kind] = rows
        except Exception as e:
            out[f"{kind}_error"] = str(e)
    return out


def fetch_delivery(s):
    """
    Delivery % per symbol from the quote's trade_info section.
    A rising delivery % (vs. its own recent average) often signals
    genuine accumulation rather than intraday churn.
    """
    out = {"as_of": dt.datetime.now().isoformat(), "stocks": []}
    for sym in WATCHLIST:
        try:
            r = s.get(
                f"{NSE_BASE}/api/quote-equity",
                params={"symbol": sym, "section": "trade_info"},
                timeout=10,
            )
            r.raise_for_status()
            j = r.json()
            dp = j.get("securityWiseDP", {})
            out["stocks"].append({
                "symbol": sym,
                "deliveryQtyPct": dp.get("deliveryToTradedQuantity"),
                "quantityTraded": dp.get("quantityTraded"),
                "deliveryQty": dp.get("deliveryQuantity"),
            })
            time.sleep(0.6)  # be polite to avoid throttling
        except Exception as e:
            out["stocks"].append({"symbol": sym, "error": str(e)})
    return out


def fetch_fii_dii(s):
    """
    Daily FII/DII net buy-sell figures. This is MARKET-LEVEL (cash market
    provisional data) - NSE does not publish a daily per-stock breakdown.
    """
    out = {"as_of": dt.datetime.now().isoformat(), "rows": [], "note":
           "Market-level provisional data only. Per-stock FII/DII holding "
           "is only available quarterly via shareholding patterns."}
    try:
        r = s.get(f"{NSE_BASE}/api/fiidiiTradeReact", timeout=10)
        r.raise_for_status()
        out["rows"] = r.json()
    except Exception as e:
        out["error"] = str(e)
    return out


def fetch_prices():
    """Price/volume snapshot via yfinance for the same watchlist."""
    out = {"as_of": dt.datetime.now().isoformat(), "stocks": []}
    if yf is None:
        out["error"] = "yfinance not installed"
        return out
    for sym in WATCHLIST:
        try:
            t = yf.Ticker(f"{sym}.NS")
            hist = t.history(period="5d")
            if hist.empty:
                continue
            last = hist.iloc[-1]
            prev = hist.iloc[-2] if len(hist) > 1 else last
            out["stocks"].append({
                "symbol": sym,
                "close": round(float(last["Close"]), 2),
                "volume": int(last["Volume"]),
                "changePct": round(
                    ((last["Close"] - prev["Close"]) / prev["Close"]) * 100, 2
                ),
            })
        except Exception as e:
            out["stocks"].append({"symbol": sym, "error": str(e)})
    return out


def dump(name, payload):
    path = os.path.join(OUT_DIR, name)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print(f"wrote {path}")


def main():
    s = nse_session()
    dump("bulk_deals.json", fetch_bulk_block_deals(s))
    dump("delivery.json", fetch_delivery(s))
    dump("fii_dii.json", fetch_fii_dii(s))
    dump("prices.json", fetch_prices())


if __name__ == "__main__":
    main()
