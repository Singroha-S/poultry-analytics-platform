import base64
import streamlit as st
import pandas as pd
import re
from urllib.parse import urlparse
from typing import Optional
import plotly.graph_objects as go
import plotly.express as px
import plotly.io as pio
from pathlib import Path
import random
import os
import io
import datetime
import numpy as np
import inspect

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

def get_favicon():
    """Load the logo and add a solid white background so it is visible in dark browser tabs."""
    try:
        from PIL import Image
        img = Image.open("assets/vsf_logo.png").convert("RGBA")
        # Create a solid white background image
        bg = Image.new("RGBA", img.size, (255, 255, 255, 255))
        # Paste the original image onto the white background using its alpha channel as a mask
        bg.paste(img, (0, 0), img)
        return bg.convert("RGB")
    except Exception:
        return "assets/vsf_logo.png"

def get_stretch():
    """Return the correct kwarg for stretching elements to container width based on Streamlit version."""
    try:
        sig = inspect.signature(st.plotly_chart)
        if 'width' in sig.parameters:
            return {"width": "stretch"}
    except Exception:
        pass
    return {"use_container_width": True}

STRETCH = get_stretch()

# Page configuration
st.set_page_config(
    page_title="Layer Farm Analytics",
    page_icon=get_favicon(),
    layout="wide",
    initial_sidebar_state="expanded"
)

# ---------------------------------------------------------------------------
# Design system / theme
# ---------------------------------------------------------------------------
# Brand palette (emerald + warm amber — fits a poultry/farm brand)
BRAND = {
    "ink": "#0f1f17",          # near-black green for text
    "muted": "#5b6b62",        # secondary text
    "primary": "#059669",      # emerald
    "primary_dark": "#047857",
    "primary_light": "#10b981",
    "accent": "#f59e0b",       # amber
    "danger": "#ef4444",
    "info": "#3b82f6",
    "violet": "#8b5cf6",
    "surface": "#ffffff",
    "line": "rgba(15,31,23,0.08)",
}
CHART_COLORS = ["#059669", "#3b82f6", "#f59e0b", "#8b5cf6", "#ef4444", "#14b8a6"]

# A single Plotly template so every chart shares one clean, modern look
pio.templates["vsf"] = go.layout.Template(
    layout=dict(
        font=dict(family="Inter, 'Segoe UI', system-ui, sans-serif", size=13, color=BRAND["ink"]),
        title=dict(font=dict(size=16, color=BRAND["ink"]), x=0.01, xanchor="left", pad=dict(b=10)),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        colorway=CHART_COLORS,
        margin=dict(l=10, r=10, t=56, b=10),
        hoverlabel=dict(bgcolor="white", bordercolor=BRAND["line"],
                        font=dict(family="Inter, sans-serif", size=12, color=BRAND["ink"])),
        xaxis=dict(showgrid=False, zeroline=False, linecolor=BRAND["line"],
                   tickcolor=BRAND["line"], title=dict(font=dict(size=12, color=BRAND["muted"]))),
        yaxis=dict(gridcolor="rgba(15,31,23,0.06)", zeroline=False, linecolor="rgba(0,0,0,0)",
                   title=dict(font=dict(size=12, color=BRAND["muted"]))),
        legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(size=12)),
    )
)
pio.templates.default = "vsf"
px.defaults.template = "vsf"
px.defaults.color_discrete_sequence = CHART_COLORS


def style_chart(fig, height: int = 320, show_legend: bool = True):
    """Apply consistent finishing touches to any Plotly figure."""
    fig.update_layout(
        height=height,
        showlegend=show_legend,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
        hovermode="x unified",
    )
    # Smooth, rounded lines + soft markers for line charts
    fig.update_traces(selector=dict(type="scatter"),
                      line=dict(width=2.6), marker=dict(size=6))
    return fig


# Load background image from assets and embed it for a subtle hero banner
def get_background_image():
    asset_path = Path("assets") / "bg1.jpeg"
    if asset_path.exists():
        encoded = base64.b64encode(asset_path.read_bytes()).decode()
        return f"data:image/jpeg;base64,{encoded}"
    return None

background_url = get_background_image() or "https://images.unsplash.com/photo-1500530855697-b586d89ba3ee?auto=format&fit=crop&w=1400&q=80"

