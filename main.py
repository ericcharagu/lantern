# FILE: app/main.py

import asyncio
from contextlib import asynccontextmanager
from concurrent.futures import ProcessPoolExecutor

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from loguru import logger

from app.config import settings
from app.routers import auth, cameras, analysis, webhooks  # Import all your routers
from app.routers.cameras import (
    MAX_WORKERS,
    CAMERAS,
    BATCH_SIZE,
    capture_camera_frames,
    detection_processor,
)


# =============================================================================
# LIFESPAN MANAGER
# =============================================================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manages application-wide startup and shutdown events."""
    logger.info("Application starting up...")

    # Initialize and assign the process pool for YOLO tasks
    process_pool = ProcessPoolExecutor(max_workers=MAX_WORKERS)
    cameras.process_pool = process_pool
    logger.info(f"Process pool initialized with {MAX_WORKERS} workers.")

    # Start background tasks for camera processing
    asyncio.create_task(detection_processor())
    logger.info("Detection processor background task started.")

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
    if cameras.process_pool:
        cameras.process_pool.shutdown(wait=True)
        logger.info("Process pool has been shut down.")
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
# You could add other middleware here, like the auth_middleware

# 2. Mount Static Files and Templates
app.mount("/static", StaticFiles(directory="./static"), name="static")
templates = Jinja2Templates(directory="templates")

# 3. Include Routers
# This is where you connect all your endpoint logic.
app.include_router(auth.router)
app.include_router(cameras.router)
app.include_router(analysis.router)
# app.include_router(webhooks.router) # Add this once you create the file


# 4. Add a simple root endpoint for a basic health check
@app.get("/")
async def root(request: Request):
    """A simple root endpoint to confirm the API is running."""
    return {
        "message": "Welcome to the Foot Traffic Analytics API",
        "docs_url": request.url_for("swagger_ui_html"),
    }
