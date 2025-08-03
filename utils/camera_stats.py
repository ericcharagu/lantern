# utils/camera_stats.py

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import declarative_base
from datetime import datetime, timedelta
from loguru import logger
from utils.timezone import nairobi_tz
from .db.base import DetectionLog  

# Logging
logger.add("./logs/camera_stats.log", rotation="1 week")

Base = declarative_base()

async def get_detection_counts(session: AsyncSession, hours: int = 24) -> list:
    """Get detection counts per camera for the last N hours."""
    time_threshold = datetime.now(nairobi_tz) - timedelta(hours=hours)
    stmt = (
        select(
            DetectionLog.camera_name,
            func.count(DetectionLog.id).label("detection_count"),
        )
        .where(DetectionLog.timestamp >= time_threshold)
        .group_by(DetectionLog.camera_name)
    )
    result = await session.execute(stmt)
    return result.mappings().all()


async def get_confidence_stats(session: AsyncSession) -> list:
    """Get average confidence by class."""
    stmt = select(
        DetectionLog.class_id,
        func.avg(DetectionLog.confidence).label("avg_confidence"),
        func.max(DetectionLog.confidence).label("max_confidence"),
        func.min(DetectionLog.confidence).label("min_confidence"),
    ).group_by(DetectionLog.class_id)
    result = await session.execute(stmt)
    return result.mappings().all()


async def get_movement_stats(session: AsyncSession, camera_name: str):
    """Get movement statistics (x/y center averages)."""
    x_center:float=DetectionLog.box_x1+((DetectionLog.box_x2-DetectionLog.box_x1)/2)
    y_center:float=DetectionLog.box_y1+((DetectionLog.box_y2-DetectionLog.box_y1)/2)
    stmt = select(
        func.avg(x_center).label("avg_x"),
        func.avg(y_center).label("avg_y"),
        func.stddev(x_center).label("stddev_x"),
        func.stddev(y_center).label("stddev_y"),
    )
    if camera_name:
        stmt = stmt.where(DetectionLog.camera_name == camera_name)

    result = await session.execute(stmt)
    return result.mappings().first()

def close(session: AsyncSession):
    session.close()
