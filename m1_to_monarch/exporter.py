"""File export and reporting for generated Monarch Money CSVs."""

import os
from typing import Dict, List, Optional


def export_csv_files(
    csv_files: Dict[str, str],
    output_dir: str = "output",
) -> List[str]:
    """Write generated CSV files to disk.

    Args:
        csv_files: Mapping of filename to CSV content string.
        output_dir: Output directory path.

    Returns:
        List of absolute file paths written.
    """
    os.makedirs(output_dir, exist_ok=True)
    written_paths: List[str] = []

    for filename, content in sorted(csv_files.items()):
        filepath = os.path.join(output_dir, filename)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        written_paths.append(os.path.abspath(filepath))

    return written_paths


def print_export_summary(written_paths: List[str]) -> None:
    """Print a clean terminal summary of exported files."""
    print("\n" + "=" * 78)
    print("M1 Finance -> Monarch Money Export Summary")
    print("=" * 78)

    for path in written_paths:
        filename = os.path.basename(path)
        with open(path, "r", encoding="utf-8") as f:
            lines = [line.strip() for line in f if line.strip()]

        data_rows = max(0, len(lines) - 1)
        if data_rows > 0:
            first_row = lines[1].split(",")
            last_row = lines[-1].split(",")
            start_date = first_row[0]
            end_date = last_row[0]
            date_range = f"{start_date} to {end_date}"
        else:
            date_range = "N/A"

        kind = "Balance History" if "balance_history" in filename else "Transactions"
        print(f"  • {filename}")
        print(f"      Type:       {kind}")
        print(f"      Rows:       {data_rows:,}")
        print(f"      Range:      {date_range}")
        print(f"      Path:       {path}")
        print()

    print("=" * 78)
    print(f"Successfully exported {len(written_paths)} CSV file(s).")
    print("Ready to import directly into Monarch Money!")
    print("=" * 78 + "\n")
