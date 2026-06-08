import base64
import streamlit as st
import pandas as pd
import re
from urllib.parse import urlparse
from typing import Optional
import plotly.graph_objects as go
import plotly.express as px
from pathlib import Path
import random
import os
import io
import datetime
import numpy as np

# Handle large background images and suppress decompression bomb warnings
try:
    from PIL import Image
    Image.MAX_IMAGE_PIXELS = 150000000  # Threshold higher than bg1.jpeg
except ImportError:
    pass

# Google service-account auth
try:
    from google.oauth2 import service_account
    from google.auth.transport.requests import AuthorizedSession
except Exception:
    service_account = None
    AuthorizedSession = None

try:
    from dotenv import load_dotenv
    # Load .env if it exists to ensure local SERVICE_ACCOUNT_FILE and GSHEET_ID are available
    env_path = Path(__file__).resolve().parent / ".env"
    if env_path.exists():
        load_dotenv(dotenv_path=env_path, override=False)
except ImportError:
    pass

# Page configuration
st.set_page_config(
    page_title="VSF Farm Analytics",
    page_icon="🐔",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Hide Streamlit chrome for professional appearance (keep sidebar toggle visible)
hide_st_style = """
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    [data-testid="stSidebarNav"] {display: block !important;}
    </style>
    """
st.markdown(hide_st_style, unsafe_allow_html=True)

# Load background image from assets and embed it for the CSS background
def get_background_image():
    asset_path = Path("assets") / "bg1.jpeg"
    if asset_path.exists():
        encoded = base64.b64encode(asset_path.read_bytes()).decode()
        return f"data:image/jpeg;base64,{encoded}"
    return None

background_url = get_background_image() or "https://images.unsplash.com/photo-1500530855697-b586d89ba3ee?auto=format&fit=crop&w=1400&q=80"

# Make background white and increase readability for non-technical users
css = f"""
    <style>
    html, body, .stApp {{
        background-image: url('{background_url}');
        background-size: cover;
        background-position: center center;
        background-attachment: fixed;
        background-repeat: no-repeat;
        color: #111111 !important;
    }}
    .stApp, .main, .block-container {{
        background-color: rgba(255,255,255,0.78) !important;
        box-shadow: 0 20px 60px rgba(0,0,0,0.08);
        border: 1px solid rgba(255,255,255,0.9);
        padding-top: 1.5rem !important;
    }}
    /* Move the sidebar content (logo) to the very top corner */
    [data-testid="stSidebar"] [data-testid="stVerticalBlock"] {{
        padding-top: 0rem !important;
        gap: 0rem !important;
    }}
    [data-testid="stSidebar"], .css-1lcbmhc.e1fqkh3o2 {{
        background-color: rgba(255,255,255,0.95) !important;
        color: #111111 !important;
    }}
    header, .css-1avcm0n, .css-1rs6os, [data-testid="stToolbar"] {{
        background-color: rgba(255,255,255,0.95) !important;
        color: #111111 !important;
    }}
    header * {{ color: #111111 !important; }}
    .stExpanderHeader, .streamlit-expanderHeader, button[aria-expanded], .stButton>button, .stDownloadButton>button {{
        color: #111111 !important;
        background-color: #f8fafc !important;
        border-color: #d1d5db !important;
    }}
    .stApp, .stApp * {{ color: #111111 !important; }}
    .css-1d391kg {{padding: 1rem;}} /* layout padding tweak */
    .big-instruction {{font-size:18px; color:#111111}}
    
    /* Sidebar Styling */
    [data-testid="stSidebar"] {{
        border-right: 1px solid rgba(0,0,0,0.05);
    }}
    .sidebar-header {{
        font-size: 20px; font-weight: 700; color: #064e3b; margin-top: 1rem;
    }}
    .stMetricValue, .stMetricLabel, .stMetricDelta {{ color: #111111 !important; }}
    .stButton>button, .stDownloadButton>button {{ color: #111111 !important; background-color: #eef2ff !important; }}
    a {{ color: #0a66c2 !important; }}
    .metric-large .stMetricValue {{font-size:28px}}
    /* Animated quote header */
    @keyframes scrollLeft {{
        0% {{ transform: translateX(100%); opacity: 0; }}
        5% {{ opacity: 1; }}
        95% {{ opacity: 1; }}
        100% {{ transform: translateX(-100%); opacity: 0; }}
    }}
    .scrolling-quote-wrapper {{
        width: 100%;
        overflow: hidden;
        display: block;
        box-sizing: border-box;
        padding: 0px 0 5px 0;
    }}
    .scrolling-quote {{
        display: inline-block;
        animation: scrollLeft 12s linear infinite;
        white-space: nowrap;
        font-weight: 600;
        color: #2d5016;
        padding: 4px 20px;
        font-size: clamp(20px, 4.5vw, 48px);
    }}
    /* Title Spacing: Adjusted to be lower than the scrolling line */
    h1 {{
        margin-top: 15px !important;
        padding-top: 0px !important;
    }}
    /* Tabs: make them more prominent and easier to find */
    div[role="tablist"] > button[role="tab"] {{
        font-size: clamp(16px, 2.4vw, 22px) !important;
        font-weight: 700 !important;
        padding: 10px 18px !important;
        border-radius: 10px !important;
        margin: 0 6px !important;
        background-color: rgba(255,255,255,0.9) !important;
        color: #064e3b !important;
        border: 1px solid rgba(6,78,59,0.08) !important;
        box-shadow: none !important;
        transition: transform 0.12s ease, box-shadow 0.12s ease;
    }}
    div[role="tablist"] > button[role="tab"][aria-selected="true"] {{
        background: linear-gradient(90deg, #d1fae5, #bbf7d0) !important;
        color: #064e3b !important;
        box-shadow: 0 6px 18px rgba(34,197,94,0.12) !important;
        transform: translateY(-3px) !important;
    }}
    div[role="tablist"] > button[role="tab"]:hover {{
        transform: translateY(-2px) !important;
        box-shadow: 0 6px 14px rgba(34,197,94,0.06) !important;
    }}
    </style>
    """
st.markdown(css, unsafe_allow_html=True)

# Google Sheets helpers
def _parse_sheet_id(url_or_id: str):
    # Accept either a full URL or just the sheet id
    if not url_or_id:
        return None
    m = re.search(r"/d/([a-zA-Z0-9-_]+)", url_or_id)
    if m:
        return m.group(1)
    # fallback: if appears like an id
    if re.fullmatch(r"[a-zA-Z0-9-_]+", url_or_id.strip()):
        return url_or_id.strip()
    return None

def _build_csv_url(sheet_id: str, gid: Optional[str] = None):
    if gid:
        return f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid={gid}"
    # try generic CSV export (first sheet)
    return f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv"


def _get_google_creds(scopes):
    """Helper to get credentials from Streamlit Secrets (Prod) or File (Dev)."""
    # 1. Try Streamlit Secrets (Recommended for Public Repos)
    try:
        # Accessing st.secrets when missing can raise an exception in some environments
        if "gcp_service_account" in st.secrets:
            return service_account.Credentials.from_service_account_info(
                st.secrets["gcp_service_account"], scopes=scopes
            )
    except Exception:
        # Silently fail and proceed to local file check
        pass
    
    # 2. Try Local File (Fall back for local development)
    sa_file = os.environ.get("SERVICE_ACCOUNT_FILE")
    if sa_file and os.path.exists(sa_file):
        return service_account.Credentials.from_service_account_file(sa_file, scopes=scopes)
        
    return None

def _download_gsheet_excel(sheet_id: str):
    scopes = [
        "https://www.googleapis.com/auth/drive.readonly",
        "https://www.googleapis.com/auth/spreadsheets.readonly",
    ]
    creds = _get_google_creds(scopes)
    if not creds:
        raise FileNotFoundError("No Google credentials found in st.secrets or via SERVICE_ACCOUNT_FILE.")

    authed = AuthorizedSession(creds)
    xlsx_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=xlsx"
    resp = authed.get(xlsx_url)
    resp.raise_for_status()
    return pd.ExcelFile(io.BytesIO(resp.content))

def _extract_records_from_raw_df(df: pd.DataFrame):
    """Parses a raw report-style DataFrame into a clean list of records."""
    records = []
    row = 0
    while row < len(df):
        # Look for a date pattern in the first few columns
        row_values = df.iloc[row, :15].tolist()
        report_date = None

        for v in row_values:
            v_str = str(v).strip()
            # Flexible regex for DD-MM-YYYY, DD/MM/YYYY, or YYYY-MM-DD
            if re.search(r"\b\d{1,4}[-/]\d{1,2}[-/]\d{1,4}\b", v_str):
                # By parsing the raw string with dayfirst=True, we fix the May/Dec swap
                d = pd.to_datetime(v_str, dayfirst=True, errors='coerce')
                if pd.notna(d):
                    report_date = d
                    break

        if report_date:
            # Look ahead: the row immediately following the date MUST contain "Shed"
            # to be considered a valid production block.
            header_row_idx = row + 1
            if header_row_idx < len(df):
                header_row_vals = " ".join(df.iloc[header_row_idx, :10].astype(str).tolist()).lower()
                if "shed" in header_row_vals:
                    # Shed names are in the next row
                    max_col = min(10, df.shape[1])
                    shed_names = df.iloc[header_row_idx, 1:max_col].tolist()
                    metrics = {}
                    # Extract metrics for the next 18 rows - normalize names to lowercase
                    for r in range(row + 2, min(row + 20, len(df))):
                        metric_name = str(df.iloc[r, 0]).strip().lower()
                        metric_values = df.iloc[r, 1:max_col].tolist()
                        metrics[metric_name] = metric_values
                    
                    for i, shed in enumerate(shed_names):
                        s_str = str(shed).strip().lower()
                        # Strictly match Sheds 1-4 only
                        m = re.search(r'shed\s*([1-4])', s_str)
                        if m:
                            valid_name = f"Shed {m.group(1)}"
                            records.append({
                                "Date": report_date,
                                "Shed": valid_name,
                                "Age": metrics.get("age", [None]*10)[i],
                                "Mortality": metrics.get("mortality", [None]*10)[i],
                                "Bird_Balance": metrics.get("bird balance", [None]*10)[i],
                                "Fresh_Eggs": metrics.get("fresh eggs", [None]*10)[i],
                                "Crack_Eggs": metrics.get("crack eggs", [None]*10)[i],
                                "Leaker_Eggs": metrics.get("leaker eggs", [None]*10)[i],
                                "Jumbo_Tray": metrics.get("jumbo tray", [None]*10)[i],
                                "Production_Pct": metrics.get("production %", [None]*10)[i],
                                "Fresh_Tray": metrics.get("fresh tray", [None]*10)[i],
                            })
                    # JUMP forward to avoid parsing numbers inside this block as dates
                    row += 18
                    continue
        row += 1
    return pd.DataFrame(records)

# Load data (supports fallback to local output CSV)
@st.cache_data
def load_data(gsheet_url: Optional[str] = None, gsheet_gid: Optional[str] = None, sa_file: Optional[str] = None):
    # If the user has provided a Google Sheet URL/ID, try that first
    sheet_id = _parse_sheet_id(gsheet_url) if gsheet_url else os.environ.get("GSHEET_ID")
    
    if not sheet_id:
        st.error("Missing Google Sheet ID or URL.")
        st.info("💡 **Production fix:** Go to your Streamlit Cloud Settings -> Secrets and add `GSHEET_ID = 'your_id_here'`")
        st.stop()

    try:
        scopes = ["https://www.googleapis.com/auth/drive.readonly", "https://www.googleapis.com/auth/spreadsheets.readonly"]
        creds = _get_google_creds(scopes)
        if not creds:
            st.error("Google credentials not found.")
            st.info("💡 **Local Dev:** Set `SERVICE_ACCOUNT_FILE` in .env\n\n💡 **Production:** Add `gcp_service_account` to Streamlit Secrets.")
            st.stop()
            
        authed = AuthorizedSession(creds)

        xls = _download_gsheet_excel(sheet_id)
        all_dfs = []
        for sheet_name in xls.sheet_names:
            if sheet_name.lower() in {"birdweight", "trayweight", "sale", "final"} or "sheet" in sheet_name.lower():
                continue
            # Force dtype=str to prevent the Excel engine from incorrectly swapping day/month
            df_s = pd.read_excel(xls, sheet_name=sheet_name, header=None, dtype=str)
            extracted = _extract_records_from_raw_df(df_s)
            if not extracted.empty:
                all_dfs.append(extracted)
        
        df = pd.concat(all_dfs, ignore_index=True) if all_dfs else pd.DataFrame()

        # Deduplicate: If the same date/shed combo exists in multiple sheets, keep the last one found
        if not df.empty and "Date" in df.columns and "Shed" in df.columns:
            df = df.drop_duplicates(subset=["Date", "Shed"], keep="last")

        if not df.empty and "Date" in df.columns:
            # Force conversion to datetime to ensure correct sorting and max() operations
            df["Date"] = pd.to_datetime(df["Date"], dayfirst=True, errors='coerce')
            df = df.dropna(subset=["Date"])
        else:
            st.error("Google Sheet loaded successfully but no 'Date' column was found.")
            st.stop()
    except Exception as e:
        st.error(f"Error reading Google Sheet with service account: {e}")
        st.info("💡 **Checklist to resolve:**\n1. Share the Google Sheet with the Service Account email found in your JSON key.\n2. Ensure Google Sheets & Drive APIs are enabled in GCP Console.\n3. Verify the Sheet ID is correct.")
        st.stop()

    # Clean and coerce numeric columns that may contain stray text (e.g. "20 p", "%", commas)
    numeric_cols = [
        "Fresh_Eggs",
        "Crack_Eggs",
        "Leaker_Eggs",
        "Jumbo_Tray",
        "Fresh_Tray",
        "Production_Pct",
        "Age",
        "Bird_Balance",
        "Mortality",
        "Bird_Weight",
        "Tray_Weight",
    ]

    for col in numeric_cols:
        if col in df.columns:
            # Aggressively extract only the first numeric sequence found.
            # This ensures "8 17 16 9" becomes "8" and prevents large concatenated numbers.
            df[col] = (
                df[col]
                .astype(str)
                .str.extract(r'(\d+\.?\d*)', expand=False)
            )
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # Normalize Shed column to remove garbage values and standardize names like "Shed 1"
    if "Shed" in df.columns:
        s = df["Shed"].astype(str).str.strip()
        shed_match = s.str.extract(r'(Shed\s*\d+)', expand=False)
        shed_num = s.str.extract(r'^\s*(\d+)\s*$', expand=False)
        s_clean = shed_match.fillna(shed_num.apply(lambda x: 'Shed ' + x if pd.notna(x) else None))
        
        # Strictly normalize to "Shed X" format and only keep Sheds 1-4
        df["Shed"] = s_clean.str.replace(r'\s+', ' ', regex=True).str.title()
        
        # Only keep the core production sheds (Shed 1 to 4) and remove garbage/summary rows
        df = df[df["Shed"].isin(["Shed 1", "Shed 2", "Shed 3", "Shed 4"])].copy()
        
        # drop rows without a recognized shed label
        df = df[df["Shed"].notna()].copy()

    return df.sort_values("Date")

st.sidebar.markdown("---")
gsheet_url = os.environ.get("GSHEET_ID", "") or os.environ.get("GSHEET_URL", "")
gsheet_gid = os.environ.get("GSHEET_GID", "")
sa_file = os.environ.get("SERVICE_ACCOUNT_FILE", None)

df = load_data(gsheet_url if gsheet_url else None, gsheet_gid if gsheet_gid else None, sa_file)

# Helper: get per-sheet max dates from the source workbook
@st.cache_data(show_spinner=False)
def get_sheet_max_dates(gsheet_url: Optional[str] = None, gsheet_gid: Optional[str] = None, sa_file: Optional[str] = None):
    # If a Google Sheet is provided, return its max Date under a single key.
    sheet_id = _parse_sheet_id(gsheet_url) if gsheet_url else None
    if not sheet_id:
        return {}

    try:
        xls = _download_gsheet_excel(sheet_id)
        sheet_max = {}
        for sheet_name in xls.sheet_names:
            if sheet_name.lower() in {"birdweight", "trayweight", "sale", "final"} or "sheet" in sheet_name.lower():
                continue
            df_s = pd.read_excel(xls, sheet_name=sheet_name, header=None, dtype=str)
            extracted = _extract_records_from_raw_df(df_s)
            if not extracted.empty:
                sheet_max[sheet_name] = extracted["Date"].max()
        return sheet_max
    except Exception:
        pass
    return {}

sheet_max_dates = get_sheet_max_dates(gsheet_url if gsheet_url else None, gsheet_gid if gsheet_gid else None, sa_file)

# Add logo to the top of the sidebar for high visibility
st.sidebar.image("assets/vsf_logo.png", use_container_width=True)

# Sidebar filters (friendly for non-technical users)
st.sidebar.markdown('<p class="sidebar-header">📅 1. Choose Time Frame</p>', unsafe_allow_html=True)

# Simple presets for non-technical users
preset = st.sidebar.radio(
    "Pick a shortcut:",
    options=["Today Only", "Last 7 days", "Last 30 days", "Show All History", "Custom Dates"],
    index=3,
)

today_date = df["Date"].max().date()
if preset == "Today Only":
    default_start = today_date
elif preset == "Last 7 days":
    default_start = today_date - pd.Timedelta(days=6)
elif preset == "Last 30 days":
    default_start = today_date - pd.Timedelta(days=29)
elif preset == "Show All History":
    default_start = df["Date"].min().date()
else:
    default_start = df["Date"].min().date()

default_end = today_date

date_range = st.sidebar.date_input(
    "Date Range",
    value=(default_start, default_end),
    min_value=df["Date"].min().date(),
    max_value=df["Date"].max().date()
)

sheds = sorted(df["Shed"].dropna().unique())
selected_sheds = st.sidebar.multiselect(
    "Select Sheds",
    options=sheds,
    default=sheds
)

# Weight aggregation controls: bird/tray sheets are weekly in the source
aggregate_weights_weekly = st.sidebar.checkbox(
    "Aggregate weight data by week (use for Bird/Tray sheets)",
    value=True,
)

# Date limiting controls
st.sidebar.markdown("---")
st.sidebar.subheader("🛡️ Data Accuracy Guard")
date_limit_mode = st.sidebar.radio(
    "Ignore data entries after:",
    options=[
        "Show everything",
        "Stop at the latest report date",
        "Stop at one sheet's final date",
        "Choose a finish date",
    ],
    index=0,
)

combined_max = df["Date"].max().date()
selected_cap_date = None
if date_limit_mode == "Stop at the latest report date":
    selected_cap_date = combined_max
elif date_limit_mode == "Stop at one sheet's final date":
    sheet_choice = st.sidebar.selectbox(
        "Pick sheet to use for the end date",
        options=sorted(sheet_max_dates.keys()),
    )
    selected_cap_date = sheet_max_dates.get(sheet_choice).date() if sheet_choice else None
elif date_limit_mode == "Choose a finish date":
    selected_cap_date = st.sidebar.date_input(
        "Choose the last date to include",
        value=combined_max,
        min_value=df["Date"].min().date(),
        max_value=combined_max,
    )

if selected_cap_date:
    st.sidebar.write(f"Including data up to: {selected_cap_date}")


# Filter data
filtered_df = df[
    (df["Date"].dt.date >= date_range[0]) &
    (df["Date"].dt.date <= date_range[1]) &
    (df["Shed"].isin(selected_sheds))
]

# Apply cap from date limiter if set
if selected_cap_date:
    filtered_df = filtered_df[filtered_df["Date"].dt.date <= selected_cap_date]

# Animated poultry quote header
quotes = [
    "🐔 Premium Poultry, Premium Care, Premium Results",
    "🥚 Every Egg Tells a Story of Excellence",
    "🌾 From Farm to Table with Precision",
    "💪 Healthy Birds, Happy Farmers, Great Yields",
    "✨ Analytics-Driven Poultry Excellence"
]
import random
quote = random.choice(quotes)
st.markdown(f'<div class="scrolling-quote">{quote}</div>', unsafe_allow_html=True)

# Main title
st.title("🐔 VSF Farm Analytics")
latest_date = filtered_df["Date"].max()
st.markdown(
    f"🗓️ **Range:** `{date_range[0]}` to `{date_range[1]}` | "
    f"🏠 **Sheds:** `{', '.join(selected_sheds)}` | "
    f"✅ **Latest Data:** `{latest_date.strftime('%B %d, %Y') if pd.notna(latest_date) else 'N/A'}`"
)

with st.expander("📖 Dashboard Guide: How to read this report"):
    st.markdown("""
    **Welcome to your Farm Analytics!** Here is how to get the most out of this view:
    1. **The Cards Below:** These show the performance for the **most recent day** in your selection.
    2. **Filtering:** Use the sidebar on the left to change dates or focus on specific sheds.
    3. **Trends:** Click the **Trends** or **Shed Details** tabs above to see how things have changed over time.
    4. **Data Guard:** If you see "future" data, check the 'Data Accuracy Guard' in the sidebar.
    """)

# Key metrics row
latest_date = filtered_df["Date"].max()
today_data = filtered_df[filtered_df["Date"] == latest_date]

st.markdown(f"### 🚀 Latest Results: **{latest_date.strftime('%d %B, %Y')}**")
col1, col2, col3, col4, col5, col6 = st.columns(6)

with col1:
    total_birds = 0
    if "Bird_Balance" in today_data.columns and today_data["Bird_Balance"].notna().any():
        try:
            total_birds = int(today_data["Bird_Balance"].sum())
        except Exception:
            total_birds = int(today_data["Bird_Balance"].sum(skipna=True) or 0)
    st.metric("Total Birds", f"{total_birds:,}", delta=None)

with col2:
    fresh_eggs = int(today_data['Fresh_Eggs'].sum()) if 'Fresh_Eggs' in today_data.columns and today_data['Fresh_Eggs'].notna().any() else 0
    st.metric("Fresh Eggs", f"{fresh_eggs:,}")

with col3:
    crack = today_data['Crack_Eggs'].sum() if 'Crack_Eggs' in today_data.columns else 0
    leaker = today_data['Leaker_Eggs'].sum() if 'Leaker_Eggs' in today_data.columns else 0
    total_produced = int(fresh_eggs + crack + leaker)
    st.metric("Total Produced", f"{total_produced:,}", help="Sum of Fresh, Crack, and Leaker eggs")

with col4:
    mortality = int(today_data['Mortality'].sum()) if 'Mortality' in today_data.columns and today_data['Mortality'].notna().any() else 0
    st.metric("Mortality", f"{mortality}", delta=None)

with col5:
    prod_pct = None
    if 'Production_Pct' in today_data.columns and today_data['Production_Pct'].notna().any():
        prod_pct = today_data['Production_Pct'].mean()
    st.metric("Avg Production %", f"{prod_pct:.2f}%" if prod_pct is not None else "N/A", delta=None)

with col6:
    fresh_trays = int(today_data['Fresh_Tray'].sum()) if 'Fresh_Tray' in today_data.columns and today_data['Fresh_Tray'].notna().any() else 0
    st.metric("Total Fresh Trays", f"{fresh_trays:,}", delta=None)
if "Bird_Weight" in df.columns or "Tray_Weight" in df.columns:
    bird_avg = None
    tray_avg = None
    if "Bird_Weight" in today_data.columns and today_data["Bird_Weight"].notna().any():
        bird_avg = today_data["Bird_Weight"].mean()
    if "Tray_Weight" in today_data.columns and today_data["Tray_Weight"].notna().any():
        tray_avg = today_data["Tray_Weight"].mean()

    col1, col2 = st.columns(2)
    with col1:
        st.metric(
            "Avg Bird Weight",
            f"{bird_avg:.1f} g" if bird_avg is not None else "N/A",
            delta=None
        )
    with col2:
        st.metric(
            "Avg Tray Weight",
            f"{tray_avg:.1f} g" if tray_avg is not None else "N/A",
            delta=None
        )
st.divider()

# Tabs for different views
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📊 Overview",
    "📈 Trends",
    "🐔 Shed Details",
    "📋 Data Table",
    "💡 Insights"
])

