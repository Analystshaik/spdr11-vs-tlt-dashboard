# 11 SPDR Sector ETFs vs TLT v1.1

Fixes the error:
`RuntimeError: No relationship rows were generated.`

## Step 1
Run:

```bat
python check_data.py
```

You should see coverage for:
TLT, XLC, XLY, XLP, XLE, XLF, XLV, XLI, XLB, XLRE, XLK, XLU

## Step 2
If any are missing, start TWS / IB Gateway and run:

```bat
python ibkr_backfill.py
```

Defaults:
- 127.0.0.1
- paper port 7497
- client ID 66
- 5 years
- ADJUSTED_LAST
- daily bars
- RTH only

## Step 3
Then:

```bat
python analyze_all.py
streamlit run dashboard.py
```

Or double-click:
`load_missing_then_run.bat`

The analyzer now prints coverage and rows generated per ETF.
