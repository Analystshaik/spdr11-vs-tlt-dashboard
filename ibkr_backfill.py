import json
import sqlite3
import threading
import time
from pathlib import Path
from queue import Queue, Empty

from ibapi.client import EClient
from ibapi.wrapper import EWrapper
from ibapi.contract import Contract

INFO_CODES = {2104,2106,2107,2108,2158}

class IBApp(EWrapper, EClient):
    def __init__(self):
        EClient.__init__(self, self)
        self.ready = threading.Event()
        self.next_id = None
        self.queues = {}
        self.errors = {}

    def nextValidId(self, orderId):
        self.next_id = orderId
        self.ready.set()

    def error(self, reqId, errorCode, errorString, *args):
        if errorCode in INFO_CODES:
            return
        if reqId in self.queues:
            self.errors[reqId] = f"{errorCode}: {errorString}"
            self.queues[reqId].put(("ERR", None))

    def historicalData(self, reqId, bar):
        if reqId in self.queues:
            self.queues[reqId].put(("BAR", bar))

    def historicalDataEnd(self, reqId, start, end):
        if reqId in self.queues:
            self.queues[reqId].put(("END", None))

    def start_api(self, host, port, client_id):
        self.connect(host, int(port), int(client_id))
        threading.Thread(target=self.run, daemon=True).start()
        if not self.ready.wait(10):
            raise RuntimeError("Could not connect to TWS/IB Gateway.")

    def contract(self, symbol):
        c = Contract()
        c.symbol = symbol
        c.secType = "STK"
        c.exchange = "SMART"
        c.currency = "USD"
        return c

    def get_daily(self, symbol, years=5, timeout=90):
        req_id = self.next_id
        self.next_id += 1
        q = Queue()
        self.queues[req_id] = q

        self.reqHistoricalData(
            req_id, self.contract(symbol), "", f"{int(years)} Y",
            "1 day", "ADJUSTED_LAST", 1, 1, False, []
        )

        rows = []
        started = time.time()
        try:
            while True:
                if time.time() - started > timeout:
                    self.cancelHistoricalData(req_id)
                    raise RuntimeError("timeout")
                try:
                    kind, obj = q.get(timeout=5)
                except Empty:
                    continue
                if kind == "ERR":
                    raise RuntimeError(self.errors.get(req_id, "IBKR error"))
                if kind == "END":
                    break
                b = obj
                d = str(b.date).replace("-", "")[:8]
                rows.append((symbol, d, float(b.open), float(b.high), float(b.low), float(b.close), float(b.volume or 0)))
        finally:
            self.queues.pop(req_id, None)
        return rows

def upsert(db_path, table, rows):
    if not rows:
        return 0

    con = sqlite3.connect(db_path)
    try:
        cols = [r[1] for r in con.execute(f'PRAGMA table_info("{table}")').fetchall()]
        if not cols:
            con.execute(
                f'CREATE TABLE "{table}" ('
                'symbol TEXT NOT NULL, bar_date TEXT NOT NULL, '
                'open REAL, high REAL, low REAL, close REAL, volume REAL, '
                'PRIMARY KEY(symbol, bar_date))'
            )
            cols = [r[1] for r in con.execute(f'PRAGMA table_info("{table}")').fetchall()]

        base = ["symbol","bar_date","open","high","low","close","volume"]
        use = [c for c in base if c in cols]
        pos = {c:i for i,c in enumerate(base)}

        for row in rows:
            vals = tuple(row[pos[c]] for c in use)
            symbol = row[0]
            bar_date = row[1]
            con.execute(f'DELETE FROM "{table}" WHERE symbol=? AND bar_date=?', (symbol, bar_date))
            col_sql = ",".join(f'"{c}"' for c in use)
            ph = ",".join("?" for _ in use)
            con.execute(f'INSERT INTO "{table}" ({col_sql}) VALUES ({ph})', vals)

        con.commit()
        return len(rows)
    finally:
        con.close()

cfg = json.loads(Path("config.json").read_text())
symbols = ["TLT"] + cfg["symbols"]

app = IBApp()
app.start_api(
    cfg.get("ibkr_host", "127.0.0.1"),
    cfg.get("ibkr_port", 7497),
    cfg.get("ibkr_client_id", 66)
)

try:
    for i, symbol in enumerate(symbols, start=1):
        try:
            rows = app.get_daily(symbol, cfg.get("ibkr_history_years", 5))
            saved = upsert(cfg["database"], cfg["source_table"], rows)
            print(f"[{i}/{len(symbols)}] {symbol}: {saved:,} rows saved")
        except Exception as e:
            print(f"[{i}/{len(symbols)}] {symbol}: FAILED - {e}")
finally:
    app.disconnect()

print("\nBackfill finished. Next run: python check_data.py")
