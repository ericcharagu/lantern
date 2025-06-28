import asyncio
import multiprocessing as mp
import os
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from threading import Lock
from typing import Dict, List, Optional

import cv2
import httpx
import numpy as np
from dotenv import load_dotenv
from fastapi import APIRouter, Response
from fastapi.responses import HTMLResponse, StreamingResponse
from loguru import logger
from utils.db.base import CameraTraffic, bulk_insert_query
from utils.holidays import holiday_checker

# Configure logging
logger.add("./logs/multi-camera.log", rotation="1 week")
with open("/app/secrets/camera_login_secrets.txt", "r") as f:
    camera_rtsp_password = f.read().strip()
load_dotenv()
# Constants
USERNAME = os.getenv("CAMERA_RTSP_USERNAME")
PASSWORD = camera_rtsp_password
PORT = 554
VIDEO_FPS = 30
DETECTION_INTERVAL = 1.0  # Process detection every 1 second
BATCH_SIZE = 4  # Process cameras in batches
MAX_WORKERS = min(8, mp.cpu_count())  # Limit workers based on CPU cores
query_batch_size = 30


@dataclass
class DetectionResult:
    timestamp: str
    camera_name: str
    count: int
    location: str
    day_of_week: str
    is_holiday: bool
    direction: str
    # confidence_scores: int
    # bounding_boxes: List[List[float]]


TEST_DIRECTION = "Entry"
# Process pool for YOLO inference
YOLO_SERVICE_URL = "http://yolo_service:5000/detect"

# Create a single, reusable async client for performance
async_http_client = httpx.AsyncClient(timeout=10.0)
CAMERAS = {
    1: {
        "channel": 1,
        "ip": "192.168.1.151",
        "name": "Third Floor Left",
        "location": "Third Floor",
    },
    2: {
        "channel": 2,
        "ip": "192.168.1.151",
        "name": "Inner Reception",
        "location": "Ground Floor",
    },
    3: {
        "channel": 3,
        "ip": "192.168.1.151",
        "name": "Exit Gate Wall",
        "location": "exit_gate",
    },
    4: {
        "channel": 4,
        "ip": "192.168.1.151",
        "name": "Main Gate",
        "location": "main_entrance",
    },
    5: {
        "channel": 5,
        "ip": "192.168.1.151",
        "name": "Third Floor Right",
        "location": "Third Floor",
    },
    6: {
        "channel": 6,
        "ip": "192.168.1.151",
        "name": "First Floor Right",
        "location": "First Floor",
    },
    7: {
        "channel": 7,
        "ip": "192.168.1.151",
        "name": "Ground Floor Right",
        "location": "Ground Floor",
    },
    8: {
        "channel": 8,
        "ip": "192.168.1.151",
        "name": "Second Floor Right",
        "location": "Second Floor",
    },
    10: {
        "channel": 10,
        "ip": "192.168.1.151",
        "name": "Main Entrance",
        "location": "main_entrance",
    },
    11: {
        "channel": 11,
        "ip": "192.168.1.151",
        "name": "First Floor Stairs",
        "location": "First Floor",
    },
    12: {
        "channel": 12,
        "ip": "192.168.1.151",
        "name": "Third Floor Stairs",
        "location": "Third Floor",
    },
    13: {
        "channel": 13,
        "ip": "192.168.1.151",
        "name": "Front Left",
        "location": "Ground Floor",
    },
    14: {
        "channel": 14,
        "ip": "192.168.1.151",
        "name": "Floor Right",
        "location": "Ground Floor",
    },
    15: {
        "channel": 15,
        "ip": "192.168.1.151",
        "name": "Borehole",
        "location": "Borehole",
    },
    #  16: {
    #        "channel": 16,
    #       "ip": "192.168.1.90",
    #       "name": "Fourteenth Flight",
    #       "location": "stairway_14",
    #   },
    17: {
        "channel": 17,
        "ip": "192.168.1.151",
        "name": "Fourth Floor Stairs",
        "location": "Fourth Floor",
    },
    18: {
        "channel": 18,
        "ip": "192.168.1.151",
        "name": "Fourth Floor Left",
        "location": "Fourth Floor",
    },
    19: {
        "channel": 19,
        "ip": "192.168.1.151",
        "name": "Ground Floor Stairs",
        "location": "Ground Floor",
    },
    20: {
        "channel": 20,
        "ip": "192.168.1.151",
        "name": "Fourth Floor Right",
        "location": "Fourth Floor",
    },
    21: {
        "channel": 21,
        "ip": "192.168.1.151",
        "name": "Exit Gate",
        "location": "exit_gate",
    },
    # Fish Eye with the altered_view
    # 22: {
    #    "channel": 22,
    #    "ip": "192.168.1.151",
    #    "name": "Twentieth Flight",
    #    "location": "stairway_20",
    # },
    23: {
        "channel": 23,
        "ip": "192.168.1.151",
        "name": "Restaurant 1",
        "location": "restaurant",
    },
    24: {
        "channel": 24,
        "ip": "192.168.1.151",
        "name": "Second Floor Stairs",
        "location": "Second Floor",
    },
    25: {
        "channel": 25,
        "ip": "192.168.1.151",
        "name": "Kitchen",
        "location": "restaurant",
    },
    26: {
        "channel": 26,
        "ip": "192.168.1.151",
        "name": "Staff Entrance",
        "location": "yard",
    },
    27: {
        "channel": 27,
        "ip": "192.168.1.151",
        "name": "Rear Wall",
        "location": "yard",
    },
    28: {
        "channel": 28,
        "ip": "192.168.1.151",
        "name": "Server Room",
        "location": "Second Floor",
    },
    29: {
        "channel": 29,
        "ip": "192.168.1.151",
        "name": "Restaurant 2",
        "location": "restaurant",
    },
    30: {
        "channel": 30,
        "ip": "192.168.1.151",
        "name": "Reception",
        "location": "Ground Floor",
    },
    31: {
        "channel": 31,
        "ip": "192.168.1.151",
        "name": "Ground Floor Left",
        "location": "Ground Floor",
    },
    32: {
        "channel": 32,
        "ip": "192.168.1.151",
        "name": "First Floor Left",
        "location": "First Floor",
    },
}