# Tab 1: Overview
with tab1:
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Daily Fresh Eggs Production")
        daily_eggs = filtered_df.groupby("Date")["Fresh_Eggs"].sum().reset_index()
        fig_eggs = px.line(
            daily_eggs,
            x="Date",
            y="Fresh_Eggs",
            markers=True,
            title="Fresh Eggs Over Time"
        )
        fig_eggs.update_yaxes(title_text="Fresh Eggs")
        st.plotly_chart(fig_eggs, use_container_width=True)
    
    with col2:
        st.subheader("Daily Bird Balance")
        daily_birds = filtered_df.groupby("Date")["Bird_Balance"].sum().reset_index()
        fig_birds = px.line(
            daily_birds,
            x="Date",
            y="Bird_Balance",
            markers=True,
            title="Total Bird Balance Over Time"
        )
        fig_birds.update_yaxes(title_text="Bird Balance")
        st.plotly_chart(fig_birds, use_container_width=True)
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Production Percentage Trend")
        prod_pct = filtered_df.groupby("Date")["Production_Pct"].mean().reset_index()
        fig_prod = px.line(
            prod_pct,
            x="Date",
            y="Production_Pct",
            markers=True,
            title="Average Production %"
        )
        fig_prod.update_yaxes(title_text="Production %")
        st.plotly_chart(fig_prod, use_container_width=True)
    
    with col2:
        st.subheader("Mortality Rate Trend")
        mortality = filtered_df.groupby("Date")["Mortality"].sum().reset_index()
        fig_mort = px.line(
            mortality,
            x="Date",
            y="Mortality",
            markers=True,
            title="Daily Mortality Count"
        )
        fig_mort.update_yaxes(title_text="Mortality Count")
        st.plotly_chart(fig_mort, use_container_width=True)

    if "Bird_Weight" in filtered_df.columns or "Tray_Weight" in filtered_df.columns:
        col1, col2 = st.columns(2)
        with col1:
            if "Bird_Weight" in filtered_df.columns:
                st.subheader("Avg Bird Weight")
                if aggregate_weights_weekly:
                    bw = filtered_df.copy()
                    bw["_week_start"] = bw["Date"].dt.to_period("W").apply(lambda p: p.start_time)
                    bird_weight = bw.groupby("_week_start")["Bird_Weight"].mean().reset_index()
                    bird_weight = bird_weight.rename(columns={"_week_start": "Date"})
                else:
                    bird_weight = filtered_df.groupby("Date")["Bird_Weight"].mean().reset_index()

                fig_bird_weight = px.line(
                    bird_weight,
                    x="Date",
                    y="Bird_Weight",
                    markers=True,
                    title="Average Bird Weight Over Time"
                )
                fig_bird_weight.update_yaxes(title_text="Bird Weight (g)")
                st.plotly_chart(fig_bird_weight, use_container_width=True)
            else:
                st.info("No Bird Weight data available.")

        with col2:
            if "Tray_Weight" in filtered_df.columns:
                st.subheader("Avg Tray Weight")
                if aggregate_weights_weekly:
                    tw = filtered_df.copy()
                    tw["_week_start"] = tw["Date"].dt.to_period("W").apply(lambda p: p.start_time)
                    tray_weight = tw.groupby("_week_start")["Tray_Weight"].mean().reset_index()
                    tray_weight = tray_weight.rename(columns={"_week_start": "Date"})
                else:
                    tray_weight = filtered_df.groupby("Date")["Tray_Weight"].mean().reset_index()

                fig_tray_weight = px.line(
                    tray_weight,
                    x="Date",
                    y="Tray_Weight",
                    markers=True,
                    title="Average Tray Weight Over Time"
                )
                fig_tray_weight.update_yaxes(title_text="Tray Weight (g)")
                st.plotly_chart(fig_tray_weight, use_container_width=True)
            else:
                st.info("No Tray Weight data available.")

