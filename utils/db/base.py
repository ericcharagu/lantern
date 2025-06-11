# db/base.py
from sqlalchemy import create_engine, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, scoped_session
from datetime import datetime, timezone
from dotenv import load_dotenv
import os
from loguru import logger
from typing import Any
import contextlib

# Load environment variables
load_dotenv()

def get_connection_string() -> str:
    """Construct the database connection string from environment variables"""
    try:
        with open("/app/secrets/postgres_secrets.txt", "r") as f:
            password = f.read().strip()
        
        return (
            f"postgresql://{os.getenv('DB_USER')}:{password}@"
            f"{os.getenv('DB_HOST')}:{os.getenv('DB_PORT', 5432)}/"
            f"{os.getenv('DB_NAME')}"
        )
    except Exception as e:
        logger.error(f"Failed to get database connection string: {e}")
        raise

# Create database engine with connection pooling
engine = create_engine(
    get_connection_string(),
    pool_pre_ping=True,          # Check connections before using them
    pool_recycle=300,            # Recycle connections after 5 minutes
    pool_size=10,                # Number of connections to keep open
    max_overflow=20,             # Allow 20 additional connections during spikes
    echo=True,                  # Set to True for SQL query logging
    connect_args={
        "connect_timeout": 5,    # 5 second connection timeout
        "keepalives": 1,         # Enable TCP keepalive
        "keepalives_idle": 30,   # Seconds before first keepalive
        "keepalives_interval": 10, # Interval between keepalives
        "keepalives_count": 5    # Number of keepalives before dropping
    }
)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,      # Automatically flush changes
    autocommit=False,    # No automatic commits
    expire_on_commit=True # Expire instances after commit
)

# Scoped session for thread safety
Session = scoped_session(SessionLocal)

# Base class for all models
Base = declarative_base()

#for the first version of stats_db
def execute_query(query: str, params: dict) -> list:
    """Execute a query and return results as list of dictionaries"""
    try:
        with engine.connect() as conn:
            result = conn.execute(text(query), params or {})
            columns = result.keys()
            return [dict(zip(columns, row)) for row in result.fetchall()]
    except Exception as e:
        logger.error(f"Query execution failed: {e}")
        return []

def init_db() -> None:
    """Initialize the database by creating all tables"""
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created successfully")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise

@contextlib.contextmanager
def session_scope() -> Any:
    """Provide a transactional scope around a series of operations"""
    session = Session()
    try:
        yield session
        session.commit()
    except Exception as e:
        session.rollback()
        logger.error(f"Session rollback due to error: {e}")
        raise
    finally:
        session.close()

def shutdown_session() -> None:
    """Properly close all database connections"""
    Session.remove()
    engine.dispose()
    logger.info("Database connections closed")

# Add utility functions that might be used across models
def current_time() -> datetime:
    """Get current UTC time"""
    return datetime.now(timezone.utc)

def get_db():
    db = Session()
    try:
        yield db
    except ValueError:
        db.rollback()
        raise
    finally:
        db.close()
