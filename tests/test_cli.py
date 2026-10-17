"""Unit tests for CLI interface."""

import json
import os
import tempfile
import unittest
from m1_to_monarch.cli import main


class TestCLI(unittest.TestCase):
    def test_cli_convert_with_synthetic_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            input_json = os.path.join(tmpdir, "test_input.json")
            output_dir = os.path.join(tmpdir, "output")

            synthetic_data = {
                "accounts": [
                    {
                        "id": "acc-test",
                        "name": "Taxable Test",
                        "isCryptoAccount": False,
                        "isRetirement": False,
                        "isActive": True,
                        "rootPortfolioSlice": {
                            "chartData": {
                                "data": [
                                    {"date": "2024-01-01T20:00:00.000Z", "close": 1234.56}
                                ]
                            }
                        },
                    }
                ],
                "activities": {
                    "acc-test": [
                        {
                            "__typename": "InvestActivityCashEntry",
                            "id": "c-1",
                            "title": "Deposit",
                            "description": "Initial deposit",
                            "amount": 1000.0,
                            "date": "2024-01-01T12:00:00-05:00",
                        }
                    ]
                },
                "net_worth": {
                    "chartData": {
                        "data": [
                            {"date": "2024-01-01T00:00:00.000Z", "close": 1234.56}
                        ]
                    }
                },
            }

            with open(input_json, "w", encoding="utf-8") as f:
                json.dump(synthetic_data, f)

            exit_code = main([
                "convert",
                "--input", input_json,
                "--output-dir", output_dir,
            ])

            self.assertEqual(exit_code, 0)
            self.assertTrue(os.path.exists(output_dir))
            files = os.listdir(output_dir)
            self.assertIn("m1_taxable_test_monarch_balance_history.csv", files)
            self.assertIn("m1_taxable_test_monarch_transactions.csv", files)
            self.assertIn("m1_all_accounts_monarch_transactions.csv", files)
            self.assertIn("m1_net_worth_monarch_balance_history.csv", files)


if __name__ == "__main__":
    unittest.main()
