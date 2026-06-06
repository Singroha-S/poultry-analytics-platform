import streamlit as st
import pandas as pd

df = pd.read_csv(
    "output/june26_clean.csv"
)

latest_date = df["Date"].max()

today = df[
    df["Date"] == latest_date
]

st.title("🐔 Layer Farm Dashboard")

col1, col2, col3, col4 = st.columns(4)

col1.metric(
    "Birds",
    int(today["Bird_Balance"].sum())
)

col2.metric(
    "Fresh Eggs",
    int(today["Fresh_Eggs"].sum())
)

col3.metric(
    "Mortality",
    int(today["Mortality"].sum())
)

col4.metric(
    "Production %",
    round(
        today["Production_Pct"].mean(),
        2
    )
)

st.divider()

st.subheader("Daily Production")

daily_prod = (
    df.groupby("Date")
      ["Fresh_Eggs"]
      .sum()
      .reset_index()
)

st.line_chart(
    daily_prod,
    x="Date",
    y="Fresh_Eggs"
)