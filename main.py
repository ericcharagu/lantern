# FILE: app/main.py

import asyncio
from contextlib import asynccontextmanager
from concurrent.futures import ProcessPoolExecutor

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from loguru import logger
from middleware.auth_middleware import auth_middleware
from config import settings
from routers import (
    auth,
    analysis,
    cameras,
    webhooks,
    internal,
    dashboard,
)
from routers.cameras import (
    MAX_WORKERS,
    CAMERAS,
    BATCH_SIZE,
    capture_camera_frames,
    detection_processor,
)
from services.nightly_services import nightly_report_task

# =============================================================================
# LIFESPAN MANAGER
# =============================================================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manages application-wide startup and shutdown events."""
    logger.info("Application starting up...")

    # Initialize and assign the process pool for YOLO tasks
    # process_pool = ProcessPoolExecutor(max_workers=MAX_WORKERS)
    # cameras.process_pool = process_pool
    # logger.info(f"Process pool initialized with {MAX_WORKERS} workers.")

    # Start background tasks for camera processing
    asyncio.create_task(detection_processor())
    logger.info("Detection processor background task started.")
    
    # Start the nightly reporting service
    asyncio.create_task(nightly_report_task())
    logger.info("Nightly report background task started.")
    for i in range(0, len(CAMERAS), BATCH_SIZE):
        batch_cameras = dict(list(CAMERAS.items())[i : i + BATCH_SIZE])
        for cam_id, config in batch_cameras.items():
            asyncio.create_task(capture_camera_frames(cam_id, config))
        await asyncio.sleep(1)
    logger.info(f"Started {len(CAMERAS)} camera capture tasks.")

    yield

    logger.info("Application shutting down...")
    cameras.stream_active = False
    logger.info("Signaled all camera streams to stop.")
    # Clean up the httpx client
    await cameras.async_http_client.aclose()
    logger.info("HTTPX client has been closed.")
    logger.info("Application shutdown complete.")


# =============================================================================
# FASTAPI APP INITIALIZATION AND ASSEMBLY
# =============================================================================

# Initialize the FastAPI app with the lifespan manager
app = FastAPI(title=settings.APP_NAME, lifespan=lifespan)

# 1. Add Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# Auth Middleware
app.middleware("http")(auth_middleware)

# 2. Mount Static Files and Templates
app.mount("/static", StaticFiles(directory="./static"), name="static")
templates = Jinja2Templates(directory="templates")

# 3. Include Routers
# This is where you connect all your endpoint logic.
app.include_router(auth.router)
app.include_router(cameras.router)
app.include_router(analysis.router)
app.include_router(webhooks.router)
app.include_router(internal.router)
app.include_router(dashboard.router)


# 4. Add a simple root endpoint for a basic health check
@app.get("/")
async def root(request: Request):
    """A simple root endpoint to confirm the API is running."""
    return {
        "message": "Welcome to the Foot Traffic Analytics API",
        "docs_url": request.url_for("swagger_ui_html"),
    }
