import re
import logging
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from .config import DATABASE_URL

logger = logging.getLogger(__name__)

def create_resilient_engine(url: str):
    if not url or "sqlite" in url:
        return create_engine(
            url or "sqlite:///./maintenance.db",
            connect_args={"check_same_thread": False},
            echo=False
        )
    
    # List candidate driver schemes for PostgreSQL
    candidate_urls = [url]
    if "postgresql" in url or "postgres" in url:
        for prefix in ["postgresql+psycopg://", "postgresql+psycopg2://", "postgresql://"]:
            alt = re.sub(r"^(?:postgresql|postgres)(?:\+[a-zA-Z0-9_-]+)?://", prefix, url)
            if alt not in candidate_urls:
                candidate_urls.append(alt)

    last_error = None
    for candidate in candidate_urls:
        try:
            eng = create_engine(
                candidate,
                pool_pre_ping=True,
                pool_recycle=300,
                pool_size=10,
                max_overflow=20,
                echo=False
            )
            return eng
        except Exception as e:
            last_error = e
            logger.warning(f"Driver initialization attempt failed for '{candidate[:25]}...': {e}")
            continue

    if last_error:
        raise last_error

engine = create_resilient_engine(DATABASE_URL)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, expire_on_commit=False)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
