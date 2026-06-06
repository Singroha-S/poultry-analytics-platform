import datetime
import os
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
FILE = ROOT / "data" / "Daily Report.xlsx"

if not FILE.exists():
    raise FileNotFoundError(f"Data file not found: {FILE}")

df = pd.read_excel(
    FILE,
    sheet_name="june26",
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

        report_date = pd.to_datetime(date_cells[0])

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

clean_df = pd.DataFrame(records)

output_dir = ROOT / "output"
output_dir.mkdir(parents=True, exist_ok=True)
output_file = output_dir / "june26_clean.csv"

clean_df.to_csv(output_file, index=False)

print(clean_df.head())
print()
print("Rows:", len(clean_df))
print(f"Saved: {output_file}")