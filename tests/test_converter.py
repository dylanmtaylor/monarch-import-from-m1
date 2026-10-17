"""Unit tests for converter module."""

import unittest
from m1_to_monarch.converter import (
    MONARCH_BALANCE_HEADER,
    MONARCH_TRANSACTIONS_HEADER,
    balance_points_to_csv,
    convert_all_data,
    transactions_to_csv,
)
from m1_to_monarch.parser import AccountBalancePoint, AccountData, AccountTransaction


class TestConverter(unittest.TestCase):
    def test_balance_points_to_csv(self):
        points = [
            AccountBalancePoint(date="2024-01-01", balance=12345.67),
            AccountBalancePoint(date="2024-01-02", balance=12400.00),
        ]
        csv_str = balance_points_to_csv(points)
        lines = [line.strip() for line in csv_str.strip().split("\n")]
        self.assertEqual(lines[0], ",".join(MONARCH_BALANCE_HEADER))
        self.assertEqual(lines[1], "2024-01-01,12345.67")
        self.assertEqual(lines[2], "2024-01-02,12400.00")

    def test_transactions_to_csv(self):
        txs = [
            AccountTransaction(
                date="2024-05-10",
                merchant="VTI",
                category="Buy",
                account="Investment",
                original_statement="Buy 2.5 VTI @ $100.0000",
                notes="Vanguard Total Stock Market ETF | Qty: 2.5 | Price: $100.0000",
                amount=-250.00,
            )
        ]
        csv_str = transactions_to_csv(txs)
        lines = [line.strip() for line in csv_str.strip().split("\n")]
        self.assertEqual(lines[0], ",".join(MONARCH_TRANSACTIONS_HEADER))
        self.assertIn("2024-05-10,VTI,Buy,Investment,Buy 2.5 VTI @ $100.0000", lines[1])
        self.assertTrue(lines[1].endswith(",-250.00"))

    def test_convert_all_data(self):
        acc1 = AccountData(
            account_id="acc-1",
            name="Investment",
            slug="investment",
            is_crypto=False,
            is_retirement=False,
            is_active=True,
            daily_balances=[AccountBalancePoint(date="2024-01-01", balance=1000.0)],
            transactions=[
                AccountTransaction(
                    date="2024-01-01",
                    merchant="VTI",
                    category="Buy",
                    account="Investment",
                    original_statement="Buy VTI",
                    notes="",
                    amount=-100.0,
                )
            ],
        )
        acc2 = AccountData(
            account_id="acc-2",
            name="Roth IRA",
            slug="roth_ira",
            is_crypto=False,
            is_retirement=True,
            is_active=True,
            daily_balances=[AccountBalancePoint(date="2024-01-01", balance=2000.0)],
            transactions=[
                AccountTransaction(
                    date="2024-01-02",
                    merchant="VXUS",
                    category="Buy",
                    account="Roth IRA",
                    original_statement="Buy VXUS",
                    notes="",
                    amount=-200.0,
                )
            ],
        )

        parsed_data = {
            "accounts": [acc1, acc2],
            "net_worth_balances": [
                AccountBalancePoint(date="2024-01-01", balance=3000.0)
            ],
        }

        files = convert_all_data(parsed_data)

        # Expected files:
        # - m1_investment_monarch_balance_history.csv
        # - m1_investment_monarch_transactions.csv
        # - m1_roth_ira_monarch_balance_history.csv
        # - m1_roth_ira_monarch_transactions.csv
        # - m1_all_accounts_monarch_transactions.csv
        # - m1_net_worth_monarch_balance_history.csv
        self.assertIn("m1_investment_monarch_balance_history.csv", files)
        self.assertIn("m1_investment_monarch_transactions.csv", files)
        self.assertIn("m1_roth_ira_monarch_balance_history.csv", files)
        self.assertIn("m1_roth_ira_monarch_transactions.csv", files)
        self.assertIn("m1_all_accounts_monarch_transactions.csv", files)
        self.assertIn("m1_net_worth_monarch_balance_history.csv", files)

        # Verify combined file contains both accounts
        combined = files["m1_all_accounts_monarch_transactions.csv"]
        self.assertIn("Investment", combined)
        self.assertIn("Roth IRA", combined)


if __name__ == "__main__":
    unittest.main()
