import datetime
import io
import os
import sys
from pathlib import Path

import pandas as pd
import requests
import re
import numpy as np

try:
    from dotenv import load_dotenv
    # Use an absolute path to find the .env file in the project root
    env_path = Path(__file__).resolve().parents[1] / ".env"
    if env_path.exists():
        load_dotenv(dotenv_path=env_path)
    else:
        print("Warning: .env file not found.")
except ImportError:
    print("Warning: 'python-dotenv' not installed. Environment variables must be set manually.")

ROOT = Path(__file__).resolve().parents[1]
FILE = ROOT / "data" / "Daily Report.xlsx"

# Note: process all sheets; user has removed empty sheets from the workbook


def _fetch_workbook_from_gsheets(sheet_id: str) -> pd.ExcelFile:
    """Download the entire workbook as an XLSX from Google Sheets using a service account and return a pandas.ExcelFile.

    Requires the path to a service account JSON key in the environment variable `SERVICE_ACCOUNT_FILE`.
    Share the spreadsheet with the service account's client_email.
    """
    sa_file = os.environ.get("SERVICE_ACCOUNT_FILE")
    if not sa_file or not os.path.exists(sa_file):
        raise FileNotFoundError("Service account file not found. Set SERVICE_ACCOUNT_FILE env var to the JSON key path.")
    from google.oauth2 import service_account
    from google.auth.transport.requests import AuthorizedSession

    scopes = ["https://www.googleapis.com/auth/drive.readonly", "https://www.googleapis.com/auth/spreadsheets.readonly"]
    creds = service_account.Credentials.from_service_account_file(sa_file, scopes=scopes)
    authed = AuthorizedSession(creds)

    xlsx_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=xlsx"
    resp = authed.get(xlsx_url)
    if resp.status_code == 403:
        print("Error 403: Access Denied. Make sure to share the Google Sheet with your service account email.")
        sys.exit(1)
    resp.raise_for_status()
    return pd.ExcelFile(io.BytesIO(resp.content))


def _try_find_sheet(names, token):
    token = token.lower()
    for n in names:
        if token in n.lower():
            return n
    return None


def _normalize_aux_sheet(df: pd.DataFrame, value_name: str):
    """
    Best-effort normalization for auxiliary sheets like bird/tray weights.
    Tries to find Date, Shed and a numeric value column. Returns DataFrame with
    columns ['Date','Shed', value_name].
    """
    # Drop completely empty rows/cols
    df = df.dropna(how="all").dropna(axis=1, how="all")

    # Handle horizontal dated blocks (sample layout): header row contains title with (date),
    # next row contains shed names, following rows contain numeric values for the sheds.
    nrows, ncols = df.shape
    out_rows = []

    for col in range(ncols):
        cell0 = str(df.iloc[0, col]) if nrows > 0 else ""
        m = re.search(r"\((\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\)", cell0)
        if m:
            date_str = m.group(1)
            date_val = pd.to_datetime(date_str, dayfirst=True, errors="coerce")

            # Determine contiguous block width by inspecting row 1 for shed names
            start_col = col
            end_col = start_col
            while end_col < ncols and not pd.isna(df.iloc[1, end_col]):
                end_col += 1
            if end_col == start_col:
                # fallback to 4 columns per block
                end_col = min(start_col + 4, ncols)

            shed_names = [str(x).strip() for x in df.iloc[1, start_col:end_col].tolist()]

            # Collect numeric rows until a blank row is encountered
            data_rows = []
            r = 2
            while r < nrows:
                block_vals = df.iloc[r, start_col:end_col].tolist()
                if all(pd.isna(v) or str(v).strip() == "" for v in block_vals):
                    break
                data_rows.append(block_vals)
                r += 1

            if data_rows:
                block_df = pd.DataFrame(data_rows, columns=shed_names)
                block_df = block_df.apply(pd.to_numeric, errors="coerce")
                block_df = block_df.replace({0: np.nan})
                means = block_df.mean(axis=0, skipna=True)
                for shed, val in means.items():
                    out_rows.append({"Date": date_val, "Shed": str(shed), value_name: val})

    if out_rows:
        out = pd.DataFrame(out_rows)
        out = out[out["Shed"].str.contains(r"Shed [1-4]", case=False, na=False)]
        out = out.groupby(["Date", "Shed"], as_index=False).mean()
        return out

    # Fallback: vertical table with explicit columns
    cols = [str(c) for c in df.columns]
    date_col = None
    shed_col = None
    value_col = None
    for c in cols:
        lc = c.lower()
        if "date" in lc and date_col is None:
            date_col = c
        if ("shed" in lc or "house" in lc or "pen" in lc) and shed_col is None:
            shed_col = c
        if ("weight" in lc or "kg" in lc or "tray" in lc or "count" in lc) and value_col is None:
            value_col = c

    if date_col and shed_col and value_col:
        out = df[[date_col, shed_col, value_col]].copy()
        out.columns = ["Date", "Shed", value_name]
        out["Date"] = pd.to_datetime(out["Date"], errors="coerce", dayfirst=True)
        out["Shed"] = out["Shed"].astype(str)
        out[value_name] = pd.to_numeric(out[value_name], errors="coerce")
        out = out.groupby(["Date", "Shed"], as_index=False).mean()
        return out

    return pd.DataFrame(columns=["Date", "Shed", value_name])


