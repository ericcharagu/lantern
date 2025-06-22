import asyncio
import multiprocessing as mp
import time
from concurrent.futures import ProcessPoolExecutor
from contextlib import asynccontextmanager
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from threading import Lock
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np
import uvicorn
from fastapi import FastAPI, Response, APIRouter
from fastapi.responses import HTMLResponse, StreamingResponse
from loguru import logger
from ultralytics import YOLO
from utils.db.base import CameraTraffic, bulk_insert_query
from utils.holidays import holiday_checker
import os
from dotenv import load_dotenv

# Configure logging
logger.add("./logs/multi-camera.log", rotation="1 week")
with open("/run/secrets/camera_login_secrets.txt", "r") as f:
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


# TODO:Denote cameras with direction implicatins such as the entrances and exits.
# TODO: Create separate tables/columns for each of those "special" data types. Consider storing them in a separate table that can house the additional metrics
TEST_DIRECTION = "Entry"
# Camera configuration dictionary
CAMERAS = {
    1: {
        "channel": 1,
        "ip": "192.168.1.79",
        "name": "Borehole",
        "location": "borehole_area",
    },
    2: {
        "channel": 2,
        "ip": "192.168.1.199",
        "name": "Borehole",
        "location": "borehole_area",
    },
    3: {
        "channel": 3,
        "ip": "192.168.1.67",
        "name": "Exit Gate Wall",
        "location": "exit_gate",
    },
    4: {
        "channel": 4,
        "ip": "192.168.1.139",
        "name": "Main Gate",
        "location": "main_entrance",
    },
    5: {
        "channel": 5,
        "ip": "192.168.1.78",
        "name": "Third Flight",
        "location": "stairway_03",
    },
    6: {
        "channel": 6,
        "ip": "192.168.1.66",
        "name": "Fourth Flight",
        "location": "stairway_04",
    },
    7: {
        "channel": 7,
        "ip": "192.168.1.197",
        "name": "Fifth Flight",
        "location": "stairway_05",
    },
    8: {
        "channel": 8,
        "ip": "192.168.1.75",
        "name": "Sixth Flight",
        "location": "stairway_06",
    },
    9: {
        "channel": 9,
        "ip": "192.168.1.73",
        "name": "Seventh Flight",
        "location": "stairway_07",
    },
    10: {
        "channel": 10,
        "ip": "192.168.1.74",
        "name": "Eighth Flight",
        "location": "stairway_08",
    },
    11: {
        "channel": 11,
        "ip": "192.168.1.82",
        "name": "Ninth Flight",
        "location": "stairway_09",
    },
    12: {
        "channel": 12,
        "ip": "192.168.1.77",
        "name": "Tenth Flight",
        "location": "stairway_10",
    },
    13: {
        "channel": 13,
        "ip": "192.168.1.70",
        "name": "Eleventh Flight",
        "location": "stairway_11",
    },
    14: {
        "channel": 14,
        "ip": "192.168.1.81",
        "name": "Twelfth Flight",
        "location": "stairway_12",
    },
    15: {
        "channel": 15,
        "ip": "192.168.1.89",
        "name": "Thirteenth Flight",
        "location": "stairway_13",
    },
    16: {
        "channel": 16,
        "ip": "192.168.1.90",
        "name": "Fourteenth Flight",
        "location": "stairway_14",
    },
    17: {
        "channel": 17,
        "ip": "192.168.1.137",
        "name": "Fifteenth Flight",
        "location": "stairway_15",
    },
    18: {
        "channel": 18,
        "ip": "192.168.1.136",
        "name": "Sixteenth Flight",
        "location": "stairway_16",
    },
    19: {
        "channel": 19,
        "ip": "192.168.1.202",
        "name": "Seventeenth Flight",
        "location": "stairway_17",
    },
    20: {
        "channel": 20,
        "ip": "192.168.1.72",
        "name": "Eighteenth Flight",
        "location": "stairway_18",
    },
    21: {
        "channel": 21,
        "ip": "192.168.1.129",
        "name": "Nineteenth Flight",
        "location": "stairway_19",
    },
    22: {
        "channel": 22,
        "ip": "192.168.1.116",
        "name": "Twentieth Flight",
        "location": "stairway_20",
    },
    23: {
        "channel": 23,
        "ip": "192.168.1.190",
        "name": "Twenty-first Flight",
        "location": "stairway_21",
    },
    24: {
        "channel": 24,
        "ip": "192.168.1.135",
        "name": "Twenty-second Flight",
        "location": "stairway_22",
    },
    25: {
        "channel": 25,
        "ip": "192.168.1.103",
        "name": "Twenty-third Flight",
        "location": "stairway_23",
    },
    26: {
        "channel": 26,
        "ip": "192.168.1.61",
        "name": "Twenty-fourth Flight",
        "location": "stairway_24",
    },
    27: {
        "channel": 27,
        "ip": "192.168.1.71",
        "name": "Twenty-fifth Flight",
        "location": "stairway_25",
    },
    28: {
        "channel": 28,
        "ip": "192.168.1.102",
        "name": "Twenty-sixth Flight",
        "location": "stairway_26",
    },
    29: {
        "channel": 29,
        "ip": "192.168.1.68",
        "name": "Twenty-seventh Flight",
        "location": "stairway_27",
    },
    30: {
        "channel": 30,
        "ip": "192.168.1.120",
        "name": "Twenty-eighth Flight",
        "location": "stairway_28",
    },
    31: {
        "channel": 31,
        "ip": "192.168.1.69",
        "name": "Twenty-ninth Flight",
        "location": "stairway_29",
    },
    32: {
        "channel": 32,
        "ip": "192.168.1.76",
        "name": "Thirtieth Flight",
        "location": "stairway_30",
    },
}