detection_queue = asyncio.Queue(maxsize=100)
stream_active = True
current_frames: Dict[int, Optional[bytes]] = {cam_id: None for cam_id in CAMERAS}
frame_locks: Dict[int, Lock] = {cam_id: Lock() for cam_id in CAMERAS}


async def load_camera_configurations():
    """
    Fetches active camera configurations from the database at application startup.
    It populates the global state dictionaries (CAMERAS, current_frames,
    and frame_locks) that are essential for the camera processing tasks.
    """
    logger.info("Attempting to load camera configurations from database...")
    db_session: AsyncSession
    async for db_session in get_db():
        try:
            # SQL query to get all cameras marked as active, ordered by their channel number
            query = text(
                """
                SELECT channel, ip, name, location
                FROM cameras
                ORDER BY channel
                """
            )

            result = await db_session.execute(query)
            cameras_from_db = result.mappings().all()

            if not cameras_from_db:
                logger.warning(
                    "No active cameras found in the database. The camera streaming service will be idle."
                )
                # Ensure globals are empty if no cameras are found
                CAMERAS.clear()
                current_frames.clear()
                frame_locks.clear()
                return  # Exit the function early

            CAMERAS.clear()
            current_frames.clear()
            frame_locks.clear()
            logger.debug("Cleared existing camera configurations for a fresh load.")

            # --- Populate the global state from the database records ---
            for cam in cameras_from_db:
                cam_id = cam["channel"]

                # 1. Add the camera's configuration to the main dictionary
                CAMERAS[cam_id] = {
                    "channel": cam_id,
                    "ip": cam["ip_address"],
                    "name": cam["name"],
                    "location": cam["location"],
                }

                # 2. Initialize the placeholder for the latest frame to None
                current_frames[cam_id] = None

                # 3. Initialize an asyncio.Lock for each camera to prevent race conditions
                #    when updating the current_frame from multiple async tasks.
                frame_locks[cam_id] = asyncio.Lock()

            logger.success(
                f"Successfully loaded and initialized {len(CAMERAS)} active camera configurations."
            )
            return CAMERAS
        except Exception as e:
            logger.error(
                f"FATAL: Could not load camera configurations from database. Error: {e}"
            )
        finally:
            await db_session.close()