# Tab 2: Trends Analysis
with tab2:
    st.subheader("Comparative Metrics Over Time")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Egg Quality Analysis")
        daily_egg_types = filtered_df.groupby("Date")[["Fresh_Eggs", "Crack_Eggs", "Leaker_Eggs"]].sum().reset_index()
        
        fig_egg_comp = go.Figure()
        # Primary Axis: Fresh Eggs
        fig_egg_comp.add_trace(go.Scatter(x=daily_egg_types["Date"], y=daily_egg_types["Fresh_Eggs"], name="Fresh Eggs (Main)", line=dict(color='#10b981', width=3)))
        # Secondary Axis: Crack and Leaker
        fig_egg_comp.add_trace(go.Scatter(x=daily_egg_types["Date"], y=daily_egg_types["Crack_Eggs"], name="Crack Eggs (Right Axis)", yaxis="y2", line=dict(color='#f59e0b', dash='dot')))
        fig_egg_comp.add_trace(go.Scatter(x=daily_egg_types["Date"], y=daily_egg_types["Leaker_Eggs"], name="Leaker Eggs (Right Axis)", yaxis="y2", line=dict(color='#ef4444', dash='dash')))
        
        fig_egg_comp.update_layout(
            title="Fresh vs. Quality Issues",
            yaxis=dict(title="Total Fresh Eggs", side="left", tickformat=","),
            yaxis2=dict(title="Crack / Leaker Count", overlaying="y", side="right", showgrid=False, tickformat=","),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            hovermode="x unified"
        )
        st.plotly_chart(fig_egg_comp, use_container_width=True)
    
    with col2:
        st.subheader("Tray Types Distribution")
        tray_data = filtered_df.groupby("Date")[["Jumbo_Tray", "Fresh_Tray"]].sum().reset_index()
        
        fig_trays = go.Figure()
        # Primary Axis: Fresh Trays
        fig_trays.add_trace(go.Bar(x=tray_data["Date"], y=tray_data["Fresh_Tray"], name="Fresh Trays", marker_color='#3b82f6', opacity=0.7))
        # Secondary Axis: Jumbo Trays
        fig_trays.add_trace(go.Scatter(x=tray_data["Date"], y=tray_data["Jumbo_Tray"], name="Jumbo Trays (Right Axis)", yaxis="y2", line=dict(color='#8b5cf6', width=3)))
        
        fig_trays.update_layout(
            title="Fresh Trays vs. Jumbo Trays",
            yaxis=dict(title="Fresh Trays (Bars)", tickformat=","),
            yaxis2=dict(title="Jumbo Trays (Line)", overlaying="y", side="right", showgrid=False, tickformat=","),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            hovermode="x unified"
        )
        st.plotly_chart(fig_trays, use_container_width=True)
    
    st.subheader("Age vs Production Performance")
    age_prod = filtered_df.groupby("Date").agg({
        "Age": "mean",
        "Production_Pct": "mean"
    }).reset_index()
    
    fig_age = go.Figure()
    fig_age.add_trace(go.Scatter(x=age_prod["Date"], y=age_prod["Age"], name="Avg Age", yaxis="y1"))
    fig_age.add_trace(go.Scatter(x=age_prod["Date"], y=age_prod["Production_Pct"], name="Production %", yaxis="y2"))
    fig_age.update_layout(
        title="Age vs Production Performance",
        xaxis=dict(title="Date"),
        yaxis=dict(title="Age (weeks)", side="left"),
        yaxis2=dict(title="Production %", overlaying="y", side="right"),
        hovermode="x unified"
    )
    st.plotly_chart(fig_age, use_container_width=True)

