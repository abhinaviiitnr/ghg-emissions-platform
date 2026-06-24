from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from pathlib import Path

# DB file lives at C:\Project2\data\emissions.db
DB_PATH = Path(__file__).resolve().parent.parent / "data" / "emissions.db"
DB_URL = f"sqlite:///{DB_PATH}"

# check_same_thread=False is the standard SQLite+FastAPI setting:
# it lets the connection be used across FastAPI's threadpool requests.
engine = create_engine(DB_URL, connect_args={"check_same_thread": False})

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class all our table models inherit from.
Base = declarative_base()


def get_db():
    """FastAPI dependency: yields a session, always closes it."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()