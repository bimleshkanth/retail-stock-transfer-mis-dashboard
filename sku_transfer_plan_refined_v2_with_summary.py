import pandas as pd
import numpy as np
from typing import List, Dict, Tuple
from dataclasses import dataclass
from enum import Enum
from datetime import datetime

class TransferPriority(Enum):
    SAME_CLUSTER = 1
    DIFFERENT_CLUSTER = 2

@dataclass
class SKUTransferPlan:
    """Represents a single SKU-level transfer"""
    transfer_id: str
    from_store: str
    from_cluster: str
    from_sku_sales: float  # Daily sales at source
    to_store: str
    to_cluster: str
    to_sku_sales: float    # Daily sales at destination
    sku: str
    source_stock: int
    source_buffer: int
    dest_stock: int
    dest_buffer: int
    quantity_to_transfer: int
    priority: TransferPriority

class SKULevelTransferOptimizer:
    """
    Refined SKU-level transfer optimizer with proper business logic
    
    NEW LOGIC:
    - Identify excess/shortage at SKU level (not option level)
    - Prioritize sources: same cluster first, then LOWEST sales
    - Prioritize destinations: same cluster first, then HIGHEST sales
    - Validate transfers at SKU level only
    """
    
    def __init__(self, df: pd.DataFrame):
        self.df = df.copy()
        self.sku_transfer_plans: List[SKUTransferPlan] = []
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    def preprocess_data(self) -> pd.DataFrame:
        """Preprocess and validate input data"""
        df = self.df.copy()
        
        numeric_cols = ['Sales', 'Stock', 'Buffer Stock', 'Option Stk', 'Option Buffer']
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
        
        df = df.fillna(0)
        return df
    
    # ========================================================================
    # SECTION 1: SUMMARY STATISTICS
    # ========================================================================
    
    def get_option_store_health_summary(self, df: pd.DataFrame) -> Dict:
        """
        Generate summary statistics for (Option + Store) combinations
        
        Shows:
        - Total unique (Option + Store) combinations
        - Number of broken combinations
        - Number of healthy combinations
        - Breakdown by cluster
        - Breakdown by option
        """
        
        df = self.preprocess_data()
        
        # ============ STEP 1: GET UNIQUE (OPTION + STORE) COMBINATIONS ============
        
        # Group by Store and Option to get unique combinations
        option_store_combinations = df.groupby(['Store', 'Option', 'Cluster', 'BOH']).agg({
            'Option Stk': 'first',
            'Option Buffer': 'first',
            'Sales': 'sum'  # Total sales across all sizes for this option
        }).reset_index()
        
        # ============ STEP 2: OVERALL SUMMARY ============
        
        total_combinations = len(option_store_combinations)
        broken_combinations = len(option_store_combinations[option_store_combinations['BOH'] == 'Broken'])
        healthy_combinations = len(option_store_combinations[option_store_combinations['BOH'] == 'Healthy'])
        
        # ============ STEP 3: BREAKDOWN BY CLUSTER ============
        
        cluster_summary = option_store_combinations.groupby('Cluster').agg({
            'BOH': lambda x: (x == 'Broken').sum(),
            'Store': 'count'
        }).reset_index()
        cluster_summary.columns = ['Cluster', 'Broken_Count', 'Total_Count']
        cluster_summary['Healthy_Count'] = cluster_summary['Total_Count'] - cluster_summary['Broken_Count']
        
        # ============ STEP 4: BREAKDOWN BY OPTION ============
        
        option_summary = option_store_combinations.groupby('Option').agg({
            'BOH': lambda x: (x == 'Broken').sum(),
            'Store': 'count'
        }).reset_index()
        option_summary.columns = ['Option', 'Broken_Count', 'Total_Count']
        option_summary['Healthy_Count'] = option_summary['Total_Count'] - option_summary['Broken_Count']
        option_summary = option_summary.sort_values('Broken_Count', ascending=False)
        
        # ============ STEP 5: DETAILED BROKEN COMBINATIONS ============
        
        broken_details = option_store_combinations[option_store_combinations['BOH'] == 'Broken'].copy()
        broken_details['Excess_Qty'] = broken_details['Option Stk'] - broken_details['Option Buffer']
        broken_details = broken_details.sort_values('Excess_Qty', ascending=False)
        
        # ============ STEP 6: CREATE SUMMARY DICTIONARY ============
        
        summary = {
            'overall': {
                'total_combinations': total_combinations,
                'broken_count': broken_combinations,
                'healthy_count': healthy_combinations,
                'broken_percentage': round((broken_combinations / total_combinations * 100), 2) if total_combinations > 0 else 0,
                'healthy_percentage': round((healthy_combinations / total_combinations * 100), 2) if total_combinations > 0 else 0
            },
            'by_cluster': cluster_summary.to_dict('records'),
            'by_option': option_summary.to_dict('records'),
            'broken_details': broken_details[['Store', 'Cluster', 'Option', 'Option Stk', 'Option Buffer', 'Excess_Qty', 'Sales']].to_dict('records'),
            'total_excess_quantity': int(broken_details['Excess_Qty'].sum())
        }
        
        return summary, cluster_summary, option_summary, broken_details
    
    def print_option_store_health_summary(self, summary: Dict, cluster_summary: pd.DataFrame, 
                                          option_summary: pd.DataFrame, broken_details: pd.DataFrame):
        """
        Pretty print the summary statistics
        """
        
        print("\n" + "="*90)
        print("OPTION + STORE COMBINATION HEALTH SUMMARY")
        print("="*90)
        
        # ============ OVERALL STATISTICS ============
        
        print("\n📊 OVERALL STATISTICS")
        print("-" * 90)
        
        overall = summary['overall']
        print(f"Total (Option + Store) Combinations: {overall['total_combinations']}")
        print(f"  ├─ Broken: {overall['broken_count']} ({overall['broken_percentage']}%)")
        print(f"  └─ Healthy: {overall['healthy_count']} ({overall['healthy_percentage']}%)")
        print(f"\nTotal Excess Quantity to Transfer: {summary['total_excess_quantity']} units")
        
        # ============ BREAKDOWN BY CLUSTER ============
        
        print("\n\n🌍 BREAKDOWN BY CLUSTER")
        print("-" * 90)
        print(f"{'Cluster':<20} {'Broken':<15} {'Healthy':<15} {'Total':<15}")
        print("-" * 90)
        
        for _, row in cluster_summary.iterrows():
            print(f"{row['Cluster']:<20} {row['Broken_Count']:<15} {row['Healthy_Count']:<15} {row['Total_Count']:<15}")
        
        print("-" * 90)
        print(f"{'TOTAL':<20} {cluster_summary['Broken_Count'].sum():<15} {cluster_summary['Healthy_Count'].sum():<15} {cluster_summary['Total_Count'].sum():<15}")
        
        # ============ BREAKDOWN BY OPTION ============
        
        print("\n\n📦 BREAKDOWN BY OPTION (Top 20)")
        print("-" * 90)
        print(f"{'Option':<25} {'Broken':<15} {'Healthy':<15} {'Total':<15}")
        print("-" * 90)
        
        for _, row in option_summary.head(20).iterrows():
            print(f"{row['Option']:<25} {int(row['Broken_Count']):<15} {int(row['Healthy_Count']):<15} {int(row['Total_Count']):<15}")
        
        if len(option_summary) > 20:
            print(f"... and {len(option_summary) - 20} more options")
        
        print("-" * 90)
        print(f"{'TOTAL':<25} {int(option_summary['Broken_Count'].sum()):<15} {int(option_summary['Healthy_Count'].sum()):<15} {int(option_summary['Total_Count'].sum()):<15}")
        
        # ============ DETAILED BROKEN COMBINATIONS ============
        
        print("\n\n🚨 BROKEN COMBINATIONS (Top 20 by Excess Quantity)")
        print("-" * 90)
        print(f"{'Store':<15} {'Cluster':<12} {'Option':<20} {'Option Stk':<12} {'Buffer':<10} {'Excess':<10}")
        print("-" * 90)
        
        for _, row in broken_details.head(20).iterrows():
            print(f"{row['Store']:<15} {row['Cluster']:<12} {row['Option']:<20} {int(row['Option Stk']):<12} {int(row['Option Buffer']):<10} {int(row['Excess_Qty']):<10}")
        
        if len(broken_details) > 20:
            print(f"... and {len(broken_details) - 20} more broken combinations")
        
        print("-" * 90)
        print(f"Total Broken Combinations: {len(broken_details)}")
        print(f"Total Excess Quantity: {int(broken_details['Excess_Qty'].sum())} units")
    
    def export_summary_to_csv(self, cluster_summary: pd.DataFrame, option_summary: pd.DataFrame, 
                              broken_details: pd.DataFrame):
        """
        Export summary statistics to CSV files
        """
        
        cluster_summary.to_csv('summary_by_cluster.csv', index=False)
        print("✓ Exported: summary_by_cluster.csv")
        
        option_summary.to_csv('summary_by_option.csv', index=False)
        print("✓ Exported: summary_by_option.csv")
        
        broken_details[['Store', 'Cluster', 'Option', 'Option Stk', 'Option Buffer', 'Excess_Qty', 'Sales']].to_csv(
            'broken_combinations_detailed.csv', index=False
        )
        print("✓ Exported: broken_combinations_detailed.csv")
    
    # ========================================================================
    # SECTION 2: TRANSFER PLAN GENERATION
    # ========================================================================
    
    def generate_transfer_plans(self, df: pd.DataFrame) -> List[SKUTransferPlan]:
        """
        REFINED ALGORITHM:
        
        Phase 1: Identify SKUs with Excess and Shortage
        Phase 2: Create Transfer Routes (Source → Destination pairs)
        Phase 3: Prioritize Sources and Destinations
        Phase 4: Calculate Transfer Quantities
        Phase 5: Generate Transfer Plans
        """
        
        df = self.preprocess_data()
        transfer_id_counter = 1
        
        # ============ PHASE 1: IDENTIFY EXCESS & SHORTAGE BY SKU ============
        
        """
        For EACH SKU (Option + Size), identify:
        - Stores with EXCESS: Stock > Buffer Stock (can send)
        - Stores with SHORTAGE: Stock < Buffer Stock (need to receive)
        """
        
        # Get unique SKUs
        unique_skus = df['SKU'].unique()
        
        print(f"\nProcessing {len(unique_skus)} unique SKUs")
        print(f"Total records: {len(df)}")
        print("-" * 90)
        
        transfer_count = 0
        
        # ============ PHASE 2: LOOP THROUGH EACH SKU ============
        
        for sku_idx, sku in enumerate(unique_skus, 1):
            # Get all stores that carry this SKU
            sku_data = df[df['SKU'] == sku].copy()
            
            if sku_data.empty:
                continue
            
            # ============ PHASE 2A: IDENTIFY EXCESS STORES ============
            
            """
            Excess Store = Stock > Buffer Stock
            These stores have excess inventory for this SKU
            """
            
            excess_stores = sku_data[sku_data['Stock'] > sku_data['Buffer Stock']].copy()
            
            if excess_stores.empty:
                continue  # No stores with excess for this SKU
            
            # Calculate excess quantity at each store
            excess_stores['Excess_Qty'] = excess_stores['Stock'] - excess_stores['Buffer Stock']
            excess_stores['Excess_Qty'] = excess_stores['Excess_Qty'].astype(int)
            
            # ============ PHASE 2B: IDENTIFY SHORTAGE STORES ============
            
            """
            Shortage Store = Stock < Buffer Stock
            These stores need more inventory for this SKU
            """
            
            shortage_stores = sku_data[sku_data['Stock'] < sku_data['Buffer Stock']].copy()
            
            if shortage_stores.empty:
                continue  # No stores with shortage for this SKU
            
            # Calculate shortage (how much needed) at each store
            shortage_stores['Shortage_Qty'] = shortage_stores['Buffer Stock'] - shortage_stores['Stock']
            shortage_stores['Shortage_Qty'] = shortage_stores['Shortage_Qty'].astype(int)
            
            # ============ PHASE 3: PRIORITIZE SOURCES (Lowest Sales First) ============
            
            """
            Business Logic:
            - Source stores are struggling (they have excess)
            - Prioritize struggling stores: lowest sales first
            - Within same cluster: prioritize lowest sales
            - Across clusters: still prioritize lowest sales
            
            Example:
            StoreA (North, SHIRT-M sales=5) - PRIORITY 1
            StoreB (North, SHIRT-M sales=15) - PRIORITY 2
            StoreC (East, SHIRT-M sales=8) - PRIORITY 3
            StoreD (East, SHIRT-M sales=20) - PRIORITY 4
            
            Execution order: StoreA → StoreB → StoreC → StoreD
            (Lowest sales stores transfer first)
            """
            
            # For now, sort by sales (lowest first)
            excess_stores = excess_stores.sort_values(
                'Sales', ascending=True  # LOWEST sales first (struggling stores)
            ).reset_index(drop=True)
            
            # ============ PHASE 4: PRIORITIZE DESTINATIONS (Highest Sales First) ============
            
            """
            Business Logic:
            - Destination stores are thriving (they need stock)
            - Prioritize high-demand stores: highest sales first
            - Within same cluster: prioritize highest sales
            - Across clusters: still prioritize highest sales
            
            Example:
            StoreE (North, SHIRT-M sales=25) - PRIORITY 1
            StoreF (North, SHIRT-M sales=15) - PRIORITY 2
            StoreG (East, SHIRT-M sales=30) - PRIORITY 3
            StoreH (East, SHIRT-M sales=10) - PRIORITY 4
            
            Execution order: StoreE → StoreF → StoreG → StoreH
            (Highest sales stores receive first)
            """
            
            shortage_stores = shortage_stores.sort_values(
                'Sales', ascending=False  # HIGHEST sales first (high-demand stores)
            ).reset_index(drop=True)
            
            # ============ PHASE 5: CREATE TRANSFER ROUTES ============
            
            """
            For each source-destination pair, calculate transfer quantity
            """
            
            for _, source_row in excess_stores.iterrows():
                source_store = source_row['Store']
                source_cluster = source_row['Cluster']
                source_sales = source_row['Sales']
                source_excess = int(source_row['Excess_Qty'])
                source_stock = int(source_row['Stock'])
                source_buffer = int(source_row['Buffer Stock'])
                
                if source_excess <= 0:
                    continue
                
                remaining_excess = source_excess
                
                # ============ PHASE 5A: TRY SAME CLUSTER FIRST ============
                
                # Prioritize same-cluster destinations
                same_cluster_dests = shortage_stores[
                    shortage_stores['Cluster'] == source_cluster
                ].copy()
                
                diff_cluster_dests = shortage_stores[
                    shortage_stores['Cluster'] != source_cluster
                ].copy()
                
                # Process in order: same cluster first, then different
                for destination_list, priority in [
                    (same_cluster_dests, TransferPriority.SAME_CLUSTER),
                    (diff_cluster_dests, TransferPriority.DIFFERENT_CLUSTER)
                ]:
                    
                    if destination_list.empty or remaining_excess <= 0:
                        continue
                    
                    for _, dest_row in destination_list.iterrows():
                        dest_store = dest_row['Store']
                        dest_cluster = dest_row['Cluster']
                        dest_sales = dest_row['Sales']
                        dest_shortage = int(dest_row['Shortage_Qty'])
                        dest_stock = int(dest_row['Stock'])
                        dest_buffer = int(dest_row['Buffer Stock'])
                        
                        if remaining_excess <= 0 or dest_shortage <= 0:
                            continue
                        
                        # Skip if source == destination
                        if source_store == dest_store:
                            continue
                        
                        # ============ PHASE 5B: CALCULATE TRANSFER QUANTITY ============
                        
                        """
                        CORRECT FORMULA:
                        
                        Source can provide: remaining_excess units
                        Destination needs: dest_shortage units
                        Transfer = min(remaining_excess, dest_shortage)
                        
                        This ensures:
                        - Source: final_stock = source_stock - transfer >= source_buffer
                        - Destination: final_stock = dest_stock + transfer <= dest_buffer
                        """
                        
                        transfer_qty = min(remaining_excess, dest_shortage)
                        transfer_qty = int(transfer_qty)
                        
                        if transfer_qty <= 0:
                            continue
                        
                        # ============ PHASE 5C: VALIDATE TRANSFER ============
                        
                        # Verify source remains above buffer after transfer
                        source_after = source_stock - transfer_qty
                        if source_after < source_buffer:
                            # Adjust transfer to keep source at buffer
                            transfer_qty = source_stock - source_buffer
                        
                        # Verify destination doesn't exceed buffer after transfer
                        dest_after = dest_stock + transfer_qty
                        if dest_after > dest_buffer:
                            # Adjust transfer to keep destination at buffer
                            transfer_qty = dest_buffer - dest_stock
                        
                        if transfer_qty <= 0:
                            continue
                        
                        # ============ PHASE 5D: CREATE TRANSFER PLAN ============
                        
                        plan = SKUTransferPlan(
                            transfer_id=f"TXN_{self.timestamp}_{transfer_id_counter:06d}",
                            from_store=source_store,
                            from_cluster=source_cluster,
                            from_sku_sales=source_sales,
                            to_store=dest_store,
                            to_cluster=dest_cluster,
                            to_sku_sales=dest_sales,
                            sku=sku,
                            source_stock=source_stock,
                            source_buffer=source_buffer,
                            dest_stock=dest_stock,
                            dest_buffer=dest_buffer,
                            quantity_to_transfer=transfer_qty,
                            priority=priority
                        )
                        
                        self.sku_transfer_plans.append(plan)
                        transfer_id_counter += 1
                        transfer_count += 1
                        
                        remaining_excess -= transfer_qty
            
            # Progress indicator
            if sku_idx % max(1, len(unique_skus) // 10) == 0:
                print(f"  Processed {sku_idx}/{len(unique_skus)} SKUs ({transfer_count} transfers so far)")
        
        # Sort by priority
        self.sku_transfer_plans.sort(
            key=lambda x: (x.priority.value, x.transfer_id)
        )
        
        return self.sku_transfer_plans
    
    # ========================================================================
    # SECTION 3: EXPORT & REPORTING
    # ========================================================================
    
    def export_to_csv(self, output_file: str = 'transfer_plan.csv') -> pd.DataFrame:
        """Export minimal transfer plan to CSV"""
        if not self.sku_transfer_plans:
            print("No transfer plans generated")
            return pd.DataFrame()
        
        plan_data = []
        for plan in self.sku_transfer_plans:
            plan_data.append({
                'From_Store': plan.from_store,
                'From_Cluster': plan.from_cluster,
                'From_SKU_Sales': round(plan.from_sku_sales, 2),
                'To_Store': plan.to_store,
                'To_Cluster': plan.to_cluster,
                'To_SKU_Sales': round(plan.to_sku_sales, 2),
                'SKU': plan.sku,
                'Source_Stock': plan.source_stock,
                'Source_Buffer': plan.source_buffer,
                'Dest_Stock': plan.dest_stock,
                'Dest_Buffer': plan.dest_buffer,
                'Qty': plan.quantity_to_transfer,
                'Priority': plan.priority.name
            })
        
        plan_df = pd.DataFrame(plan_data)
        plan_df.to_csv(output_file, index=False)
        
        total_units = plan_df['Qty'].sum()
        print(f"\n✓ Transfer plan exported to {output_file}")
        print(f"  Total transfers: {len(plan_df)}")
        print(f"  Total units: {int(total_units)}")
        
        return plan_df
    
    def get_transfer_plan_summary(self) -> Dict:
        """Generate summary statistics for transfer plan"""
        if not self.sku_transfer_plans:
            return {}
        
        same_cluster = len([p for p in self.sku_transfer_plans 
                           if p.priority == TransferPriority.SAME_CLUSTER])
        diff_cluster = len([p for p in self.sku_transfer_plans 
                           if p.priority == TransferPriority.DIFFERENT_CLUSTER])
        
        return {
            'Total Transfers': len(self.sku_transfer_plans),
            'Total Units': int(sum(p.quantity_to_transfer for p in self.sku_transfer_plans)),
            'Same Cluster Transfers': same_cluster,
            'Different Cluster Transfers': diff_cluster,
            'Same Cluster Units': int(sum(p.quantity_to_transfer for p in self.sku_transfer_plans 
                                          if p.priority == TransferPriority.SAME_CLUSTER)),
            'Different Cluster Units': int(sum(p.quantity_to_transfer for p in self.sku_transfer_plans 
                                               if p.priority == TransferPriority.DIFFERENT_CLUSTER)),
            'Unique SKUs': len(set(p.sku for p in self.sku_transfer_plans)),
            'Unique Source Stores': len(set(p.from_store for p in self.sku_transfer_plans)),
            'Unique Dest Stores': len(set(p.to_store for p in self.sku_transfer_plans))
        }
    
    # adding get_transfer_dataframe method to convert transfer plans to DataFrame for easier reporting and integration with Streamlit.
    def get_transfer_dataframe(self) -> pd.DataFrame:
        """
        Return transfer plan as DataFrame
        (Same structure as export_to_csv)
        """
        if not self.sku_transfer_plans:
            return pd.DataFrame()

        plan_data = []
        for plan in self.sku_transfer_plans:
            plan_data.append({
                'From_Store': plan.from_store,
                'From_Cluster': plan.from_cluster,
                'From_SKU_Sales': round(plan.from_sku_sales, 2),
                'To_Store': plan.to_store,
                'To_Cluster': plan.to_cluster,
                'To_SKU_Sales': round(plan.to_sku_sales, 2),
                'SKU': plan.sku,
                'Source_Stock': plan.source_stock,
                'Source_Buffer': plan.source_buffer,
                'Dest_Stock': plan.dest_stock,
                'Dest_Buffer': plan.dest_buffer,
                'Qty': plan.quantity_to_transfer,
                'Priority': plan.priority.name
            })

        return pd.DataFrame(plan_data)    
    # addding run_dashboard_mode method to run in Streamlit mode implemented separatley to avoid any issues with Streamlit's execution model and to keep the main logic clean and testable.
    '''def run_dashboard_mode(self):
        summary, cluster_summary, option_summary, broken_details = self.get_option_store_health_summary(self.df)
        self.sku_transfer_plans = []
        plans = self.generate_transfer_plans(self.df)

        transfer_df = pd.DataFrame([{
            'From Store': p.from_store,
            'From Cluster': p.from_cluster,
            'To Store': p.to_store,
            'To Cluster': p.to_cluster,
            'SKU': p.sku,
            'Qty': p.quantity_to_transfer,
            'Priority': p.priority.name
        } for p in plans])

        transfer_summary = self.get_transfer_plan_summary()

        return {
            "summary": summary,
            "cluster_summary": cluster_summary,
            "option_summary": option_summary,
            "broken_details": broken_details,
            "transfer_df": transfer_df,
            "transfer_summary": transfer_summary
        }
    '''
    def run_dashboard_mode(self):
        summary, cluster_summary, option_summary, broken_details = self.get_option_store_health_summary(self.df)

        self.sku_transfer_plans = []
        self.generate_transfer_plans(self.df)

        transfer_df = self.get_transfer_dataframe()
        transfer_summary = self.get_transfer_plan_summary()

        return {
            "summary": summary,
            "cluster_summary": cluster_summary,
            "option_summary": option_summary,
            "broken_details": broken_details,
            "transfer_df": transfer_df,
            "transfer_summary": transfer_summary
        }

# ============================================================================
# MAIN EXECUTION
# ============================================================================

def main():
    import time
    
    print("\n" + "="*90)
    print("SKU-LEVEL TRANSFER PLAN OPTIMIZER")
    print("="*90)
    
    start_time = time.time()
    
    # Load data
    print("\n📂 Loading data...")
    df = pd.read_excel(r'E:\JobApplications-General\CitiStyle-SamirSir\refinedWorking_v2\InputSheetFormat.xlsx')
    print(f"✓ Loaded {len(df)} SKU records")
    
    # Initialize optimizer
    optimizer = SKULevelTransferOptimizer(df)
    
    # ========== STEP 1: GENERATE SUMMARY STATISTICS ==========
    
    print("\n" + "="*90)
    print("STEP 1: ANALYZING CURRENT INVENTORY HEALTH")
    print("="*90)
    
    summary, cluster_summary, option_summary, broken_details = optimizer.get_option_store_health_summary(df)
    
    # Print summary
    optimizer.print_option_store_health_summary(summary, cluster_summary, option_summary, broken_details)
    
    # Export summary
    print("\n\n📁 Exporting summary statistics...")
    print("-" * 90)
    optimizer.export_summary_to_csv(cluster_summary, option_summary, broken_details)
    
    # ========== STEP 2: GENERATE TRANSFER PLANS ==========
    
    print("\n\n" + "="*90)
    print("STEP 2: GENERATING TRANSFER PLANS")
    print("="*90)
    
    plans = optimizer.generate_transfer_plans(df)
    
    elapsed_transfer = time.time() - start_time
    print(f"\n✅ Generated {len(plans)} transfer lines in {elapsed_transfer:.2f} seconds")
    
    # ========== STEP 3: EXPORT TRANSFER PLAN ==========
    
    print("\n\n" + "="*90)
    print("STEP 3: EXPORTING TRANSFER PLAN")
    print("="*90)
    
    plan_df = optimizer.export_to_csv('transfer_plan.csv')
    
    # ========== STEP 4: TRANSFER PLAN SUMMARY ==========
    
    print("\n\n" + "="*90)
    print("TRANSFER PLAN SUMMARY")
    print("="*90)
    
    transfer_summary = optimizer.get_transfer_plan_summary()
    for key, value in transfer_summary.items():
        print(f"{key}: {value}")
    
    # ========== STEP 5: SAMPLE TRANSFERS ==========
    
    print("\n\n" + "="*90)
    print("SAMPLE TRANSFERS (First 15)")
    print("="*90)
    
    for i, plan in enumerate(plans[:15], 1):
        priority_label = "🟢 SAME" if plan.priority == TransferPriority.SAME_CLUSTER else "🔴 DIFF"
        print(f"{i:2d}. {plan.from_store}({plan.from_cluster},sales={plan.from_sku_sales:6.2f}) " +
              f"→ {plan.to_store}({plan.to_cluster},sales={plan.to_sku_sales:6.2f}) | " +
              f"SKU: {plan.sku:<15} | Qty: {plan.quantity_to_transfer:3d} | {priority_label}")
    
    if len(plans) > 15:
        print(f"\n... and {len(plans) - 15} more transfers")
    
    # ========== FINAL SUMMARY ==========
    
    total_time = time.time() - start_time
    print("\n\n" + "="*90)
    print("✅ PROCESS COMPLETE")
    print("="*90)
    print(f"\nTotal execution time: {total_time:.2f} seconds")
    print("\nGenerated files:")
    print("  1. summary_by_cluster.csv - Health breakdown by cluster")
    print("  2. summary_by_option.csv - Health breakdown by option")
    print("  3. broken_combinations_detailed.csv - Detailed broken options")
    print("  4. transfer_plan.csv - Warehouse-ready transfer plan")
    print("\n" + "="*90 + "\n")


if __name__ == "__main__":
    main()