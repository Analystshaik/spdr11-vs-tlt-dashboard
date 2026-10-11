import json
from pathlib import Path
from analysis_common import coverage_report

cfg = json.loads(Path("config.json").read_text())
symbols = ["TLT"] + cfg["symbols"]
df = coverage_report(cfg["database"], cfg["source_table"], symbols)
print(df.to_string(index=False))

missing = df[df["rows"] == 0]["symbol"].tolist()
if missing:
    print("\nMissing:", ", ".join(missing))
    print("Run: python ibkr_backfill.py")
else:
    print("\nAll required symbols are present.")