# Tab 3: Shed Details
with tab3:
    st.subheader("Performance by Shed")
    
    selected_shed = st.selectbox(
        "Select Shed for Detailed Analysis",
        sorted(filtered_df["Shed"].unique())
    )
    
    shed_data = filtered_df[filtered_df["Shed"] == selected_shed]
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total Fresh Eggs", int(shed_data["Fresh_Eggs"].sum()))
    with col2:
        st.metric("Avg Age", f"{shed_data['Age'].mean():.1f} weeks")
    with col3:
        st.metric("Avg Production %", f"{shed_data['Production_Pct'].mean():.2f}%")
    with col4:
        st.metric("Total Mortality", int(shed_data["Mortality"].sum()))
    
    col1, col2 = st.columns(2)
    
    with col1:
        fig_shed_eggs = px.line(
            shed_data.sort_values("Date"),
            x="Date",
            y="Fresh_Eggs",
            title=f"{selected_shed} - Fresh Eggs",
            markers=True
        )
        st.plotly_chart(fig_shed_eggs, use_container_width=True)
    
    with col2:
        fig_shed_prod = px.line(
            shed_data.sort_values("Date"),
            x="Date",
            y="Production_Pct",
            title=f"{selected_shed} - Production %",
            markers=True
        )
        st.plotly_chart(fig_shed_prod, use_container_width=True)
    
    # Shed comparison
    st.subheader("Shed Comparison (Latest Date)")
    latest_shed_data = filtered_df[filtered_df["Date"] == latest_date]
    
    col1, col2 = st.columns(2)
    
    with col1:
        fig_comp_eggs = px.bar(
            latest_shed_data,
            x="Shed",
            y="Fresh_Eggs",
            title="Fresh Eggs by Shed (Latest Date)",
            color="Shed"
        )
        st.plotly_chart(fig_comp_eggs, use_container_width=True)
    
    with col2:
        fig_comp_prod = px.bar(
            latest_shed_data,
            x="Shed",
            y="Production_Pct",
            title="Production % by Shed (Latest Date)",
            color="Shed"
        )
        st.plotly_chart(fig_comp_prod, use_container_width=True)

