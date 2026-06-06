import base64
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from pathlib import Path
import random

# Page configuration
st.set_page_config(
    page_title="VSF Farm Analytics",
    page_icon="🐔",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Add logo
st.logo("assets/vsf_logo.png")

# Hide Streamlit chrome for professional appearance (keep sidebar toggle visible)
hide_st_style = """
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
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
    .stMetricValue, .stMetricLabel, .stMetricDelta {{ color: #111111 !important; }}
    .stButton>button, .stDownloadButton>button {{ color: #111111 !important; background-color: #eef2ff !important; }}
    a {{ color: #0a66c2 !important; }}
    .metric-large .stMetricValue {{font-size:28px}}
    /* Logo enlargement */
    [data-testid="stLogo"] img {{
        height: 140px !important;
        width: auto !important;
    }}
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
        padding: 6px 0 12px 0;
    }}
    .scrolling-quote {{
        display: inline-block;
        animation: scrollLeft 12s linear infinite;
        white-space: nowrap;
        font-weight: 600;
        color: #2d5016;
        padding: 8px 20px;
        font-size: clamp(20px, 4.5vw, 48px);
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

# Load data
@st.cache_data
def load_data():
    output_file = Path("output/all_reports_combined.csv")
    if not output_file.exists():
        st.error("Data file not found. Run `process_workbook.py` first.")
        st.stop()
    df = pd.read_csv(output_file)
    # Parse dates with dayfirst=True to match spreadsheets that use D/M/Y
    df["Date"] = pd.to_datetime(df["Date"], dayfirst=True)

    # Clean and coerce numeric columns that may contain stray text (e.g. "20 p", "%", commas)
    numeric_cols = [
        "Fresh_Eggs",
        "Crack_Eggs",
        "Jumbo_Tray",
        "Fresh_Tray",
        "Production_Pct",
        "Age",
        "Bird_Balance",
        "Mortality",
    ]
    

    for col in numeric_cols:
        if col in df.columns:
            # Convert to string, strip non-numeric characters (except dot and minus), then coerce
            df[col] = (
                df[col]
                .astype(str)
                .str.replace(r"[^0-9.\-]", "", regex=True)
            )
            df[col] = pd.to_numeric(df[col], errors="coerce")

    return df.sort_values("Date")

df = load_data()

# Helper: get per-sheet max dates from the source workbook
@st.cache_data
def get_sheet_max_dates():
    src = Path("data/Daily Report.xlsx")
    if not src.exists():
        return {}
    xls = pd.ExcelFile(src)
    exclude = {"Bird Weight","TRAY WEIGHT","Sale","Final","Sheet20","Sheet21","Sheet13","Sheet18","Sheet17","Sheet16","Sheet15"}
    sheets = [s for s in xls.sheet_names if s not in exclude and s.strip()]
    sheet_max = {}
    import datetime
    for s in sheets:
        df_s = pd.read_excel(src, sheet_name=s, header=None)
        dates = []
        for r in range(len(df_s)):
            row_values = df_s.iloc[r,:5].tolist()
            for v in row_values:
                if isinstance(v, (pd.Timestamp, datetime.datetime, datetime.date)):
                    dates.append(pd.to_datetime(v, dayfirst=True))
        if dates:
            sheet_max[s] = max(dates)
    return sheet_max

sheet_max_dates = get_sheet_max_dates()

# Sidebar filters (friendly for non-technical users)
st.sidebar.title("Filters — simple steps")
st.sidebar.markdown("""
- Pick a time range using the quick buttons below.
- Choose which sheds to view (or leave as All).
- Charts update automatically.
""")

# Simple presets for non-technical users
preset = st.sidebar.radio(
    "Quick range",
    options=["Latest day", "Last 7 days", "Last 30 days", "All data", "Custom"],
    index=2,
)

today_date = df["Date"].max().date()
if preset == "Latest day":
    default_start = today_date
elif preset == "Last 7 days":
    default_start = today_date - pd.Timedelta(days=6)
elif preset == "Last 30 days":
    default_start = today_date - pd.Timedelta(days=29)
elif preset == "All data":
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

selected_sheds = st.sidebar.multiselect(
    "Select Sheds",
    options=sorted(df["Shed"].unique()),
    default=sorted(df["Shed"].unique())
)

# Date limiting controls
st.sidebar.markdown("---")
st.sidebar.subheader("Show data through")
date_limit_mode = st.sidebar.radio(
    "Where should the data stop?",
    options=[
        "Show everything",
        "Stop at the latest report date",
        "Stop at one sheet's final date",
        "Choose a finish date",
    ],
    index=1,
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
st.markdown("---")

# Main title
st.title("🐔 VSF Farm Analytics")
latest_date = filtered_df["Date"].max()
st.caption(f"Last Updated: {latest_date.strftime('%B %d, %Y') if pd.notna(latest_date) else 'N/A'}")
st.markdown(f"**Data Range:** {date_range[0]} to {date_range[1]} | **Sheds:** {', '.join(selected_sheds)}")

# Friendly quick instructions for non-technical users
st.markdown(
        """
        <div class="big-instruction">
        <strong>How to use (3 quick steps):</strong>
        <ol>
            <li>Pick a time range on the left (Last 7 days is a good start).</li>
            <li>Select one or more sheds (or leave as All).</li>
            <li>Look at the big numbers at top and the charts below — no clicks needed.</li>
        </ol>
        </div>
        """,
        unsafe_allow_html=True,
)

with st.expander("Need a quick explanation? (click)"):
        st.write("This dashboard shows eggs, bird count, mortality and production percentage. Use simple buttons on the left to change the time range.")

# Key metrics row
latest_date = filtered_df["Date"].max()
today_data = filtered_df[filtered_df["Date"] == latest_date]

col1, col2, col3, col4, col5 = st.columns(5)

with col1:
    st.metric(
        "Total Birds",
        f"{int(today_data['Bird_Balance'].sum()):,}",
        delta=None
    )

with col2:
    st.metric(
        "Fresh Eggs",
        f"{int(today_data['Fresh_Eggs'].sum()):,}",
        delta=None
    )

with col3:
    st.metric(
        "Mortality",
        f"{int(today_data['Mortality'].sum())}",
        delta=None
    )

with col4:
    st.metric(
        "Avg Production %",
        f"{today_data['Production_Pct'].mean():.2f}%",
        delta=None
    )

with col5:
    st.metric(
        "Total Fresh Trays",
        f"{int(today_data['Fresh_Tray'].sum())}",
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

# Tab 2: Trends Analysis
with tab2:
    st.subheader("Comparative Metrics Over Time")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Fresh Eggs vs Crack Eggs")
        daily_egg_types = filtered_df.groupby("Date")[["Fresh_Eggs", "Crack_Eggs"]].sum().reset_index()
        fig_egg_comp = px.area(
            daily_egg_types,
            x="Date",
            y=["Fresh_Eggs", "Crack_Eggs"],
            title="Fresh vs Crack Eggs"
        )
        st.plotly_chart(fig_egg_comp, use_container_width=True)
    
    with col2:
        st.subheader("Tray Types Distribution")
        tray_data = filtered_df.groupby("Date")[["Jumbo_Tray", "Fresh_Tray"]].sum().reset_index()
        fig_trays = px.area(
            tray_data,
            x="Date",
            y=["Jumbo_Tray", "Fresh_Tray"],
            title="Jumbo vs Fresh Trays"
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
    
    st.write("**Summary Statistics**")
    summary = filtered_df[["Age", "Bird_Balance", "Fresh_Eggs", "Mortality", "Production_Pct"]].describe()
    st.dataframe(summary, use_container_width=True)

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
