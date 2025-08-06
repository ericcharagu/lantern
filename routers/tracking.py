# routers/tracking.py
from datetime import datetime, timedelta
from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from dependencies import require_managerial_user
from utils.db.base import get_db
from utils.db.tracking_db import get_track_history_by_id, get_unique_tracks_by_camera
from pydantic import BaseModel

router = APIRouter(
    prefix="/tracking",
    tags=["Object Tracking"],
    dependencies=[Depends(require_managerial_user)],
)

class TrackHistoryItem(BaseModel):
    timestamp: datetime
    confidence: float
    box_x1: float
    box_y1: float
    box_x2: float
    box_y2: float

    class Config:
        from_attributes = True

class TrackSummary(BaseModel):
    tracker_id: int
    object_name: str
    first_seen: datetime
    last_seen: datetime
    detection_count: int

@router.get("/history/{track_id}", response_model=List[TrackHistoryItem])
async def get_tracking_history(track_id: int, db: AsyncSession = Depends(get_db)):
    """
    Get the full movement history for a specific object tracker ID.
    """
    history = await get_track_history_by_id(db, track_id)
    if not history:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No history found for Tracker ID {track_id}",
        )
    return history

@router.get("/camera/{camera_name}", response_model=List[TrackSummary])
async def get_camera_tracks(
    camera_name: str,
    hours: int = Query(1, ge=1, le=24, description="How many hours into the past to search."),
    db: AsyncSession = Depends(get_db)
):
    """
    Get a summary of all unique objects tracked by a specific camera within a recent time window.
    """
    end_time = datetime.now(pytz.utc)
    start_time = end_time - timedelta(hours=hours)

    tracks = await get_unique_tracks_by_camera(db, camera_name, start_time, end_time)
    return tracks