def main():
    # Determine source: Google Sheet ID via env var or CLI arg, otherwise local file
    sheet_id = os.environ.get("GSHEET_ID") or (sys.argv[1] if len(sys.argv) > 1 else None)

    if not sheet_id:
        print("Error: GSHEET_ID is not set. This script strictly requires a Google Sheet ID.")
        print("To resolve: Set the 'GSHEET_ID' environment variable or pass the ID as an argument.")
        sys.exit(1)

    print(f"Fetching workbook from Google Sheets: {sheet_id}")
    xls = _fetch_workbook_from_gsheets(sheet_id)

    all_sheets = xls.sheet_names
    sheets_to_process = [s for s in all_sheets if s and s.strip()]

    print(f"Processing {len(sheets_to_process)} sheets: {sheets_to_process}\n")

    all_records = []

    for sheet_name in sheets_to_process:
        if sheet_name.lower() in {"birdweight", "trayweight"}:
            print(f"Skipping auxiliary sheet for daily parsing: {sheet_name}")
            continue
        print(f"Processing: {sheet_name}")
        # Force dtype=str to ensure we parse dates strictly from raw text
        df = pd.read_excel(xls, sheet_name=sheet_name, header=None, dtype=str)

        records = []
        row = 0
        while row < len(df):
            row_values = df.iloc[row, :15].tolist()
            report_date = None
            for v in row_values:
                v_str = str(v).strip()
                # Flexible regex for DD-MM-YYYY, DD/MM/YYYY, or YYYY-MM-DD
                if re.search(r"\b\d{1,4}[-/]\d{1,2}[-/]\d{1,4}\b", v_str):
                    d = pd.to_datetime(v_str, dayfirst=True, errors="coerce")
                    if pd.notna(d):
                        report_date = d
                        break

            if report_date:
                # Validate that the next row actually contains Shed headers
                header_row_idx = row + 1
                if header_row_idx < len(df):
                    header_row_vals = " ".join(df.iloc[header_row_idx, :10].astype(str).tolist()).lower()
                    if "shed" not in header_row_vals:
                        row += 1
                        continue

                    # Safely slice to available columns for shed names
                    max_col = min(5, df.shape[1])
                    shed_names = df.iloc[header_row_idx, 1:max_col].tolist()
                    metrics = {}

                    for r in range(row + 2, min(row + 20, len(df))):
                        metric_name = str(df.iloc[r, 0]).strip()
                        metric_values = df.iloc[r, 1:max_col].tolist() if max_col > 1 else []
                        metrics[metric_name] = metric_values

                    for i, shed in enumerate(shed_names):
                        s_str = str(shed).strip().lower()
                        m = re.search(r"shed\s*([1-4])", s_str)
                        if m:
                            valid_shed = f"Shed {m.group(1)}"
                            records.append({
                                "Date": report_date,
                                "Shed": valid_shed,
                                "Age": metrics.get("Age", [None]*10)[i],
                                "Mortality": metrics.get("Mortality", [None]*10)[i],
                                "Bird_Balance": metrics.get("Bird Balance", [None]*10)[i],
                                "Fresh_Eggs": metrics.get("Fresh Eggs", [None]*10)[i],
                                "Crack_Eggs": metrics.get("Crack Eggs", [None]*10)[i],
                                "Leaker_Eggs": metrics.get("Leaker Eggs", [None]*10)[i],
                                "Jumbo_Tray": metrics.get("Jumbo Tray", [None]*10)[i],
                                "Production_Pct": metrics.get("Production %", [None]*10)[i],
                                "Fresh_Tray": metrics.get("Fresh Tray", [None]*10)[i],
                            })
                    # Jump to avoid noise
                    row += 18
                    continue

            row += 1

        all_records.extend(records)
        print(f"  → Extracted {len(records)} records\n")

    combined_df = pd.DataFrame(all_records)

    # Clean numeric data: Extract only the first number to prevent concatenation errors (e.g. 8 17 16 9 -> 8)
    numeric_cols = [
        "Fresh_Eggs", "Crack_Eggs", "Leaker_Eggs", "Jumbo_Tray", 
        "Fresh_Tray", "Production_Pct", "Age", "Bird_Balance", "Mortality"
    ]
    for col in numeric_cols:
        if col in combined_df.columns:
            combined_df[col] = (
                combined_df[col]
                .astype(str)
                .str.extract(r'(\d+\.?\d*)', expand=False)
            )
            combined_df[col] = pd.to_numeric(combined_df[col], errors="coerce")

    # Deduplicate monthly records before processing auxiliary sheets
    if not combined_df.empty:
        combined_df["Date"] = pd.to_datetime(combined_df["Date"], dayfirst=True)
        combined_df = combined_df.drop_duplicates(subset=["Date", "Shed"], keep="last")

    # Try to find and process Bird and Tray sheets (case-insensitive match)
    bird_sheet = _try_find_sheet(all_sheets, "bird")
    tray_sheet = _try_find_sheet(all_sheets, "tray")

    aux_frames = []

    if bird_sheet:
        print(f"Found bird sheet: {bird_sheet} — parsing")
        df_bird = pd.read_excel(xls, sheet_name=bird_sheet, header=None)
        bird_norm = _normalize_aux_sheet(df_bird, "Bird_Weight")
        if not bird_norm.empty:
            aux_frames.append(bird_norm)

    if tray_sheet:
        print(f"Found tray sheet: {tray_sheet} — parsing")
        df_tray = pd.read_excel(xls, sheet_name=tray_sheet, header=None)
        tray_norm = _normalize_aux_sheet(df_tray, "Tray_Weight")
        if not tray_norm.empty:
            aux_frames.append(tray_norm)

    # Merge auxiliary frames into combined_df
    if not combined_df.empty:
        combined_df["Date"] = pd.to_datetime(combined_df["Date"], dayfirst=True)
        combined_df["Shed"] = combined_df["Shed"].astype(str)

        # Prepare a week key for weekly auxiliary merges
        combined_df = combined_df.copy()
        combined_df["_week_start"] = combined_df["Date"].dt.to_period("W").apply(lambda p: p.start_time)

        for af in aux_frames:
            af = af.copy()
            # Ensure Date and Shed types
            af["Date"] = pd.to_datetime(af["Date"], dayfirst=True, errors="coerce")
            af["Shed"] = af["Shed"].astype(str)

            # First try exact-date merge
            merged = combined_df.merge(af, on=["Date", "Shed"], how="left")

            # For rows where the aux value is NaN, forward-fill the most recent weekly value
            value_col = [c for c in af.columns if c not in ("Date", "Shed")]
            if value_col:
                val = value_col[0]
                # compute week_start keys
                af["_week_start"] = af["Date"].dt.to_period("W").apply(lambda p: p.start_time)
                merged["_week_start"] = merged["Date"].dt.to_period("W").apply(lambda p: p.start_time)

                # Prepare right frame with available weekly measurements (drop NaNs)
                af_avail = af.dropna(subset=[val])[["_week_start", "Shed", val]].sort_values(["Shed", "_week_start"])

                if not af_avail.empty:
                    # Build per-shed sorted week lists for bisect-based forward-fill
                    af_avail["_week_start"] = pd.to_datetime(af_avail["_week_start"], errors="coerce")
                    shed_map = {}
                    for shed, g in af_avail.groupby("Shed"):
                        g_sorted = g.sort_values("_week_start")
                        week_list = list(g_sorted["_week_start"].tolist())
                        val_list = list(g_sorted[val].tolist())
                        shed_map[str(shed)] = (week_list, val_list)

                    # Ensure merged has _week_start as datetime
                    merged["_week_start"] = pd.to_datetime(merged["_week_start"], errors="coerce")

                    from bisect import bisect_right

                    def _fill_forward(row):
                        cur = row.get(val)
                        if pd.notna(cur):
                            return cur
                        wk = row.get("_week_start")
                        if pd.isna(wk):
                            return cur
                        shed = str(row.get("Shed"))
                        if shed not in shed_map:
                            return cur
                        weeks, vals = shed_map[shed]
                        idx = bisect_right(weeks, wk) - 1
                        if idx >= 0:
                            return vals[idx]
                        return cur

                    merged[val] = merged.apply(_fill_forward, axis=1)

            # Clean helper column
            if "_week_start" in merged.columns:
                merged = merged.drop(columns=[c for c in merged.columns if c == "_week_start"]).assign()

            combined_df = merged

    # Save combined output
    output_dir = ROOT / "output"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / "all_reports_combined.csv"

    combined_df.to_csv(output_file, index=False)

    print(f"\n{'='*60}")
    print(f"Total records: {len(combined_df)}")
    if not combined_df.empty:
        print(f"Date range: {combined_df['Date'].min()} to {combined_df['Date'].max()}")
    print(f"Saved to: {output_file}")
    print(f"{'='*60}")
    print(combined_df.head(10))


if __name__ == "__main__":
    main()
