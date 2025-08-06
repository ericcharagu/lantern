# utils/db/tracking_db.py
from datetime import datetime
from typing import List
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from .base import DetectionLog

async def get_track_history_by_id(db: AsyncSession, track_id: int) -> List[DetectionLog]:
    """
    Retrieves the complete history for a specific tracker ID, ordered by time.
    """
    try:
        stmt = (
            select(DetectionLog)
            .where(DetectionLog.tracker_id == track_id)
            .order_by(DetectionLog.timestamp.asc())
        )
        result = await db.execute(stmt)
        return result.scalars().all()
    except Exception as e:
        logger.error(f"Error fetching history for track ID {track_id}: {e}")
        return []

async def get_unique_tracks_by_camera(
    db: AsyncSession,
    camera_name: str,
    start_time: datetime,
    end_time: datetime
) -> List[dict]:
    """
    Retrieves a summary of unique tracker IDs seen by a specific camera in a given time window.
    """
    try:
        stmt = (
            select(
                DetectionLog.tracker_id,
                DetectionLog.object_name,
                func.min(DetectionLog.timestamp).label("first_seen"),
                func.max(DetectionLog.timestamp).label("last_seen"),
                func.count(DetectionLog.id).label("detection_count")
            )
            .where(
                DetectionLog.camera_name == camera_name,
                DetectionLog.timestamp.between(start_time, end_time),
                DetectionLog.tracker_id.isnot(None)
            )
            .group_by(DetectionLog.tracker_id, DetectionLog.object_name)
            .order_by(func.min(DetectionLog.timestamp).desc())
        )
        result = await db.execute(stmt)
        return result.mappings().all()
    except Exception as e:
        logger.error(f"Error fetching unique tracks for camera {camera_name}: {e}")
        return []