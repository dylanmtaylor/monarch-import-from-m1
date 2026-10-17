"""Parser for M1 Finance accounts, daily balance histories, and transaction activities."""

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


def slugify(text: str) -> str:
    """Convert a name into a filesystem- and CLI-friendly slug."""
    s = re.sub(r"[^a-zA-Z0-9]+", "_", text).strip("_").lower()
    return s or "account"


@dataclass
class AccountBalancePoint:
    date: str
    balance: float


@dataclass
class AccountTransaction:
    date: str
    merchant: str
    category: str
    account: str
    original_statement: str
    notes: str
    amount: float
    entry_id: str = ""
    entry_type: str = ""


@dataclass
class AccountData:
    account_id: str
    name: str
    slug: str
    is_crypto: bool
    is_retirement: bool
    is_active: bool
    daily_balances: List[AccountBalancePoint] = field(default_factory=list)
    transactions: List[AccountTransaction] = field(default_factory=list)


def parse_daily_balances(chart_data: Optional[Dict[str, Any]]) -> List[AccountBalancePoint]:
    """Parse daily closing balance points from rootPortfolioSlice or netWorth chartData."""
    if not chart_data or not chart_data.get("data"):
        return []

    points: List[AccountBalancePoint] = []
    seen_dates = set()
    for item in chart_data["data"]:
        raw_date = item.get("date", "")
        if not raw_date:
            continue
        date_str = raw_date[:10]  # Extracts YYYY-MM-DD
        close_val = item.get("close")
        if close_val is None:
            continue
        try:
            balance = round(float(close_val), 2)
        except (ValueError, TypeError):
            continue

        if date_str not in seen_dates:
            seen_dates.add(date_str)
            points.append(AccountBalancePoint(date=date_str, balance=balance))

    # Sort chronologically
    points.sort(key=lambda p: p.date)
    return points


def parse_trade_entry(item: Dict[str, Any], account_name: str) -> Optional[AccountTransaction]:
    """Parse an InvestActivityTradeEntry into an AccountTransaction."""
    raw_date = item.get("date", "")
    if not raw_date:
        return None
    date_str = raw_date[:10]

    is_buy = item.get("isBuy", True)
    raw_amount = item.get("amount")
    if raw_amount is None:
        return None
    try:
        amt = float(raw_amount)
    except (ValueError, TypeError):
        return None

    # In Monarch: Cash outflow (Buy) is negative, Cash inflow (Sell) is positive.
    amount = -abs(amt) if is_buy else abs(amt)
    category = "Buy" if is_buy else "Sell"

    trade_sec = item.get("tradeSecurity") or {}
    sec = trade_sec.get("security") or {}
    symbol = sec.get("symbol") or trade_sec.get("descriptor") or ""
    sec_name = sec.get("name") or ""

    merchant = symbol if symbol else "M1 Trade"

    qty = item.get("quantity")
    share_price = item.get("sharePrice")

    # Original Statement
    orig_parts = []
    action_word = "Buy" if is_buy else "Sell"
    orig_parts.append(action_word)
    if qty is not None:
        orig_parts.append(f"{qty:g}" if isinstance(qty, float) else str(qty))
    if symbol:
        orig_parts.append(symbol)
    if share_price is not None:
        orig_parts.append(f"@ ${share_price:.4f}")
    orig_statement = " ".join(orig_parts) if orig_parts else (item.get("title") or action_word)

    # Notes
    note_parts = []
    if sec_name:
        note_parts.append(sec_name)
    if qty is not None:
        note_parts.append(f"Qty: {qty}")
    if share_price is not None:
        note_parts.append(f"Price: ${share_price:.4f}")
    notes = " | ".join(note_parts)

    return AccountTransaction(
        date=date_str,
        merchant=merchant,
        category=category,
        account=account_name,
        original_statement=orig_statement,
        notes=notes,
        amount=amount,
        entry_id=item.get("id", ""),
        entry_type="InvestActivityTradeEntry",
    )