logger.info(load_cameras_configurations())


async def detection_processor():
    """Background task to process detection queue and send to database"""
    batch = []
    last_batch_time = time.time()

    while stream_active:
        try:
            # Wait for detection results or timeout
            try:
                detection = await asyncio.wait_for(detection_queue.get(), timeout=5.0)
                if detection:
                    batch.append(detection)
            except asyncio.TimeoutError:
                pass

            # Process batch if it's full or enough time has passed
            current_time = time.time()
            if (len(batch) >= 10) or (batch and (current_time - last_batch_time) > 30):
                if batch:
                    logger.info(batch)
                    await send_detections_to_database(batch)
                    batch.clear()
                    last_batch_time = current_time

        except ValueError as e:
            logger.error(f"Detection processor error: {str(e)}")
            await asyncio.sleep(1)


async def send_detections_to_database(detections: List[DetectionResult]):
    """Send detection batch to PostgreSQL database."""
    try:
        logger.info(f"received detections {detctions}")
        detection_dicts = [asdict(detection) for detection in detections]
        # Placeholder for database insertion
        logger.info(f"Sending {len(detections)} detections to database")

        # Example of what the function call would look like:
        await bulk_insert_query(CameraTraffic, detection_dicts, query_batch_size)

    except ValueError as e:
        logger.error(f"Database insertion error: {str(e)}")


def generate_rtsp_url(camera: dict) -> List[str]:
    base_url = f"rtsp://{USERNAME}:{PASSWORD}@{camera['ip']}:{PORT}"
    return [
        f"{base_url}/cam/realmonitor?channel={camera['channel']}&subtype=0",  # Dahua format
    ]


async def get_detections_from_service(frame: np.ndarray) -> Optional[dict]:
    """Encodes a frame and sends it to the YOLO service for detection."""
    try:
        # Encode the frame to JPEG format in memory
        is_success, buffer = cv2.imencode(".jpg", frame)
        if not is_success:
            logger.warning("Failed to encode frame to JPEG.")
            return None

        # Prepare the file for multipart/form-data upload
        files = {
            "file": (f"{datetime.now()}_frame.jpg", buffer.tobytes(), "image/jpeg")
        }

        # Make the async HTTP request
        response = await async_http_client.post(YOLO_SERVICE_URL, files=files)
        # Check for successful response
        response.raise_for_status()  # Raises an exception for 4xx/5xx errors

        return response.json()

    except ValueError as e:
        logger.error(f"HTTP request to YOLO service failed: {e}")
        return None
    except Exception as e:
        logger.error(f"An unexpected error occurred when calling YOLO service: {e}")
        return None


