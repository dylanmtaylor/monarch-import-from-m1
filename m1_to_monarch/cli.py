"""Command Line Interface for M1 Finance to Monarch Money tool."""

import argparse
import json
import os
import sys
from typing import Optional

from .capture import (
    M1CaptureError,
    extract_token_from_chrome,
    fetch_all_m1_data,
    save_captured_data,
)
from .converter import convert_all_data
from .exporter import export_csv_files, print_export_summary
from .parser import parse_m1_dataset


def run_capture(args: argparse.Namespace) -> int:
    """Execute the capture subcommand."""
    print("Starting M1 Finance automated browser extraction...")
    try:
        data = fetch_all_m1_data(
            token=args.token,
            port=args.port,
            progress_callback=print,
        )
        save_captured_data(data, args.raw_output)
        print(f"\nSuccessfully saved captured raw data to: {os.path.abspath(args.raw_output)}")
        return 0
    except M1CaptureError as e:
        print(f"\n[ERROR] Capture failed: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"\n[UNEXPECTED ERROR] {e}", file=sys.stderr)
        return 2


def run_convert(args: argparse.Namespace) -> int:
    """Execute the convert subcommand."""
    if not os.path.exists(args.input):
        print(f"[ERROR] Input file not found: {args.input}", file=sys.stderr)
        return 1

    print(f"Reading captured data from: {args.input}")
    try:
        with open(args.input, "r", encoding="utf-8") as f:
            raw_data = json.load(f)
    except Exception as e:
        print(f"[ERROR] Failed to read JSON from {args.input}: {e}", file=sys.stderr)
        return 1

    print("Parsing accounts, daily closing balances, and activities...")
    parsed_data = parse_m1_dataset(raw_data, include_non_cash=args.include_non_cash)

    accounts = parsed_data["accounts"]
    print(f"Found {len(accounts)} accounts in dataset:")
    for acc in accounts:
        print(
            f"  - {acc.name} ({acc.slug}): "
            f"{len(acc.daily_balances):,} daily balance points, "
            f"{len(acc.transactions):,} transactions"
        )

    print("\nGenerating Monarch CSV files...")
    csv_files = convert_all_data(parsed_data)

    print(f"Writing CSV files to {os.path.abspath(args.output_dir)}...")
    written = export_csv_files(csv_files, output_dir=args.output_dir)

    print_export_summary(written)
    return 0


def run_all(args: argparse.Namespace) -> int:
    """Execute capture followed by convert."""
    print("Step 1/2: Capturing data from M1 Finance...")
    try:
        data = fetch_all_m1_data(
            token=args.token,
            port=args.port,
            progress_callback=print,
        )
        save_captured_data(data, args.raw_output)
        print(f"Raw data saved to {os.path.abspath(args.raw_output)}")
    except M1CaptureError as e:
        print(f"\n[ERROR] Capture failed: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"\n[UNEXPECTED ERROR] {e}", file=sys.stderr)
        return 2

    print("\nStep 2/2: Converting captured data to Monarch CSVs...")
    args.input = args.raw_output
    return run_convert(args)


def main(argv: Optional[list] = None) -> int:
    """Main CLI entrypoint."""
    parser = argparse.ArgumentParser(
        prog="m1-to-monarch",
        description="Extract M1 Finance transactions and daily balances into Monarch Money CSVs.",
    )
    subparsers = parser.add_subparsers(dest="subcommand", help="Subcommand to run")

    # Capture command
    parser_cap = subparsers.add_parser("capture", help="Capture raw data from M1 Finance")
    parser_cap.add_argument(
        "--port",
        type=int,
        default=9222,
        help="Chrome remote debugging port (default: 9222)",
    )
    parser_cap.add_argument(
        "--token",
        type=str,
        default=None,
        help="M1 Auth0 Bearer token override",
    )
    parser_cap.add_argument(
        "--raw-output",
        type=str,
        default="m1_raw_data.json",
        help="Output JSON file for captured data (default: m1_raw_data.json)",
    )

    # Convert command
    parser_conv = subparsers.add_parser("convert", help="Convert raw JSON to Monarch CSVs")
    parser_conv.add_argument(
        "--input",
        type=str,
        default="m1_raw_data.json",
        help="Path to captured JSON file (default: m1_raw_data.json)",
    )
    parser_conv.add_argument(
        "--output-dir",
        type=str,
        default="output",
        help="Output directory for generated CSVs (default: output)",
    )
    parser_conv.add_argument(
        "--include-non-cash",
        action="store_true",
        help="Include non-cash position movements such as stock splits and position transfers",
    )

    # All command
    parser_all = subparsers.add_parser("all", help="Capture and convert in one operation")
    parser_all.add_argument(
        "--port",
        type=int,
        default=9222,
        help="Chrome remote debugging port (default: 9222)",
    )
    parser_all.add_argument(
        "--token",
        type=str,
        default=None,
        help="M1 Auth0 Bearer token override",
    )
    parser_all.add_argument(
        "--raw-output",
        type=str,
        default="m1_raw_data.json",
        help="Output JSON file for captured data (default: m1_raw_data.json)",
    )
    parser_all.add_argument(
        "--output-dir",
        type=str,
        default="output",
        help="Output directory for generated CSVs (default: output)",
    )
    parser_all.add_argument(
        "--include-non-cash",
        action="store_true",
        help="Include non-cash position movements such as stock splits and position transfers",
    )

    # If no subcommand passed, default to 'all'
    if argv is None:
        argv = sys.argv[1:]

    if not argv or argv[0] not in ("capture", "convert", "all", "-h", "--help"):
        argv = ["all"] + argv

    args = parser.parse_args(argv)

    if args.subcommand == "capture":
        return run_capture(args)
    elif args.subcommand == "convert":
        return run_convert(args)
    elif args.subcommand == "all":
        return run_all(args)
    else:
        parser.print_help()
        return 0


if __name__ == "__main__":
    sys.exit(main())
