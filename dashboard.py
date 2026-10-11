import json, sqlite3
from pathlib import Path
import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(page_title="11 SPDR Sectors vs TLT",layout="wide")
cfg=json.loads(Path("config.json").read_text())
DB=cfg["database"]

TABLES={
    "Daily":"spdr11_tlt_relationship_day_snapshot",
    "Weekly":"spdr11_tlt_relationship_week_snapshot",
    "Monthly":"spdr11_tlt_relationship_month_snapshot",
}

def read_table(name):
    con=sqlite3.connect(DB)
    try:
        return pd.read_sql_query(f"SELECT * FROM {name}",con)
    finally:
        con.close()

st.title("11 SPDR Sector ETFs vs TLT")
st.caption("TLT relationship and lead/lag analysis across Daily, Weekly and Monthly timeframes.")

tabs=st.tabs(["Daily","Weekly","Monthly","Cross-Timeframe Followers"])

for tab,(label,table) in zip(tabs[:3],TABLES.items()):
    with tab:
        try:
            df=read_table(table)
        except Exception as e:
            st.error(f"Could not load {table}: {e}")
            continue
        if df.empty:
            st.info("No data.")
            continue

        left,right=st.columns(2)
        concurrent=df[df["best_lag"]==0].copy()
        followers=df[df["best_lag"]>=1].copy()

        with left:
            st.subheader("Concurrent Relationships")
            if concurrent.empty:
                st.info("None on latest snapshot.")
            else:
                concurrent["strength"]=concurrent["best_lag_corr"].abs()
                st.dataframe(
                    concurrent.sort_values("strength",ascending=False)[
                        ["ticker","relationship_type","relationship_score","best_lag","best_lag_corr","best_lag_beta"]
                    ],
                    use_container_width=True,hide_index=True
                )

        with right:
            st.subheader("True Followers")
            if followers.empty:
                st.info("None on latest snapshot.")
            else:
                followers["strength"]=followers["best_lag_corr"].abs()
                st.dataframe(
                    followers.sort_values("strength",ascending=False)[
                        ["ticker","relationship_type","relationship_score","best_lag","best_lag_corr","best_lag_beta","follower_alert"]
                    ],
                    use_container_width=True,hide_index=True
                )

        chart_df=df.copy()
        chart_df["abs_score"]=chart_df["relationship_score"].abs()
        fig=px.bar(
            chart_df.sort_values("abs_score"),
            x="relationship_score",y="ticker",orientation="h",
            title=f"{label} TLT Relationship Score"
        )
        st.plotly_chart(fig,use_container_width=True)

with tabs[3]:
    frames=[]
    for label,table in TABLES.items():
        try:
            d=read_table(table)
        except Exception:
            continue
        if d.empty: continue
        d=d[d["best_lag"]>=1].copy()
        if d.empty: continue
        d["timeframe"]=label
        d["strength"]=d["best_lag_corr"].abs()
        frames.append(d[["ticker","timeframe","relationship_type","best_lag","best_lag_corr","strength"]])

    if not frames:
        st.info("No cross-timeframe followers.")
    else:
        allf=pd.concat(frames,ignore_index=True)
        summary=(allf.groupby("ticker")
                 .agg(timeframes_following=("timeframe","nunique"),
                      combined_strength=("strength","mean"))
                 .reset_index()
                 .sort_values(["timeframes_following","combined_strength"],ascending=[False,False]))
        st.subheader("Cross-Timeframe Followers")
        st.dataframe(summary,use_container_width=True,hide_index=True)
        st.subheader("Follower Details")
        st.dataframe(allf.sort_values(["ticker","timeframe"]),use_container_width=True,hide_index=True)
