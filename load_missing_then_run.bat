@echo off
cd /d %~dp0
python ibkr_backfill.py
python check_data.py
python analyze_all.py
streamlit run dashboard.py