@logger.catch()
async def capture_camera_frames(cam_id: int, camera_config: dict):
    """
    Background task to capture frames, inspired by the Flask app's resilience logic.
    """
    global current_frames

    rtsp_urls_to_try = generate_rtsp_url(camera_config)
    working_url = None
    last_detection_time = 0

    while stream_active:
        # --- Stage 1: Find a working URL (inspired by find_working_rtsp_url) ---
        if not working_url:
            for url in rtsp_urls_to_try:
                try:
                    cap_test = cv2.VideoCapture(url, cv2.CAP_FFMPEG)
                    if cap_test.isOpened():
                        success, _ = cap_test.read()
                        if success:
                            logger.success(f"Cam {cam_id}: Found working RTSP URL.")
                            working_url = url
                            cap_test.release()
                            break  # Exit the URL testing loop
                        else:
                            logger.warning(
                                f"Cam {cam_id}: URL opens but cannot read frames."
                            )
                    cap_test.release()
                except Exception as e:
                    logger.error(f"Cam {cam_id}: Exception during URL test: {e}")

            if not working_url:
                logger.error(
                    f"Cam {cam_id}: No working URL found after all attempts. Retrying in 30 seconds."
                )
                await asyncio.sleep(30)
                continue

        # --- Stage 2: Main Capture Loop (inspired by capture_frames) ---
        cap = cv2.VideoCapture(working_url)
        if not cap.isOpened():
            logger.error(f"Cam {cam_id}: Failed to reopen working URL. Resetting...")
            working_url = None
            await asyncio.sleep(10)
            continue

        logger.info(f"Cam {cam_id}: Successfully connected to stream.")
        consecutive_failures = 0
        max_consecutive_failures = 60  # e.g., 2 seconds of dropped frames at 30fps

        while stream_active:
            success, frame = cap.read()

            if not success or frame is None:
                consecutive_failures += 1
                if consecutive_failures > max_consecutive_failures:
                    logger.warning(
                        f"Cam {cam_id}: Stream lost (too many failed reads). Reconnecting."
                    )
                    break  # Break inner loop to trigger a reconnect
                await asyncio.sleep(0.01)  # Short sleep on frame drop
                continue

            consecutive_failures = 0  # Reset on successful read
            # 1. Encode frame for web streaming
            display_frame = cv2.resize(frame, (640, 480))
            _, buffer = cv2.imencode(
                ".jpg", display_frame, [cv2.IMWRITE_JPEG_QUALITY, 70]
            )

            # Use an asyncio.Lock for safe async access to the shared dictionary
            async with frame_locks[cam_id]:
                current_frames[cam_id] = buffer.tobytes()

            # 2. Send frame for YOLO detection at intervals
            current_time = time.time()
            if current_time - last_detection_time >= DETECTION_INTERVAL:
                last_detection_time = current_time
                # This part remains the same: it calls the external yolo_service
                detection_result = await get_detections_from_service(frame)
                logger.info(detection_result)

            await asyncio.sleep(1.0 / VIDEO_FPS)  # Control the loop speed

        cap.release()
        logger.info(f"Cam {cam_id}: Capture released. Will attempt to reconnect.")
        await asyncio.sleep(5)


async def handle_detection_result(future):
    """Handle the result of YOLO detection"""
    try:
        result = await future
        if result:  # Only queue if persons detected
            await detection_queue.put(result)
    except ValueError as e:
        logger.error(f"Error handling detection result: {str(e)}")


async def generate_frames(cam_id: int):
    """Generator function for streaming frames"""
    while True:
        with frame_locks[cam_id]:
            frame = current_frames[cam_id]

        if frame:
            yield (b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + frame + b"\r\n")
        else:
            # Send placeholder image if no frame available
            placeholder = np.zeros((480, 640, 3), dtype=np.uint8)
            cv2.putText(
                placeholder,
                f"Camera {cam_id} Offline",
                (50, 240),
                cv2.FONT_HERSHEY_SIMPLEX,
                1,
                (255, 255, 255),
                2,
            )
            _, buffer = cv2.imencode(".jpg", placeholder)
            yield (
                b"--frame\r\nContent-Type: image/jpeg\r\n\r\n"
                + buffer.tobytes()
                + b"\r\n"
            )

        await asyncio.sleep(1.0 / VIDEO_FPS)


router = APIRouter(
    prefix="/cameras",
    tags=["camera_detections"],
    responses={401: {"description": "Not authorized"}},
)


