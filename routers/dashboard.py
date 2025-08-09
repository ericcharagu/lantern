# routers/dashboard.py
#!/usr/bin/env python3

from datetime import date
from typing import Annotated, Optional
from fastapi import APIRouter, Depends, Request, Form, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select, update, delete

from dependencies import require_managerial_user
from utils.db.user_db import User
from utils.db.stats_db import get_traffic_analytics, get_latest_detections
from utils.app_tools import calculate_traffic_statistics
from utils.db.base import Camera, get_db, AsyncSession


router = APIRouter(
    prefix="/dashboard",
    tags=["Dashboard"],
    dependencies=[Depends(require_managerial_user)],
)

templates = Jinja2Templates(directory="templates")

@router.get("/", response_class=HTMLResponse)
async def get_dashboard(
    request: Request, current_user: Annotated[User, Depends(require_managerial_user)]
):
    """
    Serves the main dashboard page, visible only to managerial users.
    It fetches and displays today's detection statistics.
    """
    # Fetch and process the daily analytics
    raw_analytics = await get_traffic_analytics(period='daily')
    processed_stats = calculate_traffic_statistics(raw_analytics)

    # Fetch the latest raw detection events to display in the table
    latest_detections = await get_latest_detections(limit=250)

    context = {
        "request": request,
        "user": current_user,
        "stats": processed_stats,
        "raw_data": latest_detections, # Pass latest detections to the template
    }

    return templates.TemplateResponse("dash.html", context)


@router.get("/cameras", response_class=HTMLResponse)
async def get_camera_management(request: Request, db: AsyncSession = Depends(get_db)):
    stmt = select(Camera).order_by(Camera.channel)
    result = await db.execute(stmt)
    cameras = result.scalars().all()
    # This should be part of a larger template or an HTMX partial
    return templates.TemplateResponse(
        "partials/camera_management.html", {"request": request, "cameras": cameras}
    )
# ... (The rest of the CRUD operations for cameras remain the same) ...
# CREATE
@router.post("/cameras")
async def create_camera(
    db: AsyncSession = Depends(get_db),
    channel: int = Form(...),
    name: str = Form(...),
    location: str = Form(...),
    ip_address: str = Form(...),
):
    new_camera = Camera(
        channel=channel,
        name=name,
        location=location,
        ip_address=ip_address,
    )
    db.add(new_camera)
    await db.commit()
    # Redirect back to the dashboard to see the new camera
    return RedirectResponse(url="/dashboard", status_code=status.HTTP_303_SEE_OTHER)


# UPDATE
@router.post("/cameras/{camera_id}")
async def update_camera(
    camera_id: int,
    db: AsyncSession = Depends(get_db),
    name: str = Form(...),
    location: str = Form(...),
    ip_address: str = Form(...),
    channel: str = Form(...),
):
    stmt = (
        update(Camera)
        .where(Camera.id == camera_id)
        .values(
            name=name,
            location=location,
            ip_address=ip_address,
            channel=channel,
        )
    )
    await db.execute(stmt)
    await db.commit()
    return RedirectResponse(url="/dashboard", status_code=status.HTTP_303_SEE_OTHER)


# DELETE
@router.post("/cameras/{camera_id}/delete")
async def delete_camera(camera_id: int, db: AsyncSession = Depends(get_db)):
    stmt = delete(Camera).where(Camera.id == camera_id)
    await db.execute(stmt)
    await db.commit()
    return RedirectResponse(url="/dashboard", status_code=status.HTTP_303_SEE_OTHER)
