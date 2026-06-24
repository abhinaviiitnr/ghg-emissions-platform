import sqlite3
from pathlib import Path

db = Path(__file__).resolve().parent.parent / "data" / "emissions.db"
con = sqlite3.connect(db)
tables = [r[0] for r in con.execute(
    "SELECT name FROM sqlite_master WHERE type='table'"
)]
print("Tables in DB:", tables)
con.close()