@router.get("/home", response_class=HTMLResponse)
async def index():
    """Home page with all camera feeds"""
    camera_html = "".join(
        f"""
        <div class="camera">
            <h3>Camera {cam_id} - {config["name"]}</h3>
            <div class="camera-info">
                <span class="location">Location: {config["location"]}</span>
                <span class="ip">IP: {config["ip"]}</span>
            </div>
            <img src="/video/{cam_id}" alt="Camera {cam_id} Stream" loading="lazy">
        </div>
        """
        for cam_id, config in CAMERAS.items()
    )

    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Optimized Multi-Camera Monitoring System</title>
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            body {{ 
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; 
                margin: 0;
                padding: 20px;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: #333;
            }}
            .container {{
                max-width: 95%;
                margin: 0 auto;
            }}
            h1 {{ 
                color: white; 
                text-align: center;
                margin-bottom: 30px;
                text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
                font-size: 2.5em;
            }}
            .stats {{
                background: rgba(255,255,255,0.1);
                backdrop-filter: blur(10px);
                border-radius: 15px;
                padding: 20px;
                margin-bottom: 30px;
                text-align: center;
                color: white;
            }}
            .camera-grid {{
                display: grid;
                grid-template-columns: repeat(auto-fill, minmax(400px, 1fr));
                gap: 25px;
            }}
            .camera {{
                background: rgba(255,255,255,0.95);
                backdrop-filter: blur(10px);
                border-radius: 15px;
                padding: 20px;
                box-shadow: 0 8px 32px rgba(0,0,0,0.1);
                transition: transform 0.3s ease, box-shadow 0.3s ease;
            }}
            .camera:hover {{
                transform: translateY(-5px);
                box-shadow: 0 12px 40px rgba(0,0,0,0.15);
            }}
            .camera h3 {{
                margin: 0 0 10px 0;
                font-size: 18px;
                color: #333;
                border-bottom: 2px solid #667eea;
                padding-bottom: 5px;
            }}
            .camera-info {{
                display: flex;
                justify-content: space-between;
                margin-bottom: 15px;
                font-size: 12px;
                color: #666;
            }}
            .camera img {{
                width: 100%;
                height: auto;
                max-height: 300px;
                border-radius: 10px;
                box-shadow: 0 4px 8px rgba(0,0,0,0.1);
            }}
            .status {{
                display: inline-block;
                padding: 4px 8px;
                border-radius: 20px;
                font-size: 11px;
                font-weight: bold;
                background: #4CAF50;
                color: white;
                margin-left: 10px;
            }}
            @media (max-width: 768px) {{
                .camera-grid {{
                    grid-template-columns: 1fr;
                }}
                h1 {{
                    font-size: 2em;
                }}
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🎥 Lantern Seviced Apartments</h1>
            <div class="stats">
                <h3>System Status</h3>
                <p><strong>{len(CAMERAS)}</strong> Cameras Active |
                   <strong>Real-time</strong> Person Detection | 
                   <strong>AI-Powered</strong> Analytics</p>
            </div>
            <div class="camera-grid">
                {camera_html}
            </div>
        </div>
        <script>
            // Auto-refresh detection status
            setInterval(() => {{
                fetch('/api/status')
                    .then(response => response.json())
                    .then(data => {{
                        console.log('System status:', data);
                    }})
                    .catch(err => console.log('Status check failed'));
            }}, 30000);
        </script>
    </body>
    </html>
    """


@router.get("/video/{cam_id}")
async def video_feed(cam_id: int):
    """Video streaming endpoint for individual cameras"""
    if cam_id not in CAMERAS:
        return Response("Camera not found", status_code=404)

    return StreamingResponse(
        generate_frames(cam_id),
        media_type="multipart/x-mixed-replace; boundary=frame",
        headers={"Cache-Control": "no-cache, no-store, must-revalidate"},
    )


@router.get("/api/status")
async def get_status():
    """API endpoint to get system status"""
    active_cameras = sum(1 for frame in current_frames.values() if frame is not None)

    return {
        "total_cameras": len(CAMERAS),
        "active_cameras": active_cameras,
        "detection_queue_size": detection_queue.qsize(),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


"""
if __name__ == "__main__":
    # Set multiprocessing start method
    mp.set_start_method("spawn", force=True)

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=6000,
        log_level="info",
        timeout_keep_alive=300,
        reload=True,
    )"""