# Global variables for frame and detection management
current_frames: Dict[int, Optional[bytes]] = {cam_id: None for cam_id in CAMERAS}
frame_locks: Dict[int, Lock] = {cam_id: Lock() for cam_id in CAMERAS}
detection_queue = asyncio.Queue(maxsize=100)
stream_active = True

# Process pool for YOLO inference
process_pool = None

# Declaring the onject detection mdel to be used
object_detection_model = None


def process_yolo_detection(
    frame_data: Tuple[np.ndarray, int, str, str],
) -> Optional[DetectionResult]:
    """Process YOLO detection in a separate process"""
    global object_detection_model
    try:
        # Lazy-load the model once per worker process
        if object_detection_model is None:
            object_detection_model = YOLO("yolo11l.pt")
            logger.info(f"YOLO model loaded in process {mp.current_process().pid}")

        frame, cam_id, camera_name, location = frame_data

        results = object_detection_model.predict(
            frame, conf=0.6, classes=[0], verbose=False
        )
        if len(results) > 0 and len(results[0].boxes) > 0:
            boxes = results[0].boxes
            person_detections = boxes[boxes.cls == 0]  # Filter for persons only

            count = len(person_detections)
            # confidence_scores = (
            #     person_detections.conf.cpu().numpy().tolist() if count > 0 else []
            # )
            # bounding_boxes = (
            #    person_detections.xyxy.cpu().numpy().tolist() if count > 0 else []
            # )

            now = datetime.now(timezone.utc)

            return DetectionResult(
                timestamp=now.isoformat(),
                camera_name=f"cam_{location}_{cam_id:02d}",
                count=count,
                location=location,
                day_of_week=now.strftime("%A").lower(),
                is_holiday=holiday_checker(),
                direction=TEST_DIRECTION,
                # confidence_scores=confidence_scores,
                # bounding_boxes=bounding_boxes,
            )
    except ValueError as e:
        logger.error(f"YOLO processing error for camera {cam_id}: {str(e)}")

    return None


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
                    await send_detections_to_database(batch)
                    batch.clear()
                    last_batch_time = current_time

        except ValueError as e:
            logger.error(f"Detection processor error: {str(e)}")
            await asyncio.sleep(1)


