import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from pathlib import Path

# Page configuration
st.set_page_config(
    page_title="Farm Dashboard",
    page_icon="🐔",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Load data
@st.cache_data
def load_data():
    output_file = Path("output/all_reports_combined.csv")
    if not output_file.exists():
        st.error("Data file not found. Run `process_workbook.py` first.")
        st.stop()
    df = pd.read_csv(output_file)
    df["Date"] = pd.to_datetime(df["Date"])

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

# Sidebar filters
st.sidebar.title("🔧 Filters")

date_range = st.sidebar.date_input(
    "Date Range",
    value=(df["Date"].min().date(), df["Date"].max().date()),
    min_value=df["Date"].min().date(),
    max_value=df["Date"].max().date()
)

selected_sheds = st.sidebar.multiselect(
    "Select Sheds",
    options=sorted(df["Shed"].unique()),
    default=sorted(df["Shed"].unique())
)

# Filter data
filtered_df = df[
    (df["Date"].dt.date >= date_range[0]) &
    (df["Date"].dt.date <= date_range[1]) &
    (df["Shed"].isin(selected_sheds))
]

# Main title
st.title("🐔 Layer Farm Dashboard")
st.markdown(f"**Data Range:** {date_range[0]} to {date_range[1]} | **Sheds:** {', '.join(selected_sheds)}")

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
    display_df = filtered_df.sort_values(sort_by, ascending=ascending).head(rows_to_show)
    
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
st.caption(f"Data updated: {df['Date'].max().date()} | Total Records: {len(filtered_df)}")