# Tab 4: Data Table
with tab4:
    st.subheader("Detailed Data Table")
    
    # Sort options
    col1, col2, col3 = st.columns(3)
    
    with col1:
        sort_by = st.selectbox(
            "Sort by",
            ["Date", "Shed", "Fresh_Eggs", "Production_Pct", "Bird_Balance"]
        )
    
    with col2:
        sort_order = st.selectbox("Order", ["Ascending", "Descending"])
    
    with col3:
        rows_to_show = st.slider("Rows to display", 10, len(filtered_df), 50)
    
    ascending = sort_order == "Ascending"
    display_df = filtered_df.sort_values(sort_by, ascending=ascending).head(rows_to_show).copy()

    # Format Date column to show only YYYY-MM-DD for the data table
    if "Date" in display_df.columns:
        try:
            display_df["Date"] = display_df["Date"].dt.strftime("%Y-%m-%d")
        except Exception:
            display_df["Date"] = display_df["Date"].astype(str)

    st.dataframe(display_df, use_container_width=True, height=400)
    
    # Download button
    csv = filtered_df.to_csv(index=False)
    st.download_button(
        label="📥 Download Filtered Data (CSV)",
        data=csv,
        file_name=f"farm_data_{date_range[0]}_to_{date_range[1]}.csv",
        mime="text/csv"
    )

