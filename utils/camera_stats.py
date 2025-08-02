# FILE: utils/camera_stats.py (Corrected and Refactored)

from sqlalchemy import func, select, extract, Column, Integer, Float, DateTime, JSON
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import declarative_base
from datetime import datetime, timedelta, timezone
from loguru import logger

# No longer need os, create_engine, or sessionmaker here.
# We will get the session via dependency injection.

# Model definition can stay as it is for type hinting, but it's better
# if it's imported from a central models file to avoid re-definition.
# Assuming it's defined in base.py, we could import it.
from .db.base import DetectionLog  

# Logging
logger.add("./logs/camera_stats.log", rotation="1 week")

Base = declarative_base()


class CameraTrackingData(Base):
    __tablename__ = "camera_tracking_data"
    id = Column(Integer, primary_key=True)
    tracker_id = Column(Integer, nullable=False)
    timestamp = Column(DateTime, nullable=False)
    x_center = Column(Float, nullable=False)
    y_center = Column(Float, nullable=False)
    bbox = Column(JSON, nullable=False)
    class_id = Column(Integer, nullable=False)
    confidence = Column(Float, nullable=False)
    camera_id = Column(Integer, nullable=False)


async def get_detection_counts(session: AsyncSession, hours: int = 24) -> list:
    """Get detection counts per camera for the last N hours."""
    time_threshold = datetime.now(timezone.utc) - timedelta(hours=hours)
    stmt = (
        select(
            CameraTrackingData.camera_id,
            func.count(CameraTrackingData.id).label("detection_count"),
        )
        .where(CameraTrackingData.timestamp >= time_threshold)
        .group_by(CameraTrackingData.camera_id)
    )
    result = await session.execute(stmt)
    return result.mappings().all()


async def get_confidence_stats(session: AsyncSession) -> list:
    """Get average confidence by class."""
    stmt = select(
        CameraTrackingData.class_id,
        func.avg(CameraTrackingData.confidence).label("avg_confidence"),
        func.max(CameraTrackingData.confidence).label("max_confidence"),
        func.min(CameraTrackingData.confidence).label("min_confidence"),
    ).group_by(CameraTrackingData.class_id)
    result = await session.execute(stmt)
    return result.mappings().all()


async def get_movement_stats(session: AsyncSession, camera_id: int = None):
    """Get movement statistics (x/y center averages)."""
    stmt = select(
        func.avg(CameraTrackingData.x_center).label("avg_x"),
        func.avg(CameraTrackingData.y_center).label("avg_y"),
        func.stddev(CameraTrackingData.x_center).label("stddev_x"),
        func.stddev(CameraTrackingData.y_center).label("stddev_y"),
    )
    if camera_id:
        stmt = stmt.where(CameraTrackingData.camera_id == camera_id)

    result = await session.execute(stmt)
    return result.mappings().first()


async def get_tracker_activity(session: AsyncSession, tracker_id: int):
    """Get activity timeline for a specific tracker."""
    return await (
        session.query(
            extract("hour", CameraTrackingData.timestamp).label("hour"),
            func.count(CameraTrackingData.id).label("detections"),
        )
        .filter(
            CameraTrackingData.tracker_id == tracker_id,
            CameraTrackingData.timestamp >= datetime.utcnow() - timedelta(days=1),
        )
        .group_by("hour")
        .order_by("hour")
        .all()
    )


async def get_bbox_stats(session: AsyncSession):
    """Get statistics about bounding box sizes."""
    return await session.query(
        func.avg(CameraTrackingData.bbox[2] - CameraTrackingData.bbox[0]).label(
            "avg_width"
        ),
        func.avg(CameraTrackingData.bbox[3] - CameraTrackingData.bbox[1]).label(
            "avg_height"
        ),
    ).first()


def close(session: AsyncSession):
    session.close()
