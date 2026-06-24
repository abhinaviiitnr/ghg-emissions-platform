"""One-off: create all tables in an empty database. Safe to re-run."""
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from api.database import engine, Base
from api import models  # noqa: F401  -- importing registers the tables on Base

Base.metadata.create_all(bind=engine)
print("Tables created:")
for table_name in Base.metadata.tables:
    print(f"  - {table_name}")