# to run the app:
# streamlit run budget_app_v3.py

# developments related to v3
# 1) web deployment
# 2) properly synch position list occupancy and budget editing


import streamlit as st
import pandas as pd
import numpy as np
import locale
#locale.setlocale(locale.LC_ALL, "en_US.UTF-8")
st.set_page_config(layout="wide")

position_list_columns = ["team", "position_grade", "incumbent", "incumbent_grade", "occupancy_status", "start_month", "end_month", "months_filled", "months_vacant", "monthly_rate_filled", "monthly_rate_vacant", "post_saving", "lapsed_cost"]
budget_columns = ["team", "post_saving", "corporate_technical_activities", "income_plan", "lapsed_cost", "nshr_cost", "subscriptions", "team_allocation", "working_capital"]

def upload_file(table_name, required_columns):
    file = st.file_uploader(
        f"Select the file with the {table_name}. Make sure it includes the columns: {', '.join(required_columns)}",
        type=["csv", "xls", "xlsx"] )

    if file is None:
        st.warning("Please upload a file to proceed.")
        return None

    if file.name.endswith('.csv'):
        df = pd.read_csv(file)
    else:
        df = pd.read_excel(file)

    missing_cols = [col for col in required_columns if col not in df.columns]
    if missing_cols:
        st.error(f"Missing required columns: {', '.join(missing_cols)}")
        # Reset session state
        for key in st.session_state.keys():
            del st.session_state[key]
        st.rerun()
        return None
    return df



# Data Upload
col1, col2, col3 = st.columns([1, 2, 1])
with col2:
    tab1, tab2 = st.tabs(["New Exercise", "Resume"])

    with tab1:
        df = upload_file ("Positions List", ["team", "incumbent", "position_grade", "incumbent_grade"])
        df_standard_rates = upload_file ("Standard Rates", ["grade", "monthly_rate_filled", "monthly_rate_vacant"])

        if (df is not None) and (df_standard_rates is not None):
            # adding standard cost to the poistion table
            df = df.merge(df_standard_rates[["grade", "monthly_rate_filled"]], left_on = "incumbent_grade", right_on = "grade").drop(columns=["grade"])
            df = df.merge(df_standard_rates[["grade", "monthly_rate_vacant"]], left_on = "position_grade", right_on = "grade").drop(columns=["grade"])
            # calculated fields to start operations
            df["start_month"], df["end_month"] = 1, 12
            df['occupancy_status'] = df['incumbent'].apply(
                lambda x: "Vacant" if str(x).upper().startswith("EX") 
                else "Filled")
            df['months_filled'] = np.where(df['occupancy_status'] == 'Filled', 12, 0)
            df['months_vacant'] = np.where(df['occupancy_status'] == 'Filled', 0, 12)
            df["post_saving"] = df.months_vacant * df.monthly_rate_vacant
            df["lapsed_cost"] = df.months_filled * (df.monthly_rate_filled - df.monthly_rate_vacant) # lapsed cost includes also different grade encumbrance
            df = df[position_list_columns]

            df_budget = df.groupby('team', as_index=False).agg({
                'post_saving': 'sum',
                'lapsed_cost': 'sum'
                })
            df_budget["income_plan"], df_budget["corporate_technical_activities"], df_budget["nshr_cost"], df_budget["subscriptions"], df_budget["team_allocation"] = 0,0,0,0,0
            df_budget["working_capital"] = df_budget["post_saving"] + df_budget["corporate_technical_activities"] + df_budget["income_plan"] + df_budget["team_allocation"] - df_budget["lapsed_cost"] - df_budget["nshr_cost"] - df_budget["subscriptions"]
            df_budget = df_budget[budget_columns]

            if "df_budget" not in st.session_state:
                st.session_state["df"] = df.copy()
                st.session_state["df_budget"] = df_budget.copy()

            
    with tab2: # need to use differnt variables to avoid ovrewriting df
        df_resume = upload_file ("Positions List", position_list_columns)
        df_budget_resume = upload_file ("Budget by Team", budget_columns)
        
        if (df_resume is not None) and (df_budget_resume is not None):
            df = df_resume[position_list_columns]
            df_budget = df_budget_resume[budget_columns]

            if "df_budget" not in st.session_state:
                st.session_state["df"] = df.copy()
                st.session_state["df_budget"] = df_budget.copy()

