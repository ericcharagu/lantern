#!/usr/bin/env python3

from datetime import date
from typing import Annotated, Optional
from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from dependencies import require_managerial_user
from utils.db.user_db import User
from utils.db.stats_db import get_traffic_analytics
from utils.db.base import Camera, get_db, AsyncSession
from pydantic import BaseModel

router = APIRouter(
    prefix="/dashboard",
    tags=["Dashboard"],
    dependencies=[Depends(require_managerial_user)],  # Secure the whole router
)


class CameraUpdate(BaseModel):
    name: str
    location: str
    ip_address: str
    direction: Optional[str] = None
    is_active: bool


templates = Jinja2Templates(directory="templates")


@router.get("", response_class=HTMLResponse)
async def get_dashboard(
    request: Request, current_user: Annotated[User, Depends(require_managerial_user)]
):
    """
    Serves the main dashboard page, visible only to managerial users.
    It fetches and displays today's traffic statistics.
    """
    today = date.today()

    # Fetch and process the data
    # TODO: remove two different types of dataset. Assuming comes as the SQL result
    raw_analytics = await get_traffic_analytics(today)
    # processed_stats = calculate_traffic_statistics(raw_analytics)

    # The context dictionary passed to the template
    context = {
        "request": request,
        "user": current_user,
        # "stats": processed_stats,
        "raw_data": raw_analytics.get("daily_traffic_data", []),
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


# CREATE
@router.post("/cameras")
async def create_camera(
    db: AsyncSession = Depends(get_db),
    channel: int = Form(...),
    name: str = Form(...),
    location: str = Form(...),
    ip_address: str = Form(...),
    direction: Optional[str] = Form(None),
):
    new_camera = Camera(
        channel=channel,
        name=name,
        location=location,
        ip_address=ip_address,
        direction=direction,
        is_active=True,
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
    direction: Optional[str] = Form(None),
    is_active: bool = Form(False),
):
    stmt = (
        update(Camera)
        .where(Camera.id == camera_id)
        .values(
            name=name,
            location=location,
            ip_address=ip_address,
            direction=direction,
            is_active=is_active,
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
