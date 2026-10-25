# -*- coding: utf-8 -*-
"""
portfolio.py  -  Stock Portfolio Performance Tracker
=====================================================
Features
--------
• Loads S&P 500 ticker metadata (symbol, name, sector) from 'constituents.csv'.
• Prompts for holdings: ticker symbol, buy price, share quantity.
• Stores portfolio positions in a dictionary keyed by symbol.
• Looks up current prices live from Stooq (free endpoint, stdlib only) —
  graceful fallback to manual price entry when offline.
• Computes invested capital vs current market value, per-holding P/L,
  portfolio totals, and best / worst performers.
• Automatically logs the transaction summary to 'portfolio_summary.csv'
  using Python's built-in csv module.

Usage
-----
    python portfolio.py
"""

import csv
import os
import sys
import io
import re
import urllib.request
from datetime import datetime
from pathlib import Path

# ── Force UTF-8 output on Windows so Unicode symbols print correctly ──────────
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# ──────────────────────────────────────────────────────────────────────────────
# ANSI colour helpers
# ──────────────────────────────────────────────────────────────────────────────

_USE_COLOUR = True

def _c(code: str, text: str) -> str:
    """Wrap *text* in an ANSI escape *code* when colour is enabled."""
    return f"\033[{code}m{text}\033[0m" if _USE_COLOUR else text

def red(t):    return _c("91", t)
def green(t):  return _c("92", t)
def yellow(t): return _c("93", t)
def cyan(t):   return _c("96", t)
def bold(t):   return _c("1",  t)
def dim(t):    return _c("2",  t)

# ──────────────────────────────────────────────────────────────────────────────
# File paths (resolved next to this script so the tool works from anywhere)
# ──────────────────────────────────────────────────────────────────────────────

_SCRIPT_DIR  = Path(__file__).resolve().parent
_UNIVERSE_CSV = _SCRIPT_DIR / "constituents.csv"        # S&P 500 ticker dataset
_SUMMARY_CSV  = _SCRIPT_DIR / "portfolio_summary.csv"   # generated performance log

# ──────────────────────────────────────────────────────────────────────────────
# Ticker universe (from the bundled constituents.csv)
# ──────────────────────────────────────────────────────────────────────────────

def load_universe() -> dict:
    """Return {symbol: {'name': …, 'sector': …}} from the S&P 500 dataset."""
    if not _UNIVERSE_CSV.exists():
        print(yellow(f"Warning: '{_UNIVERSE_CSV.name}' not found — "
                     f"ticker validation and company names disabled.\n"))
        return {}
    universe = {}
    with _UNIVERSE_CSV.open(encoding="utf-8-sig", newline="") as fh:
        for row in csv.DictReader(fh):
            symbol = (row.get("Symbol") or "").strip().upper()
            if symbol:
                universe[symbol] = {
                    "name":   (row.get("Security") or "").strip(),
                    "sector": (row.get("GICS Sector") or "").strip(),
                }
    return universe


def money(value: float) -> str:
    """Format a currency amount, e.g. 1,234.56 (no symbol)."""
    return f"{value:,.2f}"


def parse_float(prompt: str, allow_zero: bool = False) -> float:
    """Prompt until the user enters a valid positive decimal number."""
    while True:
        raw = input(prompt).replace("$", "").replace(",", "").strip()
        try:
            value = float(raw)
        except ValueError:
            print(red("  ✘  Please enter a valid number."))
            continue
        if value < 0 or (value == 0 and not allow_zero):
            print(red("  ✘  Value must be greater than zero."))
            continue
        return value


# ──────────────────────────────────────────────────────────────────────────────
# Live price lookup (Stooq free CSV endpoint — stdlib only, no API key)
# ──────────────────────────────────────────────────────────────────────────────

def fetch_live_price(symbol: str, timeout: float = 8.0):
    """
    Return the latest price for *symbol* from stooq.com, or None on any
    network / parse failure (caller falls back to manual entry).
    """
    url = f"https://stooq.com/q/l/?s={symbol.lower()}.us&f=sd2t2ohlcv&h&e=csv"
    try:
        request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(request, timeout=timeout) as response:
            rows = list(csv.DictReader(io.TextIOWrapper(response, encoding="utf-8")))
        close = rows[-1].get("Close", "") if rows else ""
        price = float(close)
        return price if price > 0 else None
    except Exception:
        return None


