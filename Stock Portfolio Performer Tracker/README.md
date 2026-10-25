# Stock Portfolio Performance Tracker

A console-based investment portfolio utility — enter your stock holdings, get a real-time valuation, and automatically log the results to CSV.

## How It Works

- Ticker symbols are validated against the bundled **S&P 500 constituents dataset** (`constituents.csv` — symbol, company, sector).
- You enter each holding's **ticker, buy price, and share quantity**; positions are stored in a **dictionary** keyed by symbol.
- The script fetches **live prices from Yahoo Finance** (free chart endpoint, no API key, standard library only). If the network is unavailable it gracefully falls back to **manual price entry**.
- Adding more shares of the same ticker **updates the position with a weighted-average buy price**.
- It computes **invested capital vs current market value**, per-holding gain/loss, overall P/L, and best/worst performers.
- The transaction summary is written to **`portfolio_summary.csv`** with Python's built-in `csv` module.

## Sample Console Output

```
  SYMBOL COMPANY                   SECTOR                    QTY       BUY       NOW      VALUE    P/L %      P/L $
  ────────────────────────────────────────────────────────────────────────────────────────────────────
  AAPL   Apple Inc.                Information Technology   180.2   $14.99   $222.49  $40,092.70  +1383.82%  +37,390.70
  MSFT   Microsoft                 Information Technology   320.5    $5.00   $350.98 $112,489.09  +6919.60% +110,886.59

  Total invested capital : $4,304.50
  Current market value   : $152,581.79
  Overall gain / loss    : +148,277.29  (+3444.70%)
```

## Portfolio Summary CSV

Each report run writes/refreshes `portfolio_summary.csv` with one row per holding:

| Timestamp | Symbol | Company | Sector | Quantity | Buy Price | Current Price | Invested Capital | Market Value | Profit / Loss | Profit / Loss % | Price Source |
|-----------|--------|---------|--------|----------|-----------|---------------|------------------|--------------|---------------|-----------------|--------------|

## Getting Started

**Requirements:** Python 3 (standard library only — no external packages, internet optional)

```bash
git clone https://github.com/Divyanshu11007/Datheon-Python-Internship.git
cd "Datheon-Python-Internship/Stock Portfolio Performer Tracker"
python portfolio.py
```

## Project Structure

```
Stock Portfolio Performer Tracker/
├── portfolio.py            # Main script — entry, valuation, CSV logging
├── constituents.csv        # S&P 500 ticker dataset (validation + metadata)
└── portfolio_summary.csv   # Generated performance log (from last run)
```

## Built With

- Python 3 — `csv`, `urllib.request`, `datetime`, `pathlib`
- File I/O + `csv` module for persistence
