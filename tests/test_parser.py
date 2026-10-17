"""Unit tests for parser module."""

import unittest
from m1_to_monarch.parser import (
    parse_cash_entry,
    parse_daily_balances,
    parse_m1_dataset,
    parse_position_entry,
    parse_trade_entry,
    slugify,
)


class TestParser(unittest.TestCase):
    def test_slugify(self):
        self.assertEqual(slugify("Investment"), "investment")
        self.assertEqual(slugify("Roth IRA"), "roth_ira")
        self.assertEqual(slugify("Beneficiary IRA - 2024"), "beneficiary_ira_2024")
        self.assertEqual(slugify("Crypto & DeFi!"), "crypto_defi")

    def test_parse_daily_balances(self):
        chart_data = {
            "data": [
                {"date": "2024-01-02T20:00:00.000Z", "close": 10500.50},
                {"date": "2024-01-01T20:00:00.000Z", "close": 10000.00},
                {"date": "2024-01-02T22:00:00.000Z", "close": 10500.50},  # duplicate date
            ]
        }
        points = parse_daily_balances(chart_data)
        self.assertEqual(len(points), 2)
        # Chronological sort check
        self.assertEqual(points[0].date, "2024-01-01")
        self.assertEqual(points[0].balance, 10000.00)
        self.assertEqual(points[1].date, "2024-01-02")
        self.assertEqual(points[1].balance, 10500.50)

    def test_parse_trade_entry_buy(self):
        item = {
            "id": "trade-1",
            "isBuy": True,
            "quantity": 2.5,
            "sharePrice": 100.0,
            "amount": 250.0,
            "date": "2024-05-10T09:30:00-04:00",
            "title": "Buy",
            "tradeSecurity": {
                "descriptor": "VTI",
                "security": {"symbol": "VTI", "name": "Vanguard Total Stock Market ETF"},
            },
        }
        tx = parse_trade_entry(item, "Investment")
        self.assertIsNotNone(tx)
        self.assertEqual(tx.date, "2024-05-10")
        self.assertEqual(tx.merchant, "VTI")
        self.assertEqual(tx.category, "Buy")
        self.assertEqual(tx.account, "Investment")
        self.assertEqual(tx.amount, -250.0)  # Cash outflow is negative
        self.assertIn("Buy 2.5 VTI @ $100.0000", tx.original_statement)
        self.assertIn("Vanguard Total Stock Market ETF", tx.notes)

    def test_parse_trade_entry_sell(self):
        item = {
            "id": "trade-2",
            "isBuy": False,
            "quantity": 10.0,
            "sharePrice": 50.0,
            "amount": 500.0,
            "date": "2024-06-15T10:00:00-04:00",
            "title": "Sell",
            "tradeSecurity": {
                "descriptor": "VXUS",
                "security": {"symbol": "VXUS", "name": "Vanguard Total International Stock ETF"},
            },
        }
        tx = parse_trade_entry(item, "Roth IRA")
        self.assertIsNotNone(tx)
        self.assertEqual(tx.amount, 500.0)  # Cash inflow is positive
        self.assertEqual(tx.category, "Sell")
        self.assertEqual(tx.merchant, "VXUS")
        self.assertIn("Sell 10 VXUS @ $50.0000", tx.original_statement)

    def test_parse_cash_entry_dividend(self):
        item = {
            "id": "cash-1",
            "title": "Dividend",
            "description": "Dividend payment",
            "amount": 42.50,
            "date": "2024-03-31T00:00:00-04:00",
            "cashSecurity": {
                "descriptor": "BNDX",
                "security": {"symbol": "BNDX", "name": "Vanguard Total International Bond ETF"},
            },
        }
        tx = parse_cash_entry(item, "Investment")
        self.assertIsNotNone(tx)
        self.assertEqual(tx.date, "2024-03-31")
        self.assertEqual(tx.category, "Dividend")
        self.assertEqual(tx.merchant, "BNDX")
        self.assertEqual(tx.amount, 42.50)

    def test_parse_cash_entry_deposit_and_withdrawal(self):
        dep = {
            "id": "cash-dep",
            "title": "Deposit",
            "description": "Deposit of $500.00 completed.",
            "amount": 500.0,
            "date": "2024-02-01T12:00:00-05:00",
        }
        tx_dep = parse_cash_entry(dep, "Investment")
        self.assertEqual(tx_dep.category, "Deposit")
        self.assertEqual(tx_dep.amount, 500.0)

        withd = {
            "id": "cash-w",
            "title": "Withdrawal",
            "description": "Withdrawal of $1000.00",
            "amount": -1000.0,
            "date": "2024-02-15T12:00:00-05:00",
        }
        tx_w = parse_cash_entry(withd, "Investment")
        self.assertEqual(tx_w.category, "Withdrawal")
        self.assertEqual(tx_w.amount, -1000.0)

    def test_parse_position_entry_toggle(self):
        split = {
            "id": "pos-split",
            "title": "Stock split",
            "description": "Forward stock split 10:1",
            "date": "2024-06-10T00:00:00-04:00",
            "quantity": 100,
            "positionSecurity": {
                "descriptor": "NVDA",
                "security": {"symbol": "NVDA", "name": "NVIDIA Corporation"},
            },
        }
        self.assertIsNone(parse_position_entry(split, "Investment", include_non_cash=False))
        tx = parse_position_entry(split, "Investment", include_non_cash=True)
        self.assertIsNotNone(tx)
        self.assertEqual(tx.category, "Stock Split")
        self.assertEqual(tx.merchant, "NVDA")
        self.assertEqual(tx.amount, 0.0)

    def test_parse_m1_dataset(self):
        raw_data = {
            "accounts": [
                {
                    "id": "acc-1",
                    "name": "Taxable Investment",
                    "isCryptoAccount": False,
                    "isRetirement": False,
                    "isActive": True,
                    "rootPortfolioSlice": {
                        "chartData": {
                            "data": [
                                {"date": "2024-01-01T20:00:00.000Z", "close": 50000.0},
                                {"date": "2024-01-02T20:00:00.000Z", "close": 51000.0},
                            ]
                        }
                    },
                }
            ],
            "activities": {
                "acc-1": [
                    {
                        "__typename": "InvestActivityTradeEntry",
                        "id": "t-1",
                        "isBuy": True,
                        "quantity": 10,
                        "sharePrice": 100,
                        "amount": 1000,
                        "date": "2024-01-02T09:30:00-05:00",
                        "tradeSecurity": {
                            "descriptor": "VTI",
                            "security": {"symbol": "VTI", "name": "Vanguard Total Stock"},
                        },
                    }
                ]
            },
            "net_worth": {
                "chartData": {
                    "data": [
                        {"date": "2024-01-01T00:00:00.000Z", "close": 50000.0},
                    ]
                }
            },
        }

        parsed = parse_m1_dataset(raw_data)
        accounts = parsed["accounts"]
        self.assertEqual(len(accounts), 1)
        acc = accounts[0]
        self.assertEqual(acc.name, "Taxable Investment")
        self.assertEqual(acc.slug, "taxable_investment")
        self.assertEqual(len(acc.daily_balances), 2)
        self.assertEqual(len(acc.transactions), 1)
        self.assertEqual(acc.transactions[0].amount, -1000.0)
        self.assertEqual(len(parsed["net_worth_balances"]), 1)


if __name__ == "__main__":
    unittest.main()
