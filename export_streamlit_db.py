import sqlite3
from pathlib import Path

SOURCE_DB=r"C:\Keystone\ibkr_production_data_engine_v2\data\ibkr_market_data.sqlite"
TARGET_DB=Path("data")/"streamlit_data.sqlite"
TABLES=[
    "spdr11_tlt_relationship_day",
    "spdr11_tlt_relationship_day_snapshot",
    "spdr11_tlt_relationship_week",
    "spdr11_tlt_relationship_week_snapshot",
    "spdr11_tlt_relationship_month",
    "spdr11_tlt_relationship_month_snapshot",
]

def copy_table(src,dst,table):
    schema=src.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name=?",(table,)).fetchone()
    if not schema or not schema[0]:
        print("SKIP",table)
        return
    dst.execute(f'DROP TABLE IF EXISTS "{table}"')
    dst.execute(schema[0])
    rows=src.execute(f'SELECT * FROM "{table}"').fetchall()
    if rows:
        ph=",".join("?" for _ in rows[0])
        dst.executemany(f'INSERT INTO "{table}" VALUES ({ph})',rows)
    print("COPIED",table,len(rows))

def main():
    TARGET_DB.parent.mkdir(exist_ok=True)
    if TARGET_DB.exists(): TARGET_DB.unlink()
    src=sqlite3.connect(SOURCE_DB); dst=sqlite3.connect(TARGET_DB)
    try:
        for t in TABLES: copy_table(src,dst,t)
        dst.commit(); dst.execute("VACUUM"); dst.commit()
    finally:
        src.close(); dst.close()
    print("Created",TARGET_DB.resolve())

if __name__=="__main__":
    main()