def parse_cash_entry(item: Dict[str, Any], account_name: str) -> Optional[AccountTransaction]:
    """Parse an InvestActivityCashEntry into an AccountTransaction."""
    raw_date = item.get("date", "")
    if not raw_date:
        return None
    date_str = raw_date[:10]

    raw_amount = item.get("amount")
    if raw_amount is None:
        return None
    try:
        amount = float(raw_amount)
    except (ValueError, TypeError):
        return None

    title = item.get("title", "")
    desc = item.get("description", "")
    title_lower = title.lower()

    # Determine category
    if "dividend" in title_lower:
        category = "Dividend"
    elif "deposit" in title_lower or "check" in title_lower:
        category = "Deposit"
    elif "withdrawal" in title_lower:
        category = "Withdrawal"
    elif "interest" in title_lower or "lending" in title_lower:
        category = "Interest"
    elif "reward" in title_lower:
        category = "Credit Card Rewards"
    elif "borrow" in title_lower or "margin" in title_lower:
        category = "Loan Payment"
    elif "conversion" in title_lower or "recharacterization" in title_lower or "transfer" in title_lower:
        category = "Transfer"
    elif "refund" in title_lower:
        category = "Refund"
    elif "fee" in title_lower:
        category = "Fee"
    else:
        category = title or "Cash Activity"

    # Determine merchant
    cash_sec = item.get("cashSecurity") or {}
    sec = cash_sec.get("security") or {}
    symbol = sec.get("symbol") or cash_sec.get("descriptor") or ""
    sec_name = sec.get("name") or ""

    if symbol:
        merchant = symbol
    elif "Axos" in desc or "AXOS" in desc:
        merchant = "Axos Clearing"
    else:
        merchant = "M1 Finance"

    # Original Statement
    orig_statement = desc if desc else (title or "M1 Cash Transaction")

    # Notes
    note_parts = []
    if sec_name:
        note_parts.append(sec_name)
    details = item.get("transferDetails") or {}
    if details.get("transferSummary"):
        note_parts.append(details["transferSummary"])
    if details.get("transferId"):
        note_parts.append(f"Transfer ID: {details['transferId']}")

    notes = " | ".join(note_parts)

    return AccountTransaction(
        date=date_str,
        merchant=merchant,
        category=category,
        account=account_name,
        original_statement=orig_statement,
        notes=notes,
        amount=amount,
        entry_id=item.get("id", ""),
        entry_type="InvestActivityCashEntry",
    )


def parse_position_entry(
    item: Dict[str, Any], account_name: str, include_non_cash: bool = False
) -> Optional[AccountTransaction]:
    """Parse position movements (splits, position transfers)."""
    if not include_non_cash:
        return None

    raw_date = item.get("date", "")
    if not raw_date:
        return None
    date_str = raw_date[:10]

    title = item.get("title", "Position Activity")
    desc = item.get("description", "")
    qty = item.get("quantity")

    pos_sec = item.get("positionSecurity") or {}
    sec = pos_sec.get("security") or {}
    symbol = sec.get("symbol") or pos_sec.get("descriptor") or ""
    sec_name = sec.get("name") or ""

    merchant = symbol if symbol else "M1 Finance"
    category = "Stock Split" if "split" in title.lower() else "Transfer"
    orig_statement = desc if desc else title
    notes = f"{sec_name} | Qty: {qty}" if qty is not None else sec_name

    return AccountTransaction(
        date=date_str,
        merchant=merchant,
        category=category,
        account=account_name,
        original_statement=orig_statement,
        notes=notes,
        amount=0.0,
        entry_id=item.get("id", ""),
        entry_type="InvestActivityPositionEntry",
    )


def parse_activity_item(
    item: Dict[str, Any], account_name: str, include_non_cash: bool = False
) -> Optional[AccountTransaction]:
    """Parse a single activity node based on __typename."""
    typename = item.get("__typename", "")
    if typename == "InvestActivityTradeEntry":
        return parse_trade_entry(item, account_name)
    elif typename == "InvestActivityCashEntry":
        return parse_cash_entry(item, account_name)
    elif typename == "InvestActivityPositionEntry":
        return parse_position_entry(item, account_name, include_non_cash)
    return None


def parse_m1_dataset(
    raw_data: Dict[str, Any], include_non_cash: bool = False
) -> Dict[str, Any]:
    """Parse complete captured M1 JSON payload into structured AccountData objects.

    Args:
        raw_data: Captured M1 dictionary.
        include_non_cash: Whether to include non-cash position entries (splits, etc.).

    Returns:
        Dictionary containing:
            - 'accounts': List[AccountData]
            - 'net_worth_balances': List[AccountBalancePoint]
    """
    raw_accounts = raw_data.get("accounts", [])
    raw_activities = raw_data.get("activities", {})
    raw_net_worth = raw_data.get("net_worth", {})

    parsed_accounts: List[AccountData] = []

    for acc in raw_accounts:
        acc_id = acc.get("id", "")
        acc_name = acc.get("name", "Account")
        acc_slug = slugify(acc_name)

        slice_data = acc.get("rootPortfolioSlice") or {}
        chart_data = slice_data.get("chartData")
        daily_balances = parse_daily_balances(chart_data)

        raw_acc_activities = raw_activities.get(acc_id, [])
        transactions: List[AccountTransaction] = []
        seen_ids = set()

        for act in raw_acc_activities:
            tx = parse_activity_item(act, acc_name, include_non_cash=include_non_cash)
            if tx:
                if tx.entry_id and tx.entry_id in seen_ids:
                    continue
                if tx.entry_id:
                    seen_ids.add(tx.entry_id)
                transactions.append(tx)

        # Sort transactions chronologically
        transactions.sort(key=lambda t: t.date)

        account_obj = AccountData(
            account_id=acc_id,
            name=acc_name,
            slug=acc_slug,
            is_crypto=bool(acc.get("isCryptoAccount")),
            is_retirement=bool(acc.get("isRetirement")),
            is_active=bool(acc.get("isActive", True)),
            daily_balances=daily_balances,
            transactions=transactions,
        )
        parsed_accounts.append(account_obj)

    nw_chart = raw_net_worth.get("chartData")
    net_worth_balances = parse_daily_balances(nw_chart)

    return {
        "accounts": parsed_accounts,
        "net_worth_balances": net_worth_balances,
    }
