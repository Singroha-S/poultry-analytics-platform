import datetime
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
FILE = ROOT / "data" / "Daily Report.xlsx"

if not FILE.exists():
    raise FileNotFoundError(f"Data file not found: {FILE}")

# Sheets to exclude
EXCLUDE_SHEETS = {
    "Bird Weight",
    "TRAY WEIGHT",
    "Sale",
    "Final",
    "Sheet20",
    "Sheet21",
    "Sheet13",
    "Sheet18",
    "Sheet17",
    "Sheet16",
    "Sheet15",
}

# Get all sheets
all_sheets = pd.ExcelFile(FILE).sheet_names
sheets_to_process = [s for s in all_sheets if s not in EXCLUDE_SHEETS and s.strip()]

print(f"Processing {len(sheets_to_process)} sheets: {sheets_to_process}\n")

# Combine records from all sheets
all_records = []

for sheet_name in sheets_to_process:
    print(f"Processing: {sheet_name}")

    df = pd.read_excel(
        FILE,
        sheet_name=sheet_name,
        header=None
    )

    records = []
    row = 0

    while row < len(df):

        row_values = df.iloc[row, :5].tolist()
        date_cells = [
            v for v in row_values
            if isinstance(v, (pd.Timestamp, datetime.datetime, datetime.date))
        ]

        # date rows
        if date_cells:

            # Parse date with dayfirst=True to correctly interpret dates like 05/06/2026 as 5 June 2026
            report_date = pd.to_datetime(date_cells[0], dayfirst=True)

            shed_names = (
                df.iloc[row + 1, 1:5]
                .tolist()
            )

            metrics = {}

            for r in range(row + 2, row + 12):

                metric_name = str(df.iloc[r, 0]).strip()

                metric_values = (
                    df.iloc[r, 1:5]
                    .tolist()
                )

                metrics[metric_name] = metric_values

            for i, shed in enumerate(shed_names):

                records.append({
                    "Date": report_date,
                    "Shed": shed,
                    "Age": metrics.get("Age", [None]*4)[i],
                    "Mortality": metrics.get("Mortality", [None]*4)[i],
                    "Bird_Balance": metrics.get("Bird Balance", [None]*4)[i],
                    "Fresh_Eggs": metrics.get("Fresh Eggs", [None]*4)[i],
                    "Crack_Eggs": metrics.get("Crack Eggs", [None]*4)[i],
                    "Leaker_Eggs": metrics.get("Leaker Eggs", [None]*4)[i],
                    "Jumbo_Tray": metrics.get("Jumbo Tray", [None]*4)[i],
                    "Production_Pct": metrics.get("Production %", [None]*4)[i],
                    "Fresh_Tray": metrics.get("Fresh Tray", [None]*4)[i],
                })

        row += 1

    all_records.extend(records)
    print(f"  → Extracted {len(records)} records\n")

# Combine all into one DataFrame
combined_df = pd.DataFrame(all_records)

# Save combined output
output_dir = ROOT / "output"
output_dir.mkdir(parents=True, exist_ok=True)
output_file = output_dir / "all_reports_combined.csv"

combined_df.to_csv(output_file, index=False)

print(f"\n{'='*60}")
print(f"Total records: {len(combined_df)}")
print(f"Date range: {combined_df['Date'].min()} to {combined_df['Date'].max()}")
print(f"Saved to: {output_file}")
print(f"{'='*60}")
print(combined_df.head(10))
