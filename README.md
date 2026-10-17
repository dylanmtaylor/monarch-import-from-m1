# Monarch Import from M1 Finance

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)
[![Monarch Money](https://img.shields.io/badge/Monarch%20Money-Compatible-blueviolet.svg)](https://www.monarchmoney.com/)

An automated command-line utility to extract all **M1 Finance** accounts—including continuous **daily balance histories**, itemized trade executions, dividends, deposits, and transfers—into CSV files formatted specifically for import into **[Monarch Money](https://www.monarchmoney.com/)**.

---

## 🌟 Why This Exists

While M1 Finance provides monthly statement PDFs, monthly snapshots miss intraday market volatility, daily balance trends, and granular transaction details. Furthermore, downloading multiple PDFs across several accounts (Taxable, Roth IRA, Traditional IRA, Beneficiary IRA, Crypto) is tedious.

Behind the scenes, M1's web platform (`dashboard.m1.com`) connects to an internal GraphQL API (`lens.m1.com`) that records:
1. **Continuous Daily Closing Balances**: Exact daily closing valuations for every account from inception to the present day.
2. **Itemized Investment Activities**: Full order executions (ticker symbol, share quantity, executed price, and total amount), dividends, deposits, withdrawals, and margin payments.

This tool automates connecting to your active authenticated M1 browser session via Chrome DevTools Protocol (CDP), queries the GraphQL API, and converts all accounts into Monarch-compatible CSVs in seconds.

---

## 🚀 Key Features

- 🏦 **All Accounts Supported**: Automatically discovers and processes all accounts in your M1 profile (Taxable Individual/Joint Brokerage, Roth IRA, Traditional IRA, Beneficiary/Inherited IRA, Crypto, and Margin).
- 📈 **Continuous Daily Balance History**: Generates per-account `m1_{account}_monarch_balance_history.csv` files with daily closing balances going back years, eliminating gaps in Monarch net worth charts.
- 🌐 **Net Worth Daily History**: Generates `m1_net_worth_monarch_balance_history.csv` reflecting your total portfolio value over time.
- ⚡ **Granular Trade Disaggregation**: Uses M1's `neverSummarizeTrades: true` GraphQL capability to decompose trade summaries (e.g. "Morning Trading") into itemized executions with exact tickers, share counts, and unit prices.
- 💳 **Monarch Cashflow Conventions**: Properly formats asset transaction signs (negative for buys and withdrawals; positive for sells, dividends, interest, and deposits).
- 🤖 **Zero-Configuration Browser Capture**: Connects directly to your running Chrome instance via CDP (`--remote-debugging-port=9222`) to retrieve the Auth0 session token automatically.
- 🔒 **Privacy & Security First**: All generated `.csv` and raw `.json` files are excluded by `.gitignore`. Test fixtures use 100% synthetic mock data.

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────┐
│       Chrome Browser (Authenticated)    │
│           dashboard.m1.com              │
└────────────────────┬────────────────────┘
                     │ Chrome DevTools Protocol (CDP)
                     ▼
┌─────────────────────────────────────────┐
│         m1-to-monarch capture           │
│   (Auth0 Token -> lens.m1.com GraphQL)  │
└────────────────────┬────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────┐
│            m1_raw_data.json             │
│   (Raw accounts, balances & activities) │
└────────────────────┬────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────┐
│         m1-to-monarch convert           │
│   (Parses & normalizes to Monarch CSV)  │
└────────────────────┬────────────────────┘
                     │
     ┌───────────────┴─────────────────────────────┐
     ▼                                             ▼
┌──────────────────────────────────┐ ┌──────────────────────────────────┐
│ Balance History CSVs             │ │ Transactions CSVs                │
│ • m1_investment_balance_...csv   │ │ • m1_investment_transactions.csv│
│ • m1_roth_ira_balance_...csv     │ │ • m1_roth_ira_transactions.csv  │
│ • m1_beneficiary_ira_...csv      │ │ • m1_beneficiary_ira_...csv     │
│ • m1_crypto_balance_...csv       │ │ • m1_crypto_transactions.csv     │
│ • m1_net_worth_balance_...csv    │ │ • m1_all_accounts_...csv        │
└──────────────────────────────────┘ └──────────────────────────────────┘
```

---

## 💻 Installation

### 1. Clone the repository
```bash
git clone https://github.com/dylanmtaylor/monarch-import-from-m1.git
cd monarch-import-from-m1
```

### 2. Install dependencies
```bash
pip install -e .
```
*(Requires Python 3.8+ and `websocket-client`)*

---

## 📖 Quick Start

### Step 1: Launch Chrome with Remote Debugging
Launch Google Chrome with remote debugging enabled:

**Linux:**
```bash
google-chrome --remote-debugging-port=9222
# or flatpak:
flatpak run com.google.Chrome --remote-debugging-port=9222
```

**macOS:**
```bash
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome --remote-debugging-port=9222
```

**Windows:**
```cmd
"C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222
```

### Step 2: Log into M1 Finance
Navigate to [dashboard.m1.com](https://dashboard.m1.com) and log in with your credentials (and 2FA).

### Step 3: Run Extraction & Conversion
Execute the CLI tool in one seamless command:
```bash
m1-to-monarch all
```

Or run step-by-step:
```bash
# 1. Capture raw data from M1 GraphQL API
m1-to-monarch capture --raw-output m1_raw_data.json

# 2. Convert raw data into Monarch CSVs
m1-to-monarch convert --input m1_raw_data.json --output-dir output
```

---

## 📂 Output Files

All output files are saved to the `output/` directory:

| Filename | Type | Description |
|:---|:---|:---|
| `m1_{account}_monarch_balance_history.csv` | Balance History | Exact daily closing balances from account inception to present (`Date,Balance`). |
| `m1_{account}_monarch_transactions.csv` | Transactions | Itemized buys, sells, dividends, transfers, and deposits for that specific account. |
| `m1_all_accounts_monarch_transactions.csv` | Transactions | Combined chronological transaction ledger across all accounts. |
| `m1_net_worth_monarch_balance_history.csv` | Balance History | Aggregated total portfolio daily closing valuation. |

### Monarch Transactions CSV Schema
```csv
Date,Merchant,Category,Account,Original Statement,Notes,Amount
2026-10-12,M1 Finance,Deposit,Investment,Deposit of $250.00 completed.,,250.00
2026-10-12,VXUS,Buy,Investment,Buy 2.95347 VXUS @ $84.6463,Vanguard Total International Stock ETF | Qty: 2.95347 | Price: $84.6463,-250.00
2026-10-05,BNDX,Dividend,Investment,Dividend,Vanguard Total International Bond ETF,21.36
2026-06-15,SCHF,Sell,Investment,Sell 100 SCHF @ $19.1600,Schwab International Equity ETF | Qty: 100 | Price: $19.1600,1916.00
```

### Monarch Balance History CSV Schema
```csv
Date,Balance
2022-09-26,0.00
2022-09-27,95.59
...
2026-10-16,625763.92
2026-10-17,625763.92
```

---

## 📥 How to Import into Monarch Money

1. In Monarch Money, navigate to **Accounts**.
2. Select your M1 Finance account (or create a manual account if not synced).
3. Click **Edit** (gear icon) in the top right.
4. **Import Balance History**:
   - Select **Upload balance history**.
   - Choose the corresponding `m1_{account}_monarch_balance_history.csv`.
5. **Import Transactions**:
   - Select **Upload transactions**.
   - Choose the corresponding `m1_{account}_monarch_transactions.csv`.

---

## 🧪 Running Tests

The test suite runs with Python's built-in `unittest` or `pytest`:
```bash
python3 -m unittest discover -v tests
```

---

## 🛡️ Privacy & Security

- Your M1 credentials are never requested or stored. The tool retrieves an ephemeral session token from your own local browser session via CDP.
- All network requests communicate exclusively with official endpoints: `localhost:9222` and `https://lens.m1.com/graphql`.
- No telemetry, analytics, or external calls.

---

## 📄 License

This project is open-source under the [MIT License](LICENSE).
