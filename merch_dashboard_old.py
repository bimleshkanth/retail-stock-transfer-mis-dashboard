import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="Merchandise Sales Dashboard", layout="wide")

st.title("📊 Merchandise Sales Performance Dashboard")

# ===============================
# Load Data
# ===============================
uploaded_file = st.file_uploader("Upload Sales CSV File", type=["csv"])

if uploaded_file:

    df = pd.read_csv(uploaded_file)

    # ===============================
    # Sidebar Filters
    # ===============================
    st.sidebar.header("🔎 Filters")

    store_filter = st.sidebar.multiselect(
        "Select Store",
        options=df["Store"].unique(),
        default=df["Store"].unique()
    )

    manager_filter = st.sidebar.multiselect(
        "Select Cluster Manager",
        options=df["Cluster Manager"].unique(),
        default=df["Cluster Manager"].unique()
    )

    colour_filter = st.sidebar.multiselect(
        "Select Colour",
        options=df["Colour"].unique(),
        default=df["Colour"].unique()
    )

    size_filter = st.sidebar.multiselect(
        "Select Size",
        options=df["Size"].unique(),
        default=df["Size"].unique()
    )

    # Apply filters
    filtered_df = df[
        (df["Store"].isin(store_filter)) &
        (df["Cluster Manager"].isin(manager_filter)) &
        (df["Colour"].isin(colour_filter)) &
        (df["Size"].isin(size_filter))
    ]

    # ===============================
    # KPIs
    # ===============================
    total_sales = filtered_df["Sales Value"].sum()
    total_qty = filtered_df["Sales Qty"].sum()
    total_stock = filtered_df["Stk Qty"].sum()

    sell_through = (
        total_qty / (total_qty + total_stock) * 100
        if (total_qty + total_stock) > 0 else 0
    )

    col1, col2, col3, col4 = st.columns(4)

    col1.metric("💰 Total Sales Value", f"₹ {total_sales:,.0f}")
    col2.metric("📦 Total Sales Qty", f"{total_qty:,.0f}")
    col3.metric("🏬 Total Stock Qty", f"{total_stock:,.0f}")
    col4.metric("🔥 Sell Through %", f"{sell_through:.2f}%")

    st.markdown("---")

    # ===============================
    # Sales by Store
    # ===============================
    store_sales = filtered_df.groupby("Store")["Sales Value"].sum().reset_index()
    store_sales = store_sales.sort_values("Sales Value", ascending=False)

    fig_store = px.bar(
        store_sales,
        x="Store",
        y="Sales Value",
        title="Sales by Store"
    )
    st.plotly_chart(fig_store, use_container_width=True)

    # ===============================
    # Sales by Cluster Manager
    # ===============================
    manager_sales = filtered_df.groupby("Cluster Manager")["Sales Value"].sum().reset_index()

    fig_manager = px.bar(
        manager_sales,
        x="Cluster Manager",
        y="Sales Value",
        title="Sales by Cluster Manager"
    )
    st.plotly_chart(fig_manager, use_container_width=True)

    # ===============================
    # Colour Performance
    # ===============================
    colour_sales = filtered_df.groupby("Colour")["Sales Value"].sum().reset_index()

    fig_colour = px.pie(
        colour_sales,
        names="Colour",
        values="Sales Value",
        title="Sales Contribution by Colour"
    )
    st.plotly_chart(fig_colour, use_container_width=True)

    # ===============================
    # Size Performance
    # ===============================
    size_sales = filtered_df.groupby("Size")["Sales Qty"].sum().reset_index()

    fig_size = px.bar(
        size_sales,
        x="Size",
        y="Sales Qty",
        title="Sales Qty by Size"
    )
    st.plotly_chart(fig_size, use_container_width=True)

    # ===============================
    # Stock vs Sales Analysis
    # ===============================
    sku_analysis = filtered_df.groupby(
        ["Design No", "Colour", "Size"]
    ).agg({
        "Sales Qty": "sum",
        "Stk Qty": "sum"
    }).reset_index()

    fig_scatter = px.scatter(
        sku_analysis,
        x="Stk Qty",
        y="Sales Qty",
        title="Stock vs Sales Analysis (Identify Overstock)",
        hover_data=["Design No", "Colour", "Size"]
    )

    st.plotly_chart(fig_scatter, use_container_width=True)

    # ===============================
    # Top 10 Stores
    # ===============================
    st.subheader("🏆 Top 10 Performing Stores")

    top10 = store_sales.head(10)
    st.dataframe(top10)

    # ===============================
    # Download Button
    # ===============================
    st.download_button(
        "Download Filtered Data",
        filtered_df.to_csv(index=False),
        file_name="filtered_merch_data.csv"
    )

else:
    st.info("Please upload the DummySalesCSV.csv file to view the dashboard.")