css = f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

    /* Hide default Streamlit chrome */
    #MainMenu, footer {{ visibility: hidden; }}
    [data-testid="stHeader"] {{ background: rgba(0,0,0,0); }}
    [data-testid="stSidebarNav"] {{ display: block !important; }}

    /* ---- App canvas: clean, soft gradient ---- */
    html, body, .stApp {{
        font-family: 'Inter', system-ui, sans-serif;
        background: linear-gradient(160deg, #f3f8f5 0%, #eef4f9 45%, #f6f4ef 100%) fixed;
        color: {BRAND['ink']};
    }}
    .block-container {{
        padding-top: 1.2rem !important;
        max-width: 1300px;
    }}

    /* ---- Typography ---- */
    h1, h2, h3, h4 {{ font-family: 'Inter', sans-serif; color: {BRAND['ink']}; letter-spacing: -0.01em; }}
    h1 {{ font-weight: 800 !important; font-size: clamp(28px, 4vw, 40px) !important; margin: 4px 0 2px 0 !important; }}
    h2 {{ font-weight: 700 !important; }}
    h3 {{ font-weight: 700 !important; font-size: 1.18rem !important; }}
    .stApp p, .stApp li, .stApp label {{ color: {BRAND['ink']}; }}
    a {{ color: {BRAND['primary_dark']} !important; font-weight: 600; }}

    /* ---- Hero banner ---- */
    .hero {{
        position: relative;
        border-radius: 22px;
        padding: 30px 34px;
        margin-bottom: 18px;
        color: #fff;
        background:
            linear-gradient(120deg, rgba(4,120,87,0.94) 0%, rgba(5,150,105,0.86) 55%, rgba(13,148,136,0.82) 100%),
            url('{background_url}');
        background-size: cover;
        background-position: center;
        box-shadow: 0 18px 40px rgba(4,120,87,0.22);
        overflow: hidden;
    }}
    .hero h1 {{ color: #fff !important; margin: 0 !important; font-size: clamp(26px, 3.6vw, 38px) !important; }}
    .hero .tagline {{
        display: inline-block; margin-top: 6px; font-weight: 500;
        font-size: clamp(14px, 1.6vw, 17px); color: rgba(255,255,255,0.92);
    }}
    .hero .pill-row {{ margin-top: 16px; display: flex; flex-wrap: wrap; gap: 10px; }}
    .hero .pill {{
        background: rgba(255,255,255,0.18); border: 1px solid rgba(255,255,255,0.28);
        backdrop-filter: blur(6px); padding: 6px 14px; border-radius: 999px;
        font-size: 13.5px; font-weight: 600; color: #fff;
    }}
    .hero .pill b {{ font-weight: 800; }}

    /* ---- Section heading ---- */
    .section-title {{
        font-size: 1.15rem; font-weight: 800; color: {BRAND['ink']};
        margin: 6px 0 2px 0; display: flex; align-items: center; gap: 8px;
    }}

    /* ---- KPI metric cards (st.metric) ---- */
    [data-testid="stMetric"] {{
        background: {BRAND['surface']};
        border: 1px solid {BRAND['line']};
        border-radius: 16px;
        padding: 16px 18px;
        box-shadow: 0 4px 14px rgba(15,31,23,0.05);
        transition: transform .15s ease, box-shadow .15s ease;
        border-top: 3px solid {BRAND['primary']};
    }}
    [data-testid="stMetric"]:hover {{
        transform: translateY(-3px);
        box-shadow: 0 12px 26px rgba(15,31,23,0.10);
    }}
    [data-testid="stMetricLabel"] {{
        font-size: 0.82rem !important; font-weight: 600 !important;
        color: {BRAND['muted']} !important; text-transform: uppercase; letter-spacing: .04em;
    }}
    [data-testid="stMetricValue"] {{
        font-size: 1.7rem !important; font-weight: 800 !important; color: {BRAND['ink']} !important;
    }}

    /* ---- Charts get a card frame ---- */
    [data-testid="stPlotlyChart"] {{
        background: {BRAND['surface']};
        border: 1px solid {BRAND['line']};
        border-radius: 16px;
        padding: 8px 8px 4px 8px;
        box-shadow: 0 4px 14px rgba(15,31,23,0.05);
    }}

    /* ---- Sidebar ---- */
    [data-testid="stSidebar"] {{
        background: {BRAND['surface']};
        border-right: 1px solid {BRAND['line']};
    }}
    [data-testid="stSidebar"] [data-testid="stVerticalBlock"] {{ gap: 0.5rem !important; }}
    .sidebar-header {{
        font-size: 15px; font-weight: 800; color: {BRAND['primary_dark']};
        margin: 14px 0 2px 0; text-transform: uppercase; letter-spacing: .03em;
    }}

    /* ---- Buttons ---- */
    .stButton>button, .stDownloadButton>button {{
        background: {BRAND['primary']} !important;
        color: #fff !important;
        border: none !important;
        border-radius: 10px !important;
        font-weight: 700 !important;
        padding: 0.5rem 1rem !important;
        box-shadow: 0 4px 12px rgba(5,150,105,0.25) !important;
        transition: transform .12s ease, box-shadow .12s ease;
    }}
    .stButton>button:hover, .stDownloadButton>button:hover {{
        transform: translateY(-1px);
        box-shadow: 0 8px 18px rgba(5,150,105,0.32) !important;
    }}

    /* ---- Tabs ---- */
    div[role="tablist"] {{ gap: 6px; border-bottom: 1px solid {BRAND['line']}; padding-bottom: 2px; }}
    div[role="tablist"] > button[role="tab"] {{
        font-size: 15px !important;
        font-weight: 600 !important;
        padding: 9px 18px !important;
        border-radius: 10px 10px 0 0 !important;
        background: transparent !important;
        color: {BRAND['muted']} !important;
        border: none !important;
        transition: all .15s ease;
    }}
    div[role="tablist"] > button[role="tab"]:hover {{
        color: {BRAND['primary_dark']} !important;
        background: rgba(5,150,105,0.06) !important;
    }}
    div[role="tablist"] > button[role="tab"][aria-selected="true"] {{
        color: {BRAND['primary_dark']} !important;
        background: rgba(5,150,105,0.10) !important;
        border-bottom: 3px solid {BRAND['primary']} !important;
        font-weight: 800 !important;
    }}

    /* ---- Expander + info callouts ---- */
    [data-testid="stExpander"] {{
        border: 1px solid {BRAND['line']} !important;
        border-radius: 14px !important;
        background: {BRAND['surface']};
        box-shadow: 0 2px 8px rgba(15,31,23,0.04);
    }}
    [data-testid="stAlert"] {{ border-radius: 14px; }}

    /* ---- Insight cards ---- */
    .insight-card {{
        background: {BRAND['surface']};
        border: 1px solid {BRAND['line']};
        border-left: 4px solid {BRAND['primary']};
        border-radius: 14px;
        padding: 16px 18px;
        box-shadow: 0 4px 14px rgba(15,31,23,0.05);
        height: 100%;
    }}
    .insight-card .ic-label {{ font-size: .8rem; font-weight: 700; color: {BRAND['muted']};
        text-transform: uppercase; letter-spacing: .04em; }}
    .insight-card .ic-main {{ font-size: 1.5rem; font-weight: 800; color: {BRAND['ink']}; margin: 4px 0 0 0; }}
    .insight-card .ic-sub {{ font-size: .9rem; color: {BRAND['muted']}; margin-top: 2px; }}
    .insight-card.amber {{ border-left-color: {BRAND['accent']}; }}
    .insight-card.blue {{ border-left-color: {BRAND['info']}; }}
    .insight-card.red  {{ border-left-color: {BRAND['danger']}; }}

    /* dataframe rounding */
    [data-testid="stDataFrame"] {{ border-radius: 12px; overflow: hidden; }}
    hr {{ border-color: {BRAND['line']}; }}

    /* ---- Mobile Responsiveness ---- */
    @media (max-width: 768px) {{
        .block-container {{ padding-top: 1rem !important; padding-left: 0.8rem !important; padding-right: 0.8rem !important; }}
        .hero {{ padding: 22px 18px; border-radius: 16px; margin-bottom: 16px; }}
        .hero h1 {{ font-size: 1.5rem !important; margin-bottom: 6px !important; line-height: 1.2 !important; }}
        .hero .tagline {{ font-size: 0.9rem !important; }}
        .hero .pill-row {{ gap: 8px; flex-direction: column; }}
        .hero .pill {{ font-size: 12px; padding: 6px 12px; align-self: flex-start; }}
        [data-testid="stMetric"] {{ padding: 12px 14px; border-radius: 12px; }}
        [data-testid="stMetricValue"] {{ font-size: 1.4rem !important; }}
        [data-testid="stMetricLabel"] {{ font-size: 0.75rem !important; }}
        [data-testid="stPlotlyChart"] {{ padding: 6px; border-radius: 12px; }}
        div[role="tablist"] > button[role="tab"] {{ font-size: 13px !important; padding: 10px 8px !important; }}
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
            # Flexible regex for DD-MM-YYYY, DD/MM/YYYY, YYYY-MM-DD, or dots
            if re.search(r"\b\d{1,4}[-./]\d{1,2}[-./]\d{1,4}\b", v_str):
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
                    # JUMP forward slightly to avoid parsing numbers inside this block as dates
                    row += 12
                    continue
        row += 1
    return pd.DataFrame(records)

def _load_local_csv():
    """Fallback data source used when no live Google Sheet / credentials are configured.

    Reads the most complete CSV bundled in the output/ folder so the dashboard can run
    offline (local development, demos, or when credentials are unavailable).
    """
    candidates = [
        Path("output") / "all_reports_combined.csv",
        Path("output") / "june26_clean.csv",
    ]
    for p in candidates:
        if p.exists():
            try:
                return pd.read_csv(p)
            except Exception:
                continue
    return None


# Load data (Google Sheet when configured, otherwise the bundled local CSV)
@st.cache_data
def load_data(gsheet_url: Optional[str] = None, gsheet_gid: Optional[str] = None, sa_file: Optional[str] = None):
    # If the user has provided a Google Sheet URL/ID, try that first
    sheet_id = _parse_sheet_id(gsheet_url) if gsheet_url else os.environ.get("GSHEET_ID")
    scopes = ["https://www.googleapis.com/auth/drive.readonly", "https://www.googleapis.com/auth/spreadsheets.readonly"]
    creds = _get_google_creds(scopes) if (sheet_id and service_account is not None) else None

    df = None
    if sheet_id and creds:
        try:
            authed = AuthorizedSession(creds)
            xls = _download_gsheet_excel(sheet_id)
            all_dfs = []
            for sheet_name in xls.sheet_names:
                if sheet_name.lower() in {"birdweight", "trayweight", "sale", "final"}:
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
        except Exception as e:
            st.warning(f"⚠️ Could not read the Google Sheet ({e}). Showing bundled local data instead.")
            df = None

    # Fall back to the bundled local CSV when no live sheet/credentials are available
    if df is None or df.empty:
        df = _load_local_csv()

    if df is None or df.empty:
        st.error("No data source available.")
        st.info("💡 Configure `GSHEET_ID` + Google credentials, or keep a CSV in the `output/` folder.")
        st.stop()

    # Force conversion to datetime to ensure correct sorting and max() operations
    if "Date" in df.columns:
        df["Date"] = pd.to_datetime(df["Date"], dayfirst=True, errors="coerce")
        df = df.dropna(subset=["Date"])
    else:
        st.error("Data loaded successfully but no 'Date' column was found.")
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
st.sidebar.image("assets/vsf_logo.png", **STRETCH)

# Sidebar filters (friendly for non-technical users)
st.sidebar.markdown('<p class="sidebar-header">📅 Choose Time Frame</p>', unsafe_allow_html=True)

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

with st.sidebar.expander("⚙️ Advance Setting"):
    if st.button("🔄 Refresh Data", help="Fetch the latest data from Google Sheets immediately", **STRETCH):
        st.cache_data.clear()
        st.success("Fetching fresh data...")
        st.rerun()

    # Weight aggregation controls: bird/tray sheets are weekly in the source
    aggregate_weights_weekly = st.checkbox(
        "Aggregate weight data by week (use for Bird/Tray sheets)",
        value=True,
    )

    # Date limiting controls
    st.markdown("---")
    st.subheader("🛡️ Data Accuracy Guard")
    date_limit_mode = st.radio(
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
        sheet_choice = st.selectbox(
            "Pick sheet to use for the end date",
            options=sorted(sheet_max_dates.keys()),
        )
        selected_cap_date = sheet_max_dates.get(sheet_choice).date() if sheet_choice else None
    elif date_limit_mode == "Choose a finish date":
        selected_cap_date = st.date_input(
            "Choose the last date to include",
            value=combined_max,
            min_value=df["Date"].min().date(),
            max_value=combined_max,
        )

    if selected_cap_date:
        st.write(f"Including data up to: {selected_cap_date}")


# Filter data
filtered_df = df[
    (df["Date"].dt.date >= date_range[0]) &
    (df["Date"].dt.date <= date_range[1]) &
    (df["Shed"].isin(selected_sheds))
]

# Apply cap from date limiter if set
if selected_cap_date:
    filtered_df = filtered_df[filtered_df["Date"].dt.date <= selected_cap_date]

# Hero banner header
quotes = [
    "Premium Poultry, Premium Care, Premium Results",
    "Every Egg Tells a Story of Excellence",
    "From Farm to Table with Precision",
    "Healthy Birds, Happy Farmers, Great Yields",
    "Analytics-Driven Poultry Excellence",
]
quote = random.choice(quotes)
latest_date = filtered_df["Date"].max()
latest_label = latest_date.strftime("%B %d, %Y") if pd.notna(latest_date) else "N/A"
sheds_label = ", ".join(selected_sheds) if selected_sheds else "None"

st.markdown(
    f"""
    <div class="hero">
        <h1>🥚 Layer Farm Analytics 🐔</h1>
        <marquee class="tagline" scrollamount="6">✨ {quote}</marquee>
        <div class="pill-row">
            <span class="pill">🗓️ <b>{date_range[0]}</b> → <b>{date_range[1]}</b></span>
            <span class="pill">🏠 Sheds: <b>{sheds_label}</b></span>
            <span class="pill">✅ Latest data: <b>{latest_label}</b></span>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
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

st.markdown(
    f'<div class="section-title">🚀 Latest Results — {latest_date.strftime("%d %B, %Y")}</div>',
    unsafe_allow_html=True,
)
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
        st.markdown('<div class="section-title">🥚 Daily Fresh Eggs Production</div>', unsafe_allow_html=True)
        daily_eggs = filtered_df.groupby("Date")["Fresh_Eggs"].sum().reset_index()
        fig_eggs = px.line(daily_eggs, x="Date", y="Fresh_Eggs", markers=True)
        fig_eggs.update_traces(line_color=BRAND["primary"], fill="tozeroy",
                               fillcolor="rgba(5,150,105,0.08)")
        fig_eggs.update_yaxes(title_text="Fresh Eggs")
        st.plotly_chart(style_chart(fig_eggs, show_legend=False), **STRETCH)

    with col2:
        st.markdown('<div class="section-title">🐔 Daily Bird Balance</div>', unsafe_allow_html=True)
        daily_birds = filtered_df.groupby("Date")["Bird_Balance"].sum().reset_index()
        fig_birds = px.line(daily_birds, x="Date", y="Bird_Balance", markers=True)
        fig_birds.update_traces(line_color=BRAND["info"], fill="tozeroy",
                                fillcolor="rgba(59,130,246,0.08)")
        fig_birds.update_yaxes(title_text="Bird Balance")
        st.plotly_chart(style_chart(fig_birds, show_legend=False), **STRETCH)

    col1, col2 = st.columns(2)

    with col1:
        st.markdown('<div class="section-title">📈 Production Percentage Trend</div>', unsafe_allow_html=True)
        prod_pct = filtered_df.groupby("Date")["Production_Pct"].mean().reset_index()
        fig_prod = px.line(prod_pct, x="Date", y="Production_Pct", markers=True)
        fig_prod.update_traces(line_color=BRAND["violet"])
        fig_prod.update_yaxes(title_text="Production %")
        st.plotly_chart(style_chart(fig_prod, show_legend=False), **STRETCH)

    with col2:
        st.markdown('<div class="section-title">⚠️ Mortality Rate Trend</div>', unsafe_allow_html=True)
        mortality = filtered_df.groupby("Date")["Mortality"].sum().reset_index()
        fig_mort = px.bar(mortality, x="Date", y="Mortality")
        fig_mort.update_traces(marker_color=BRAND["danger"], marker_line_width=0)
        fig_mort.update_yaxes(title_text="Mortality Count")
        st.plotly_chart(style_chart(fig_mort, show_legend=False), **STRETCH)

    if "Bird_Weight" in filtered_df.columns or "Tray_Weight" in filtered_df.columns:
        col1, col2 = st.columns(2)
        with col1:
            if "Bird_Weight" in filtered_df.columns:
                st.markdown('<div class="section-title">⚖️ Avg Bird Weight</div>', unsafe_allow_html=True)
                if aggregate_weights_weekly:
                    bw = filtered_df.copy()
                    bw["_week_start"] = bw["Date"].dt.to_period("W").apply(lambda p: p.start_time)
                    bird_weight = bw.groupby("_week_start")["Bird_Weight"].mean().reset_index()
                    bird_weight = bird_weight.rename(columns={"_week_start": "Date"})
                else:
                    bird_weight = filtered_df.groupby("Date")["Bird_Weight"].mean().reset_index()

                fig_bird_weight = px.line(bird_weight, x="Date", y="Bird_Weight", markers=True)
                fig_bird_weight.update_traces(line_color=BRAND["accent"])
                fig_bird_weight.update_yaxes(title_text="Bird Weight (g)")
                st.plotly_chart(style_chart(fig_bird_weight, show_legend=False), **STRETCH)
            else:
                st.info("No Bird Weight data available.")

        with col2:
            if "Tray_Weight" in filtered_df.columns:
                st.markdown('<div class="section-title">⚖️ Avg Tray Weight</div>', unsafe_allow_html=True)
                if aggregate_weights_weekly:
                    tw = filtered_df.copy()
                    tw["_week_start"] = tw["Date"].dt.to_period("W").apply(lambda p: p.start_time)
                    tray_weight = tw.groupby("_week_start")["Tray_Weight"].mean().reset_index()
                    tray_weight = tray_weight.rename(columns={"_week_start": "Date"})
                else:
                    tray_weight = filtered_df.groupby("Date")["Tray_Weight"].mean().reset_index()

                fig_tray_weight = px.line(tray_weight, x="Date", y="Tray_Weight", markers=True)
                fig_tray_weight.update_traces(line_color="#14b8a6")
                fig_tray_weight.update_yaxes(title_text="Tray Weight (g)")
                st.plotly_chart(style_chart(fig_tray_weight, show_legend=False), **STRETCH)
            else:
                st.info("No Tray Weight data available.")

# Tab 2: Trends Analysis
with tab2:
    st.markdown('<div class="section-title">📊 Comparative Metrics Over Time</div>', unsafe_allow_html=True)

    col1, col2 = st.columns(2)

    with col1:
        st.markdown('<div class="section-title">🥚 Egg Quality Analysis</div>', unsafe_allow_html=True)
        daily_egg_types = filtered_df.groupby("Date")[["Fresh_Eggs", "Crack_Eggs", "Leaker_Eggs"]].sum().reset_index()

        fig_egg_comp = go.Figure()
        # Primary Axis: Fresh Eggs
        fig_egg_comp.add_trace(go.Scatter(x=daily_egg_types["Date"], y=daily_egg_types["Fresh_Eggs"], name="Fresh Eggs", line=dict(color=BRAND['primary'], width=3), fill="tozeroy", fillcolor="rgba(5,150,105,0.07)"))
        # Secondary Axis: Crack and Leaker
        fig_egg_comp.add_trace(go.Scatter(x=daily_egg_types["Date"], y=daily_egg_types["Crack_Eggs"], name="Crack Eggs", yaxis="y2", line=dict(color=BRAND['accent'], dash='dot')))
        fig_egg_comp.add_trace(go.Scatter(x=daily_egg_types["Date"], y=daily_egg_types["Leaker_Eggs"], name="Leaker Eggs", yaxis="y2", line=dict(color=BRAND['danger'], dash='dash')))

        fig_egg_comp.update_layout(
            yaxis=dict(title="Fresh Eggs", side="left", tickformat=","),
            yaxis2=dict(title="Crack / Leaker", overlaying="y", side="right", showgrid=False, tickformat=","),
        )
        st.plotly_chart(style_chart(fig_egg_comp), **STRETCH)

    with col2:
        st.markdown('<div class="section-title">🧺 Tray Types Distribution</div>', unsafe_allow_html=True)
        tray_data = filtered_df.groupby("Date")[["Jumbo_Tray", "Fresh_Tray"]].sum().reset_index()

        fig_trays = go.Figure()
        # Primary Axis: Fresh Trays
        fig_trays.add_trace(go.Bar(x=tray_data["Date"], y=tray_data["Fresh_Tray"], name="Fresh Trays", marker_color=BRAND['info'], marker_line_width=0, opacity=0.85))
        # Secondary Axis: Jumbo Trays
        fig_trays.add_trace(go.Scatter(x=tray_data["Date"], y=tray_data["Jumbo_Tray"], name="Jumbo Trays", yaxis="y2", line=dict(color=BRAND['violet'], width=3)))

        fig_trays.update_layout(
            yaxis=dict(title="Fresh Trays", tickformat=","),
            yaxis2=dict(title="Jumbo Trays", overlaying="y", side="right", showgrid=False, tickformat=","),
        )
        st.plotly_chart(style_chart(fig_trays), **STRETCH)

    st.markdown('<div class="section-title">🌱 Age vs Production Performance</div>', unsafe_allow_html=True)
    age_prod = filtered_df.groupby("Date").agg({
        "Age": "mean",
        "Production_Pct": "mean"
    }).reset_index()

    fig_age = go.Figure()
    fig_age.add_trace(go.Scatter(x=age_prod["Date"], y=age_prod["Age"], name="Avg Age", yaxis="y1", line=dict(color=BRAND['accent'], width=3)))
    fig_age.add_trace(go.Scatter(x=age_prod["Date"], y=age_prod["Production_Pct"], name="Production %", yaxis="y2", line=dict(color=BRAND['primary'], width=3)))
    fig_age.update_layout(
        xaxis=dict(title="Date"),
        yaxis=dict(title="Age (weeks)", side="left"),
        yaxis2=dict(title="Production %", overlaying="y", side="right", showgrid=False),
    )
    st.plotly_chart(style_chart(fig_age, height=360), **STRETCH)

# Tab 3: Shed Details
with tab3:
    st.markdown('<div class="section-title">🐔 Performance by Shed</div>', unsafe_allow_html=True)

    selected_shed = st.selectbox(
        "Select Shed for Detailed Analysis",
        sorted(filtered_df["Shed"].unique())
    )

    shed_data = filtered_df[filtered_df["Shed"] == selected_shed]

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Total Fresh Eggs", f"{int(shed_data['Fresh_Eggs'].sum()):,}")
    with col2:
        st.metric("Avg Age", f"{shed_data['Age'].mean():.1f} weeks")
    with col3:
        st.metric("Avg Production %", f"{shed_data['Production_Pct'].mean():.2f}%")
    with col4:
        st.metric("Total Mortality", f"{int(shed_data['Mortality'].sum()):,}")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown(f'<div class="section-title">🥚 {selected_shed} — Fresh Eggs</div>', unsafe_allow_html=True)
        fig_shed_eggs = px.line(shed_data.sort_values("Date"), x="Date", y="Fresh_Eggs", markers=True)
        fig_shed_eggs.update_traces(line_color=BRAND["primary"], fill="tozeroy",
                                    fillcolor="rgba(5,150,105,0.08)")
        st.plotly_chart(style_chart(fig_shed_eggs, show_legend=False), **STRETCH)

    with col2:
        st.markdown(f'<div class="section-title">📈 {selected_shed} — Production %</div>', unsafe_allow_html=True)
        fig_shed_prod = px.line(shed_data.sort_values("Date"), x="Date", y="Production_Pct", markers=True)
        fig_shed_prod.update_traces(line_color=BRAND["violet"])
        st.plotly_chart(style_chart(fig_shed_prod, show_legend=False), **STRETCH)

    # Shed comparison
    st.markdown('<div class="section-title">🏆 Shed Comparison (Latest Date)</div>', unsafe_allow_html=True)
    latest_shed_data = filtered_df[filtered_df["Date"] == latest_date]

    col1, col2 = st.columns(2)

    with col1:
        fig_comp_eggs = px.bar(latest_shed_data, x="Shed", y="Fresh_Eggs", color="Shed")
        fig_comp_eggs.update_traces(marker_line_width=0)
        st.plotly_chart(style_chart(fig_comp_eggs, show_legend=False), **STRETCH)

    with col2:
        fig_comp_prod = px.bar(latest_shed_data, x="Shed", y="Production_Pct", color="Shed")
        fig_comp_prod.update_traces(marker_line_width=0)
        st.plotly_chart(style_chart(fig_comp_prod, show_legend=False), **STRETCH)

# Tab 4: Data Table
with tab4:
    st.markdown('<div class="section-title">📋 Detailed Data Table</div>', unsafe_allow_html=True)
    
    # Sort options
    col1, col2, col3 = st.columns(3)
    
    with col1:
        sort_by = st.selectbox(
            "Sort by",
             ["Date", "Shed", "Fresh_Eggs", "Production_Pct", "Bird_Balance"],
             key="dt_sort_by"
        )
    
    with col2:
        sort_order = st.selectbox("Order", ["Descending", "Ascending"], key="dt_sort_order")
    
    with col3:
        max_rows = max(1, len(filtered_df))
        rows_to_show = st.slider("Rows to display", 1, max_rows, min(50, max_rows), key="dt_rows_to_show")
    
    ascending = sort_order == "Ascending"
    #display_df = filtered_df.sort_values(sort_by, ascending=ascending).head(rows_to_show).copy()

    if sort_by == "Date":
        #Ensure sheds are always in 1, 2, 3, 4 order for the same date
        display_df = filtered_df.sort_values(["Date", "Shed"], ascending=[ascending, True]).head(rows_to_show).copy()
    else:
        display_df = filtered_df.sort_values(sort_by, ascending=ascending).head(rows_to_show).copy()


     # Adjust row number index to start from 1 instead of 0
    display_df.index = range(1, len(display_df) + 1)

    # Format Date column to show only YYYY-MM-DD for the data table
    if "Date" in display_df.columns:
        try:
            display_df["Date"] = display_df["Date"].dt.strftime("%Y-%m-%d")
        except Exception:
            display_df["Date"] = display_df["Date"].astype(str)

    #st.dataframe(display_df, height=400, **STRETCH)
    
    def highlight_latest(row):
        #Highlight the first 4 rows to emphasize the most recent data when default sorted
        if sort_by == "Date" and sort_order == "Descending" and row.name <= 4:
            return ['background-color: rgba(5, 150, 105, 0.12)'] * len(row)
        return [''] * len(row)

            
    # Restore clean number formatting that was lost when applying the style
    format_dict = {
        "Fresh_Eggs": "{:,.0f}", "Crack_Eggs": "{:,.0f}", "Leaker_Eggs": "{:,.0f}",
        "Jumbo_Tray": "{:,.0f}", "Fresh_Tray": "{:,.0f}", "Bird_Balance": "{:,.0f}",
        "Mortality": "{:,.0f}", "Age": "{:,.1f}", "Production_Pct": "{:,.2f}",
        "Bird_Weight": "{:,.1f}", "Tray_Weight": "{:,.1f}"
    }
    active_formats = {c: format_dict[c] for c in display_df.columns if c in format_dict}
    
    styled_df = display_df.style.apply(highlight_latest, axis=1).format(active_formats, na_rep="")

    st.dataframe(styled_df, height=400, **STRETCH)
    #st.dataframe(display_df.style.apply(highlight_latest, axis=1), height=400, **STRETCH)
   

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
    st.markdown('<div class="section-title">💡 Key Insights</div>', unsafe_allow_html=True)

    def insight_card(label, main, sub, tone=""):
        st.markdown(
            f"""<div class="insight-card {tone}">
                <div class="ic-label">{label}</div>
                <div class="ic-main">{main}</div>
                <div class="ic-sub">{sub}</div>
            </div>""",
            unsafe_allow_html=True,
        )

    daily_sum = filtered_df.groupby("Date")["Fresh_Eggs"].sum()
    top_day, top_eggs = daily_sum.idxmax(), daily_sum.max()
    low_day, low_eggs = daily_sum.idxmin(), daily_sum.min()
    shed_prod = filtered_df.groupby("Shed")["Production_Pct"].mean()
    best_shed, best_prod = shed_prod.idxmax(), shed_prod.max()
    shed_mort = filtered_df.groupby("Shed")["Mortality"].sum()
    high_mort_shed, high_mort = shed_mort.idxmax(), shed_mort.max()

    col1, col2 = st.columns(2)
    with col1:
        insight_card("🏆 Highest Production Day", f"{int(top_eggs):,} eggs", f"on {top_day.date()}")
    with col2:
        insight_card("📉 Lowest Production Day", f"{int(low_eggs):,} eggs", f"on {low_day.date()}", "amber")

    st.write("")
    col1, col2 = st.columns(2)
    with col1:
        insight_card("⭐ Best Performing Shed", best_shed, f"Avg production {best_prod:.2f}%", "blue")
    with col2:
        insight_card("⚠️ Highest Mortality Shed", high_mort_shed, f"Total mortality {int(high_mort):,}", "red")

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
    
    st.markdown('<div class="section-title">📈 Farm Performance Benchmarks</div>', unsafe_allow_html=True)
    st.caption("Typical performance versus the best and worst days in your selected range.")
    
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
        **STRETCH
    )

# Footer
st.markdown(
    """
    <div style="margin-top:28px; border-radius:18px; padding:22px 26px;
         background:linear-gradient(120deg,#0f1f17,#064e3b); color:#e8f5ee;
         box-shadow:0 12px 30px rgba(6,78,59,0.25);">
        <div style="font-size:1.05rem; font-weight:800; color:#fff; margin-bottom:8px;">VSF - Layer Farm</div>
        <div style="display:flex; flex-wrap:wrap; gap:28px; font-size:.92rem; line-height:1.7;">
            <div>
                <div style="opacity:.7; text-transform:uppercase; font-size:.72rem; letter-spacing:.05em;">Owner</div>
                Late Sh Charan Singh S/O Ch VED Singh Singroha<br>
                Bharon Khera, Jind, Haryana - 126114
            </div>
            <div>
                <div style="opacity:.7; text-transform:uppercase; font-size:.72rem; letter-spacing:.05em;">Contact</div>
                📱 WhatsApp: +91 9992373885<br>
                ✉️ <a href="mailto:naveensingroha92@gmail.com" style="color:#a7f3d0 !important;">naveensingroha92@gmail.com</a>
            </div>
            <div>
                <div style="opacity:.7; text-transform:uppercase; font-size:.72rem; letter-spacing:.05em;">Developer</div>
                <div style="display:flex; gap:12px; margin-top:6px;">
                    <a href="https://www.linkedin.com/in/singroha/" target="_blank" style="color:#a7f3d0;" title="LinkedIn">
                        <svg xmlns="http://www.w3.org/2000/svg" width="22" height="22" fill="currentColor" viewBox="0 0 24 24"><path d="M19 0h-14c-2.761 0-5 2.239-5 5v14c0 2.761 2.239 5 5 5h14c2.762 0 5-2.239 5-5v-14c0-2.761-2.238-5-5-5zm-11 19h-3v-11h3v11zm-1.5-12.268c-.966 0-1.75-.79-1.75-1.764s.784-1.764 1.75-1.764 1.75.79 1.75 1.764-.783 1.764-1.75 1.764zm13.5 12.268h-3v-5.604c0-3.368-4-3.113-4 0v5.604h-3v-11h3v1.765c1.396-2.586 7-2.777 7 2.476v6.759z"/></svg>
                    </a>
                    <a href="https://github.com/Singroha-S" target="_blank" style="color:#a7f3d0;" title="GitHub">
                        <svg xmlns="http://www.w3.org/2000/svg" width="22" height="22" fill="currentColor" viewBox="0 0 24 24"><path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z"/></svg>
                    </a>
                </div>
            </div>
        </div>
        <div style="margin-top:20px; padding-top:14px; border-top:1px solid rgba(255,255,255,0.1); font-size:.8rem; opacity:.8; text-align:center;">
            © Copyright 2026 | VSF Pvt Ltd.
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)