def resolve_prices(positions: dict) -> None:
    """Attach a current price to every position (live fetch → manual fallback)."""
    for symbol, info in positions.items():
        print(dim(f"  Fetching live price for {symbol} …"), end="\r")
        price = fetch_live_price(symbol)
        if price is not None:
            info["current"] = price
            info["source"]  = "stooq"
            print(green(f"  ✔  {symbol:<6s} live price  ${money(price):>10s}      "))
        else:
            print(yellow(f"  ⚠  {symbol:<6s} live lookup failed — enter it manually."))
            while True:
                price = parse_float(bold(f"     Current price of {symbol} → $"))
                if price > 0:
                    break
                print(red("     Price must be greater than zero."))
            info["current"] = price
            info["source"]  = "manual"


# ──────────────────────────────────────────────────────────────────────────────
# Input entry: build the position dictionary
# ──────────────────────────────────────────────────────────────────────────────

def add_position(positions: dict, universe: dict) -> None:
    """Interactively add (or add-to) one holding in the positions dict."""
    while True:
        symbol = input(bold("  Ticker symbol  → ")).strip().upper()
        if re.fullmatch(r"[A-Z.\-]{1,6}", symbol):
            break
        print(red("  ✘  Symbols are 1-6 letters/digits, e.g. AAPL."))

    if symbol in positions:
        print(yellow(f"  ⚠  You already hold {symbol} ({positions[symbol]['qty']:g} shares "
                     f"@ ${money(positions[symbol]['buy_price'])} avg). Adding to the position."))
        existing_qty   = positions[symbol]["qty"]
        existing_price = positions[symbol]["buy_price"]
    else:
        existing_qty, existing_price = 0.0, 0.0

    if universe and symbol not in universe:
        confirm = input(yellow(f"  ⚠  '{symbol}' is not in the S&P 500 list. Add anyway? (y/n) → ")).strip().lower()
        if confirm != "y":
            print(dim("  Cancelled."))
            return

    qty   = parse_float(bold("  Share quantity → "))
    price = parse_float(bold("  Buy price      → $"))

    # Weighted-average buy price when adding to an existing holding
    total_qty   = existing_qty + qty
    avg_price   = ((existing_qty * existing_price) + (qty * price)) / total_qty

    meta = universe.get(symbol, {})
    positions[symbol] = {
        "name":   meta.get("name", "(unknown company)"),
        "sector": meta.get("sector", "(unknown sector)"),
        "qty":   total_qty,
        "buy_price": avg_price,
    }

    print(green(f"  ✔  Added {qty:g} × {symbol} @ ${money(price)} "
                f"(position now {total_qty:g} shares @ ${money(avg_price)} avg)"))


# ──────────────────────────────────────────────────────────────────────────────
# Valuation + reporting
# ──────────────────────────────────────────────────────────────────────────────

def compute_rows(positions: dict) -> list:
    """Turn the positions dict into valuation rows (one per holding)."""
    rows = []
    for symbol, info in positions.items():
        invested = info["qty"] * info["buy_price"]
        market   = info["qty"] * info["current"]
        pl_val   = market - invested
        pl_pct   = (pl_val / invested) * 100 if invested else 0.0
        rows.append({
            "symbol":   symbol,
            "name":     info["name"],
            "sector":   info["sector"],
            "qty":      info["qty"],
            "buy":      info["buy_price"],
            "current":  info["current"],
            "invested": invested,
            "market":   market,
            "pl_val":   pl_val,
            "pl_pct":   pl_pct,
            "source":   info["source"],
        })
    return rows


def _pl_coloured(value: float) -> str:
    if value > 0:
        return green(f"+{money(value)}")
    if value < 0:
        return red(money(value))
    return yellow("0.00")


def _pl_pct_coloured(value: float) -> str:
    if value > 0:
        return green(f"+{value:.2f}%")
    if value < 0:
        return red(f"{value:.2f}%")
    return yellow("0.00%")


