import streamlit as st
import pandas as pd
from sku_transfer_plan_refined_v2_with_summary import SKULevelTransferOptimizer
import io

st.set_page_config(layout="wide")
st.title("🏢 Retail Inventory Health & Transfer Optimization App")

st.markdown("Upload inventory file to analyze health and generate transfer plan.")

uploaded_file = st.file_uploader(
    "Upload InputSheetFormat.xlsx",
    type=["xlsx"]
)

if uploaded_file:

    df = pd.read_excel(uploaded_file)

    st.success("File uploaded successfully")

    # ================= EXECUTIVE KPIs =================
    total_stock = df["Stock"].sum()
    total_buffer = df["Buffer Stock"].sum()
    total_skus = df["SKU"].nunique()
    total_stores = df["Store"].nunique()

    excess_units = (df["Stock"] - df["Buffer Stock"])
    excess_units = excess_units[excess_units > 0].sum()

    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Total Stores", total_stores)
    col2.metric("Total SKUs", total_skus)
    col3.metric("Total Stock", int(total_stock))
    col4.metric("Total Buffer", int(total_buffer))
    col5.metric("Total Excess Units", int(excess_units))

    st.markdown("---")

    # ================= HEALTH SUMMARY =================
    optimizer = SKULevelTransferOptimizer(df)

    summary, cluster_summary, option_summary, broken_details = \
        optimizer.get_option_store_health_summary(df)

    broken_pct = summary["overall"]["broken_percentage"]

    st.subheader("Inventory Health Summary")
    st.metric("Broken Option %", f"{broken_pct:.2f}%")

    st.subheader("Broken by Cluster")
    st.dataframe(cluster_summary)

    st.subheader("Top Broken Options")
    st.dataframe(option_summary.head(20))

    st.markdown("---")

    # ================= RUN OPTIMIZER =================
    if st.button("🚀 Run Transfer Optimization"):

        with st.spinner("Running SKU-level transfer optimization..."):

            result = optimizer.run_dashboard_mode()

            transfer_df = result["transfer_df"]
            transfer_summary = result["transfer_summary"]
            cluster_summary = result["cluster_summary"]
            option_summary = result["option_summary"]
            broken_details = result["broken_details"]

        st.success("Optimization Complete")

        # ===== Transfer KPIs =====
        col1, col2, col3 = st.columns(3)
        col1.metric("Total Transfers", transfer_summary["Total Transfers"])
        col2.metric("Total Units Moved", transfer_summary["Total Units"])
        col3.metric("Same Cluster Transfers",
                    transfer_summary["Same Cluster Transfers"])

        st.markdown("---")
        st.subheader("Recommended Transfer Plan")
        st.dataframe(transfer_df)

        # ================= DOWNLOAD SECTION =================
        st.markdown("### 📥 Download Output Files")

        def convert_df(df):
            return df.to_csv(index=False).encode('utf-8')

        st.download_button(
            "Download Transfer Plan",
            convert_df(transfer_df),
            "transfer_plan.csv",
            "text/csv"
        )

        st.download_button(
            "Download Cluster Summary",
            convert_df(cluster_summary),
            "summary_by_cluster.csv",
            "text/csv"
        )

        st.download_button(
            "Download Option Summary",
            convert_df(option_summary),
            "summary_by_option.csv",
            "text/csv"
        )

        st.download_button(
            "Download Broken Details",
            convert_df(broken_details),
            "broken_combinations_detailed.csv",
            "text/csv"
        )