# Data Management
# "df_budget" in st.session_state works as a flag of occurred upload
if "df_budget" in st.session_state:
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2: 
        st.title("EST Budget app")
        st.write("### Position occupancy by team")

        df = st.session_state["df"]
        df_budget = st.session_state["df_budget"]
        
        for team in sorted(df['team'].unique()):
            with st.expander(f"## ***Team {team}***"):
                df_team = df[df['team'] == team].reset_index(drop=True)

                for idx, row in df_team.iterrows():
                    # Two columns: label and controls
                    sub_col1, sub_col2 = st.columns([1, 1])

                    with sub_col1:
                        st.markdown(f"**{row['position_grade']}: {row['incumbent']}**")
                    with sub_col2:
                        row['occupancy_status'] = st.radio(
                            "Occupancy",
                            ["Filled", "Partial", "Vacant"],
                            index=["Filled", "Partial", "Vacant"].index(row['occupancy_status']),
                            key=f"{team}_{idx}_occupancy",
                            horizontal=True,
                            label_visibility="collapsed"
                        )

                    # Handle months and occupancy percentage
                    # months_filled and months_vacant variables are used to trigger changes in the occupancy status
                    # if they are different from row['months_filled'] and row['months_vacant'] we trigger a rerun()
                    if row['occupancy_status'] == "Filled":
                        row['start_month'], row['end_month'], months_filled, months_vacant = None, None, 12, 0
                    elif row['occupancy_status'] == "Vacant":
                        row['start_month'], row['end_month'], months_filled, months_vacant = None, None, 0, 12
                    else:  # Partial
                        row['start_month'], row['end_month'] = st.slider(
                            "Active Months",
                            min_value=1,
                            max_value=12,
                            value=(
                                int(1 if pd.isna(row['start_month']) else row['start_month']),
                                int(12 if pd.isna(row['end_month']) else row['end_month'])),
                            step=1,
                            key=f"{team}_{idx}_months")
                        row['months_filled'] = row['end_month'] - row['start_month'] + 1
                        row['months_vacant'] = 12 - row['end_month'] + row['start_month'] -1

                    # Align df and df_budget with the changes if there was a change
                    mask = (df_budget['team'] == team)
                    post_saving_variation = row['months_vacant'] * row['monthly_rate_vacant'] - row['post_saving']
                    lapsed_cost_variation = row['months_filled'] * (row['monthly_rate_filled'] - row['monthly_rate_vacant']) - row['lapsed_cost']
                    df_budget.loc[mask, 'working_capital'] += post_saving_variation - lapsed_cost_variation
                    df_budget.loc[mask, 'post_saving'] += post_saving_variation
                    df_budget.loc[mask, 'lapsed_cost'] += lapsed_cost_variation

                    mask = (
                        (df['team'] == team) &
                        (df['position_grade'] == row['position_grade']) &
                        (df['incumbent'] == row['incumbent'])
                        )
                    df.loc[mask, 'occupancy_status'] = row['occupancy_status']
                    df.loc[mask, 'start_month'] = row['start_month']
                    df.loc[mask, 'end_month'] = end = row['end_month']
                    df.loc[mask, 'months_filled'] = row['months_filled']
                    df.loc[mask, 'months_vacant'] = row['months_vacant']
                    df.loc[mask, 'post_saving'] = row['months_vacant'] * row['monthly_rate_vacant']
                    df.loc[mask, 'lapsed_cost'] = row['months_filled'] * (row['monthly_rate_filled'] - row['monthly_rate_vacant'])

    # Show updated table
    st.write("### Position listing")
    df = st.data_editor(
        df,
        key="position_listing",
        column_config={
            "team": st.column_config.TextColumn("Team", disabled=True),
            "position_grade": st.column_config.TextColumn("Position Grade", disabled=True),
            "incumbent": st.column_config.TextColumn("Incumbent", disabled=True),
            "incumbent_grade": st.column_config.TextColumn("Incumbent Grade", disabled=True),
            "occupancy_status": st.column_config.TextColumn("Occupancy Status", disabled=True),
            "start_month": st.column_config.NumberColumn("Start Month", format="%d", disabled=True),
            "end_month": st.column_config.NumberColumn("End Month", format="%d", disabled=True),
            "months_filled": st.column_config.NumberColumn("Filled Months", format="%d", disabled=True),
            "months_vacant": st.column_config.NumberColumn("Vacant Months", format="%d", disabled=True),
            "monthly_rate_filled": st.column_config.NumberColumn("Filled Standard Rate", format="localized", disabled=True),
            "monthly_rate_vacant": st.column_config.NumberColumn("Vacant Standard Rate", format="localized", disabled=True),
            "post_saving": st.column_config.NumberColumn("Post Saving", format="localized", disabled=True),
            "lapsed_cost": st.column_config.NumberColumn("Lapsed Cost", format="localized", disabled=True),
        })

    col4, col5, col6 = st.columns([1, 5, 1])
    with col5:
        st.write("### Summary by Team")
        
        def recalc_working_capital():
            d = st.session_state['df_budget']
            for index, row in st.session_state['budget_editor']['edited_rows'].items():
                for col, value in row.items():
                    d.at[index, col] = value # updating summary_df with summary_editor
            d["working_capital"] = d["post_saving"] + d["corporate_technical_activities"] + d["income_plan"] + d["team_allocation"] - d["lapsed_cost"] - d["nshr_cost"] - d["subscriptions"]

        # Editable table
        df_budget = st.data_editor(
            df_budget,
            key="budget_editor",
            on_change=recalc_working_capital,
            column_config={
                "team": st.column_config.TextColumn("Team", disabled=True),
                "post_saving": st.column_config.NumberColumn("Post Saving", format="localized", disabled=True),
                "income_plan": st.column_config.NumberColumn("Income Plan", format="localized"),
                "corporate_technical_activities": st.column_config.NumberColumn("Corporate Technical Activities", format="localized"),
                "lapsed_cost": st.column_config.NumberColumn("Lapsed Cost", format="localized", disabled=True),
                "nshr_cost": st.column_config.NumberColumn("NSHR Cost", format="localized"),
                "subscriptions": st.column_config.NumberColumn("Subscriptions", format="localized"),
                "team_allocation": st.column_config.NumberColumn("Team Allocation", format="localized"),
                "working_capital": st.column_config.NumberColumn("Working Capital", format="localized", disabled=True)},
            )
