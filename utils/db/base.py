# FILE: utils/db/base.py

import contextlib
from typing import Any, List, Dict, Union
from datetime import datetime, timezone
import os

from dotenv import load_dotenv
from loguru import logger
from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    Boolean,
    Float,
    Text,
    JSON,
    text,
    insert,
)
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base

# Define logger path
logger.add("./logs/base_db.log", rotation="1 week")
# Load environment variables
load_dotenv()

# Base class for all models remains the same
Base = declarative_base()


# Common data classes to be reused
class Camera(Base):
    __tablename__ = "cameras"
    id = Column(Integer, primary_key=True)
    channel = Column(DateTime(timezone=True))
    ip_address = Column(String(15))
    name = Column(String(100))
    location = Column(String(100))
    direction = Column(String(20))
    is_active = Column(Boolean)


class CameraTraffic(Base):
    __tablename__ = "camera_traffic"
    id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime(timezone=True))
    camera_name = Column(String(50))
    count = Column(Integer)
    location = Column(String(50))
    direction = Column(String(10))
    day_of_week = Column(String(10))
    is_holiday = Column(Boolean)


class MobileRequestLog(Base):
    __tablename__ = "mobile_request_logs"
    id = Column(String, primary_key=True, index=True)
    client_timestamp = Column(DateTime, nullable=True)
    server_timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    prompt = Column(Text, nullable=False)
    response = Column(Text, nullable=True)
    status = Column(String(50), nullable=False)
    model = Column(String(100), nullable=True)
    response_time = Column(Float, nullable=True)
    prompt_hash = Column(String(64), index=True)
    error_message = Column(Text, nullable=True)

    def __repr__(self):
        return f"<MobileRequestLog(id={self.id}, status={self.status}, model={self.model})>"


def get_async_connection_string() -> str:
    """Construct the ASYNCHRONOUS database connection string."""
    try:
        # Assumes the secret is at /run/secrets/postgres_secrets in Docker
        # For local dev, you might need a different path or load from .env
        secret_path = "/run/secrets/postgres_secrets"
        if not os.path.exists(secret_path):
            secret_path = "./secrets/postgres_secrets.txt"  # Fallback for local dev

        with open(secret_path, "r") as f:
            password = f.read().strip()

        # The key change: postgresql+asyncpg
        return (
            f"postgresql+asyncpg://{os.getenv('DB_USER')}:{password}@"
            f"{os.getenv('DB_HOST')}:{os.getenv('DB_PORT', 5432)}/"
            f"{os.getenv('DB_NAME')}"
        )
    except Exception as e:
        logger.error(f"Failed to get database connection string: {e}")
        raise


# Create ASYNC database engine with connection pooling
async_engine = create_async_engine(
    get_async_connection_string(),
    pool_pre_ping=True,
    pool_recycle=300,
    pool_size=10,
    max_overflow=20,
    echo=True,  # TODO:Set to False in prod
)

# Create an ASYNC session factory
AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,  # Important for async operations
    autoflush=False,
    autocommit=False,
)

# Refactored query functions to be async


async def execute_query(query: str, params: dict = None) -> list:
    """Execute a read-only query and return results as list of dictionaries."""
    try:
        async with async_engine.connect() as conn:
            result = await conn.execute(text(query), params or {})
            # .mappings() is a convenient way to get dict-like rows
            return result.mappings().all()
    except Exception as e:
        logger.error(f"Async query execution failed: {e}")
        return []


async def single_insert_query(db_table: Base, query_values: dict):
    """Execute an async insert query for a single row."""
    async with AsyncSessionLocal() as session:
        try:
            session.add(db_table(**query_values))
            await session.commit()
        except Exception as e:
            await session.rollback()
            logger.error(f"Failed to insert data into {db_table.__tablename__}: {e}")
            raise


async def bulk_insert_query(
    db_table_name: type[Base],
    query_values: Union[Dict[str, Any], List[Dict[str, Any]]],
    batch_size: int = 500,  # Added default batch_size
):
    """Execute an async bulk insert query."""
    if not query_values:
        return

    # Handle single row (convert to list)
    if isinstance(query_values, dict):
        query_values = [query_values]

    async with AsyncSessionLocal() as session:
        try:
            # SQLAlchemy's `add_all` is efficient for bulk inserts
            for i in range(0, len(query_values), batch_size):
                batch = [
                    db_table_name(**row) for row in query_values[i : i + batch_size]
                ]
                session.add_all(batch)
                await session.commit()  # Commit each batch
            logger.info(
                f"Successfully inserted {len(query_values)} rows into {db_table_name.__tablename__}."
            )
        except Exception as e:
            await session.rollback()
            logger.error(
                f"Failed to bulk insert data into {db_table_name.__tablename__}: {e}"
            )
            raise


# Dependency to get a DB session in FastAPI endpoints
async def get_db() -> AsyncSession:
    """FastAPI dependency that provides an async database session."""
    async_session = AsyncSessionLocal()
    try:
        yield async_session
    finally:
        await async_session.close()


# Other utility functions
async def init_db() -> None:
    """Initialize the database by creating all tables."""
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables created successfully (if they didn't exist).")


async def shutdown_db() -> None:
    """Properly close all database connections."""
    await async_engine.dispose()
    logger.info("Database connections closed.")
