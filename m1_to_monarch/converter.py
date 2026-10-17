"""Conversion of parsed M1 data into Monarch Money CSV formats."""

import csv
import io
from typing import Any, Dict, List

from .parser import AccountBalancePoint, AccountData, AccountTransaction

MONARCH_BALANCE_HEADER = ["Date", "Balance"]
MONARCH_TRANSACTIONS_HEADER = [
    "Date",
    "Merchant",
    "Category",
    "Account",
    "Original Statement",
    "Notes",
    "Amount",
]


def balance_points_to_csv(points: List[AccountBalancePoint]) -> str:
    """Format balance points into a Monarch balance history CSV string."""
    output = io.StringIO()
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(MONARCH_BALANCE_HEADER)
    for p in points:
        writer.writerow([p.date, f"{p.balance:.2f}"])
    return output.getvalue()


def transactions_to_csv(transactions: List[AccountTransaction]) -> str:
    """Format account transactions into a Monarch transactions CSV string."""
    output = io.StringIO()
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(MONARCH_TRANSACTIONS_HEADER)
    for t in transactions:
        writer.writerow([
            t.date,
            t.merchant,
            t.category,
            t.account,
            t.original_statement,
            t.notes,
            f"{t.amount:.2f}",
        ])
    return output.getvalue()


def convert_all_data(parsed_data: Dict[str, Any]) -> Dict[str, str]:
    """Convert parsed accounts and net worth data into named CSV files.

    Args:
        parsed_data: Output dictionary from parse_m1_dataset.

    Returns:
        Mapping of filename to CSV content string.
    """
    files: Dict[str, str] = {}
    accounts: List[AccountData] = parsed_data.get("accounts", [])
    net_worth_balances: List[AccountBalancePoint] = parsed_data.get("net_worth_balances", [])

    all_transactions: List[AccountTransaction] = []

    for acc in accounts:
        # Per-account daily balance history
        if acc.daily_balances:
            bal_filename = f"m1_{acc.slug}_monarch_balance_history.csv"
            files[bal_filename] = balance_points_to_csv(acc.daily_balances)

        # Per-account transactions
        if acc.transactions:
            tx_filename = f"m1_{acc.slug}_monarch_transactions.csv"
            files[tx_filename] = transactions_to_csv(acc.transactions)
            all_transactions.extend(acc.transactions)

    # Combined transactions across all accounts
    if all_transactions:
        # Sort combined chronologically
        all_transactions.sort(key=lambda t: t.date)
        files["m1_all_accounts_monarch_transactions.csv"] = transactions_to_csv(all_transactions)

    # Net worth daily balance history
    if net_worth_balances:
        files["m1_net_worth_monarch_balance_history.csv"] = balance_points_to_csv(net_worth_balances)

    return files
