from __future__ import annotations
import sqlite3
import numpy as np
import pandas as pd

def normalize_dates(series):
    x = series.astype(str).str.strip()
    mask = x.str.fullmatch(r"\d{8}", na=False)
    x = x.where(~mask, x.str.slice(0,4) + "-" + x.str.slice(4,6) + "-" + x.str.slice(6,8))
    return pd.to_datetime(x, errors="coerce")

def coverage_report(db_path, table, symbols):
    con = sqlite3.connect(db_path)
    rows = []
    try:
        for sym in symbols:
            count, mind, maxd = con.execute(
                f'SELECT COUNT(*), MIN(bar_date), MAX(bar_date) FROM "{table}" WHERE symbol=?',
                (sym,)
            ).fetchone()
            rows.append({"symbol": sym, "rows": int(count or 0), "min_date": mind, "max_date": maxd})
    finally:
        con.close()
    return pd.DataFrame(rows)

def load_daily(db_path, table, symbols):
    all_syms = ["TLT"] + list(symbols)
    ph = ",".join("?" for _ in all_syms)
    con = sqlite3.connect(db_path)
    try:
        df = pd.read_sql_query(
            f'SELECT symbol, bar_date, open, high, low, close FROM "{table}" '
            f'WHERE symbol IN ({ph}) ORDER BY symbol, bar_date',
            con,
            params=all_syms
        )
    finally:
        con.close()

    if df.empty:
        raise RuntimeError(f"No TLT/SPDR rows found in {table}.")

    df["bar_date"] = normalize_dates(df["bar_date"])
    for c in ["open","high","low","close"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df.dropna(subset=["bar_date","close"])
    df = df.sort_values(["symbol","bar_date"]).drop_duplicates(["symbol","bar_date"], keep="last")
    return df

def resample_close(df, rule):
    frames = []
    for sym, g in df.groupby("symbol"):
        s = g.set_index("bar_date")["close"].sort_index().resample(rule).last().dropna()
        if not s.empty:
            frames.append(pd.DataFrame({"date": s.index, "symbol": sym, "close": s.values}))
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True).pivot(index="date", columns="symbol", values="close").sort_index()

def safe_corr(a, b, min_n):
    d = pd.concat([a,b], axis=1).dropna()
    if len(d) < min_n or d.iloc[:,0].std() == 0 or d.iloc[:,1].std() == 0:
        return np.nan
    return float(d.iloc[:,0].corr(d.iloc[:,1]))

def rel_row(ticker, rets, asof, windows, lags, minhist):
    if ticker not in rets.columns or "TLT" not in rets.columns:
        return None

    hist = rets.loc[:asof, [ticker, "TLT"]].dropna()
    if len(hist) < minhist:
        return None

    out = {"ticker": ticker, "asof_date": pd.Timestamp(asof).strftime("%Y-%m-%d")}

    for w in windows:
        need = max(6, min(int(w), max(6, minhist // 2)))
        out[f"corr_{w}"] = safe_corr(hist[ticker].tail(w), hist["TLT"].tail(w), need)

    lag_corr = {}
    lag_beta = {}
    for lag in lags:
        d = pd.concat([hist[ticker], hist["TLT"].shift(lag)], axis=1).dropna().tail(max(windows))
        need = min(minhist, max(10, int(max(windows) * 0.6)))
        if len(d) < need:
            continue
        corr = safe_corr(d.iloc[:,0], d.iloc[:,1], need)
        if not np.isfinite(corr):
            continue
        var = d.iloc[:,1].var(ddof=1)
        beta = np.nan if not np.isfinite(var) or var == 0 else float(d.iloc[:,0].cov(d.iloc[:,1]) / var)
        lag_corr[int(lag)] = corr
        lag_beta[int(lag)] = beta

    if not lag_corr:
        return None

    best_lag = max(lag_corr, key=lambda k: abs(lag_corr[k]))
    best_corr = lag_corr[best_lag]

    out.update({
        "best_lag": best_lag,
        "best_lag_corr": best_corr,
        "best_lag_beta": None if not np.isfinite(lag_beta[best_lag]) else lag_beta[best_lag],
        "relationship_type": "POSITIVE_TLT" if best_corr > 0 else "INVERSE_TLT",
        "relationship_score": 100.0 * best_corr,
        "follower_alert": 1 if best_lag >= 1 and abs(best_corr) >= 0.40 else 0
    })
    return out

def write_tables(db_path, hist_table, snap_table, rows):
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    con = sqlite3.connect(db_path)
    try:
        df.to_sql(hist_table, con, if_exists="replace", index=False)
        latest = df[df["asof_date"] == df["asof_date"].max()].copy()
        latest.to_sql(snap_table, con, if_exists="replace", index=False)
    finally:
        con.close()
    return df
