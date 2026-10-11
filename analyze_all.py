import json
from pathlib import Path
import pandas as pd
from analysis_common import coverage_report, load_daily, resample_close, rel_row, write_tables

cfg = json.loads(Path("config.json").read_text())
symbols = cfg["symbols"]

print("\n=== PRE-FLIGHT DATA COVERAGE ===")
cov = coverage_report(cfg["database"], cfg["source_table"], ["TLT"] + symbols)
print(cov.to_string(index=False))

loaded = set(cov.loc[cov["rows"] > 0, "symbol"])
usable = [s for s in symbols if s in loaded]

if "TLT" not in loaded:
    raise RuntimeError("TLT is missing. Run: python ibkr_backfill.py")

if not usable:
    raise RuntimeError("No SPDR sector ETFs are loaded. Run: python ibkr_backfill.py")

missing = [s for s in symbols if s not in loaded]
if missing:
    print("\nMissing sector ETFs:", ", ".join(missing))
    print("Continuing with loaded symbols only.\n")

df = load_daily(cfg["database"], cfg["source_table"], usable)

def run_tf(label, piv, windows, lags, minhist, hist_table, snap_table):
    if piv.empty or "TLT" not in piv.columns:
        print(f"{label}: insufficient data")
        return pd.DataFrame()

    rets = piv.pct_change()
    rows = []
    counts = {s: 0 for s in usable}

    for dt in rets.index:
        for ticker in usable:
            row = rel_row(ticker, rets, dt, windows, lags, minhist)
            if row:
                rows.append(row)
                counts[ticker] += 1

    result = write_tables(cfg["database"], hist_table, snap_table, rows)
    print(f"\n{label}: {len(result):,} rows generated")
    for ticker, n in counts.items():
        print(f"  {ticker}: {n:,}")
    return result

def run_daily():
    piv = df.pivot(index="bar_date", columns="symbol", values="close").sort_index()
    return run_tf(
        "Daily", piv,
        cfg.get("daily_correlation_windows", [20,60,120]),
        cfg.get("daily_lags", list(range(7))),
        cfg.get("min_history_days", 60),
        "spdr11_tlt_relationship_day",
        "spdr11_tlt_relationship_day_snapshot"
    )

def run_weekly():
    piv = resample_close(df, "W-FRI")
    return run_tf(
        "Weekly", piv,
        cfg.get("weekly_correlation_windows", [13,26,52]),
        cfg.get("weekly_lags", list(range(7))),
        cfg.get("min_history_weeks", 30),
        "spdr11_tlt_relationship_week",
        "spdr11_tlt_relationship_week_snapshot"
    )

def run_monthly():
    try:
        piv = resample_close(df, "ME")
    except ValueError:
        piv = resample_close(df, "M")
    return run_tf(
        "Monthly", piv,
        cfg.get("monthly_correlation_windows", [6,12,24]),
        cfg.get("monthly_lags", list(range(7))),
        cfg.get("min_history_months", 18),
        "spdr11_tlt_relationship_month",
        "spdr11_tlt_relationship_month_snapshot"
    )

if __name__ == "__main__":
    d = run_daily()
    w = run_weekly()
    m = run_monthly()

    if d.empty and w.empty and m.empty:
        raise RuntimeError(
            "No relationship rows were generated on any timeframe. "
            "Run python check_data.py and then python ibkr_backfill.py if needed."
        )
    print("\nAnalysis complete.")