def render_report(rows: list) -> None:
    """Print the formatted portfolio valuation table to the console."""
    print(bold(cyan("""
  ╔══════════════════════════════════════════════════════════════════╗
  ║                 S T O C K   P O R T F O L I O                    ║
  ╚══════════════════════════════════════════════════════════════════╝
""")))
    header = (f"  {'SYMBOL':<7}{'COMPANY':<26}{'SECTOR':<20}{'QTY':>6}"
              f"{'BUY':>10}{'NOW':>10}{'VALUE':>11}{'P/L %':>9}{'P/L $':>11}")
    print(bold(header))
    print(dim("  " + "─" * 100))

    for r in rows:
        company = (r["name"][:24] + "…") if len(r["name"]) > 25 else r["name"]
        sector  = (r["sector"][:18] + "…") if len(r["sector"]) > 19 else r["sector"]
        print(f"  {bold(r['symbol']):<7}{company:<26}{dim(sector):<20}{r['qty']:>6g}"
              f"{'$' + money(r['buy']):>10}{'$' + money(r['current']):>10}"
              f"{'$' + money(r['market']):>11}{_pl_pct_coloured(r['pl_pct']):>9}{_pl_coloured(r['pl_val']):>11}")

    invested = sum(r["invested"] for r in rows)
    market   = sum(r["market"]  for r in rows)
    pl_val   = market - invested
    pl_pct   = (pl_val / invested) * 100 if invested else 0.0
    best  = max(rows, key=lambda r: r["pl_pct"])
    worst = min(rows, key=lambda r: r["pl_pct"])

    print(dim("  " + "─" * 100))
    print()
    print(f"  Total invested capital : ${bold(money(invested))}")
    print(f"  Current market value   : ${bold(money(market))}")
    print(f"  Overall gain / loss    : {_pl_coloured(pl_val)}  ({_pl_pct_coloured(pl_pct)})")
    print()
    print(f"  Best  performer        : {green(bold(best['symbol']))}  {_pl_pct_coloured(best['pl_pct'])}")
    print(f"  Worst performer        : {red(bold(worst['symbol']))}  {_pl_pct_coloured(worst['pl_pct'])}")
    print()


def write_summary_csv(rows: list) -> Path:
    """Persist the transaction summary to 'portfolio_summary.csv'."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    fieldnames = ["Timestamp", "Symbol", "Company", "Sector", "Quantity",
                  "Buy Price", "Current Price", "Invested Capital",
                  "Market Value", "Profit / Loss", "Profit / Loss %",
                  "Price Source"]
    with _SUMMARY_CSV.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for r in rows:
            writer.writerow({
                "Timestamp":       timestamp,
                "Symbol":          r["symbol"],
                "Company":         r["name"],
                "Sector":          r["sector"],
                "Quantity":        r["qty"],
                "Buy Price":       f"{r['buy']:.2f}",
                "Current Price":   f"{r['current']:.2f}",
                "Invested Capital": f"{r['invested']:.2f}",
                "Market Value":    f"{r['market']:.2f}",
                "Profit / Loss":   f"{r['pl_val']:+.2f}",
                "Profit / Loss %": f"{r['pl_pct']:+.2f}",
                "Price Source":    r["source"],
            })
    return _SUMMARY_CSV


# ──────────────────────────────────────────────────────────────────────────────
# Main loop
# ──────────────────────────────────────────────────────────────────────────────

def menu() -> str:
    """Ask the user for the next action."""
    print(bold("  Menu:  [1] Add stock   [2] View holdings   [3] Generate report & save\n"))
    while True:
        choice = input(bold("  Choose 1 / 2 / 3 → ")).strip()
        if choice in ("1", "2", "3"):
            return choice
        print(red("  Invalid choice – please enter 1, 2, or 3."))


def view_holdings(positions: dict) -> None:
    """Print a quick no-prices overview of the positions entered so far."""
    if not positions:
        print(yellow("  No holdings yet — add a stock first.\n"))
        return
    print()
    print(bold(f"  {'SYMBOL':<8}{'COMPANY':<28}{'QTY':>8}{'AVG BUY':>12}"))
    for symbol, info in positions.items():
        name = (info["name"][:26] + "…") if len(info["name"]) > 27 else info["name"]
        print(f"  {bold(symbol):<8}{dim(name):<28}{info['qty']:>8g}{'$' + money(info['buy_price']):>12}")
    print()


def main() -> None:
    universe = load_universe()
    positions: dict = {}

    print(bold(cyan("""
  ╔════════════════════════════════════════════════╗
  ║        STOCK  PORTFOLIO  PERFORMANCE           ║
  ║                 T R A C K E R                  ║
  ╚════════════════════════════════════════════════╝
""")))
    if universe:
        print(dim(f"  Ticker universe loaded: {len(universe)} S&P 500 symbols.\n"))
    input(dim("  (press Enter to begin)"))

    while True:
        choice = menu()
        if choice == "1":
            add_position(positions, universe)
        elif choice == "2":
            view_holdings(positions)
        else:
            if not positions:
                print(red("\n  Nothing to report – add at least one stock first.\n"))
                continue
            print()
            resolve_prices(positions)
            rows = compute_rows(positions)
            render_report(rows)
            path = write_summary_csv(rows)
            print(green(f"  ✔  Transaction summary saved to: {bold(str(path))}\n"))
            break

    print(cyan(bold("  Thanks for tracking your portfolio!\n")))


if __name__ == "__main__":
    main()