async def send_detections_to_database(detections: List[DetectionResult]):
    """Send detection batch to PostgreSQL database"""
    try:
        # Import your database function here
        # from database_handler import insert_detections

        detection_dicts = [asdict(detection) for detection in detections]

        # Placeholder for database insertion
        logger.info(f"Sending {len(detections)} detections to database")

        # Example of what the function call would look like:
        await bulk_insert_query(CameraTraffic, detection_dicts, query_batch_size)

    except ValueError as e:
        logger.error(f"Database insertion error: {str(e)}")


def generate_rtsp_url(camera: dict) -> List[str]:
    """Generate possible RTSP URLs for a camera"""
    base_url = f"rtsp://{USERNAME}:{PASSWORD}@{camera['ip']}:{PORT}"
    return [
        f"{base_url}/cam/realmonitor?channel={camera['channel']}&subtype=0",  # Dahua format
        # f"{base_url}/Streaming/Channels/{camera['channel']}01",  # Hikvision format
    ]


async def capture_camera_frames(cam_id: int, camera_config: dict):
    """Optimized background task to capture frames from a specific camera"""
    global current_frames, stream_active, process_pool

    rtsp_urls = generate_rtsp_url(camera_config)
    cap = None
    last_detection_time = 0
    frame_count = 0

    while stream_active:
        # Connection logic
        for url in rtsp_urls:
            try:
                cap = cv2.VideoCapture(url)
                cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # Reduce buffer size
                cap.set(cv2.CAP_PROP_FPS, VIDEO_FPS)

                if cap.isOpened():
                    logger.info(f"Successfully connected to camera {cam_id} at {url}")
                    break
            except Exception as e:
                logger.debug(f"Error connecting to camera {cam_id}: {str(e)}")
                continue

        if cap is None or not cap.isOpened():
            logger.debug(f"Could not connect to any RTSP URL for camera {cam_id}")
            await asyncio.sleep(5)
            continue

        try:
            while stream_active:
                success, frame = cap.read()
                if not success:
                    logger.warning(f"Frame read failed for camera {cam_id}")
                    break

                frame_count += 1
                current_time = time.time()

                # Process detection at intervals (not every frame)
                if current_time - last_detection_time >= DETECTION_INTERVAL:
                    try:
                        # Resize frame for faster processing
                        detection_frame = cv2.resize(frame, (640, 480))

                        # Submit to process pool for YOLO inference
                        loop = asyncio.get_event_loop()
                        future = loop.run_in_executor(
                            process_pool,
                            process_yolo_detection,
                            (
                                detection_frame,
                                cam_id,
                                camera_config["name"],
                                camera_config["location"],
                            ),
                        )
                        # Process the results async
                        asyncio.create_task(handle_detection_result(future))
                        last_detection_time = current_time

                    except ValueError as e:
                        logger.error(
                            f"Detection submission error for camera {cam_id}: {str(e)}"
                        )

                # Encode frame for streaming (smaller size for web display)
                display_frame = cv2.resize(frame, (640, 480))
                success, buffer = cv2.imencode(
                    ".jpg", display_frame, [cv2.IMWRITE_JPEG_QUALITY, 70]
                )

                if success:
                    with frame_locks[cam_id]:
                        current_frames[cam_id] = buffer.tobytes()

                # Control frame rate
                await asyncio.sleep(1.0 / VIDEO_FPS)

        except ValueError as e:
            logger.debug(f"Error in frame capture for camera {cam_id}: {str(e)}")
        finally:
            if cap:
                cap.release()
                logger.info(f"Released capture for camera {cam_id}")

        logger.info(f"Attempting to reconnect to camera {cam_id} in 5 seconds...")
        await asyncio.sleep(5)


async def handle_detection_result(future):
    """Handle the result of YOLO detection"""
    try:
        result = await future
        if result and result.count > 0:  # Only queue if persons detected
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
    prefix="/camera",
    tags=["camera_detections"],
    responses={401: {"description": "Not authorized"}},
)


@router.get("/", response_class=HTMLResponse)
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
            <h1>🎥 Advanced Multi-Camera Surveillance System</h1>
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