# Tab 5: Insights
with tab5:
    st.subheader("📊 Key Insights")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.info("**Highest Production Day**")
        top_day = filtered_df.groupby("Date")["Fresh_Eggs"].sum().idxmax()
        top_eggs = filtered_df.groupby("Date")["Fresh_Eggs"].sum().max()
        st.write(f"Date: {top_day.date()}")
        st.write(f"Fresh Eggs: {int(top_eggs):,}")
    
    with col2:
        st.info("**Lowest Production Day**")
        low_day = filtered_df.groupby("Date")["Fresh_Eggs"].sum().idxmin()
        low_eggs = filtered_df.groupby("Date")["Fresh_Eggs"].sum().min()
        st.write(f"Date: {low_day.date()}")
        st.write(f"Fresh Eggs: {int(low_eggs):,}")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.info("**Best Performing Shed**")
        best_shed = filtered_df.groupby("Shed")["Production_Pct"].mean().idxmax()
        best_prod = filtered_df.groupby("Shed")["Production_Pct"].mean().max()
        st.write(f"Shed: {best_shed}")
        st.write(f"Avg Production %: {best_prod:.2f}%")
    
    with col2:
        st.info("**Highest Mortality Shed**")
        high_mort_shed = filtered_df.groupby("Shed")["Mortality"].sum().idxmax()
        high_mort = filtered_df.groupby("Shed")["Mortality"].sum().max()
        st.write(f"Shed: {high_mort_shed}")
        st.write(f"Total Mortality: {int(high_mort)}")
    
    st.divider()
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric(
            "Avg Daily Production",
            f"{int(filtered_df.groupby('Date')['Fresh_Eggs'].sum().mean()):,}"
        )
    
    with col2:
        st.metric(
            "Overall Avg Age",
            f"{filtered_df['Age'].mean():.1f} weeks"
        )
    
    with col3:
        st.metric(
            "Avg Production %",
            f"{filtered_df['Production_Pct'].mean():.2f}%"
        )
    
    st.divider()
    
    st.write("**📈 Farm Performance Benchmarks**")
    st.write("This table shows the typical performance versus the best and worst days in your selected range.")
    
    # Create a user-friendly summary table
    stats_df = filtered_df.agg({
        "Age": ["mean", "min", "max"],
        "Bird_Balance": ["mean", "min", "max"],
        "Fresh_Eggs": ["mean", "min", "max"],
        "Mortality": ["mean", "min", "max"],
        "Production_Pct": ["mean", "min", "max"]
    }).T

    stats_df.columns = ["Average (Typical)", "Lowest Recorded", "Highest Recorded"]
    stats_df.index = ["Age (Weeks)", "Bird Population", "Daily Fresh Eggs", "Daily Mortality", "Production %"]

    # Display cleaned up table
    st.dataframe(
        stats_df.style.format({
            "Average (Typical)": "{:,.2f}",
            "Lowest Recorded": "{:,.0f}",
            "Highest Recorded": "{:,.0f}"
        }),
        use_container_width=True
    )

# Footer
st.divider()
st.markdown(
    """
    ### About
    **Owner:** Late Ch VED Singh Singroha  
    **Address:** Bharon Khera, Jind, Haryana - 126114  

    **Contact Us:**  
    📱 WhatsApp: +91 9992373885  
    ✉️ Email: [naveensingroha92@gmail.com](mailto:naveensingroha92@gmail.com)
    """
)
st.caption(f"Data updated: {df['Date'].max().date()}")
