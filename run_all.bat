@echo off
cd /d %~dp0
python check_data.py
python analyze_all.py
streamlit run dashboard.py
