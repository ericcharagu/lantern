from fastapi import FastAPI, Response
from fastapi.responses import HTMLResponse, StreamingResponse
import cv2
import asyncio
import uvicorn
from ultralytics import YOLO
from threading import Lock
from typing import Dict, Optional
from loguru import logger
import traceback

# Configure logging
logger.add("camera_system.log", rotation="10 MB", retention="7 days")

# Constants
USERNAME = "admin"
PASSWORD = "Lantern@2030"
PORT = 554

# Camera configuration dictionary (32 cameras)
CAMERAS = {
    1: {"channel": 1, "ip": "192.168.1.79", "name": "Borehole"},
    2: {"channel": 2, "ip": "192.168.1.199", "name": "Borehole"},
    3: {"channel": 3, "ip": "192.168.1.67", "name": "Exit Gate Wall"},
    4: {"channel": 4, "ip": "192.168.1.139", "name": "Main Gate"},
    5: {"channel": 5, "ip": "192.168.1.78", "name": "Third Flight"},
    6: {"channel": 6, "ip": "192.168.1.66", "name": "Fourth Flight"},
    7: {"channel": 7, "ip": "192.168.1.197", "name": "Fifth Flight"},
    8: {"channel": 8, "ip": "192.168.1.75", "name": "Sixth Flight"},
    9: {"channel": 9, "ip": "192.168.1.73", "name": "Seventh Flight"},
    10: {"channel": 10, "ip": "192.168.1.74", "name": "Eighth Flight"},
    11: {"channel": 11, "ip": "192.168.1.82", "name": "Ninth Flight"},
    12: {"channel": 12, "ip": "192.168.1.77", "name": "Tenth Flight"},
    13: {"channel": 13, "ip": "192.168.1.70", "name": "Eleventh Flight"},
    14: {"channel": 14, "ip": "192.168.1.81", "name": "Twelfth Flight"},
    15: {"channel": 15, "ip": "192.168.1.89", "name": "Thirteenth Flight"},
    16: {"channel": 16, "ip": "192.168.1.90", "name": "Fourteenth Flight"},
    17: {"channel": 17, "ip": "192.168.1.137", "name": "Fifteenth Flight"},
    18: {"channel": 18, "ip": "192.168.1.136", "name": "Sixteenth Flight"},
    19: {"channel": 19, "ip": "192.168.1.202", "name": "Seventeenth Flight"},
    20: {"channel": 20, "ip": "192.168.1.72", "name": "Eighteenth Flight"},
    21: {"channel": 21, "ip": "192.168.1.129", "name": "Nineteenth Flight"},
    22: {"channel": 22, "ip": "192.168.1.116", "name": "Twentieth Flight"},
    23: {"channel": 23, "ip": "192.168.1.190", "name": "Twenty-first Flight"},
    24: {"channel": 24, "ip": "192.168.1.135", "name": "Twenty-second Flight"},
    25: {"channel": 25, "ip": "192.168.1.103", "name": "Twenty-third Flight"},
    26: {"channel": 26, "ip": "192.168.1.61", "name": "Twenty-fourth Flight"},
    27: {"channel": 27, "ip": "192.168.1.71", "name": "Twenty-fifth Flight"},
    28: {"channel": 28, "ip": "192.168.1.102", "name": "Twenty-sixth Flight"},
    29: {"channel": 29, "ip": "192.168.1.68", "name": "Twenty-seventh Flight"},
    30: {"channel": 30, "ip": "192.168.1.120", "name": "Twenty-eighth Flight"},
    31: {"channel": 31, "ip": "192.168.1.69", "name": "Twenty-ninth Flight"},
    32: {"channel": 32, "ip": "192.168.1.76", "name": "Thirtieth Flight"},
}

# Global variables for frame management
current_frames: Dict[int, Optional[bytes]] = {cam_id: None for cam_id in CAMERAS}
frame_locks: Dict[int, Lock] = {cam_id: Lock() for cam_id in CAMERAS}
stream_active = True

# Initialize YOLO model once to avoid loading it repeatedly
try:
    yolo_model = YOLO("yolo11n.pt")  # Using nano model for better performance
    logger.info("YOLO model loaded successfully")
except Exception as e:
    logger.error(f"Failed to load YOLO model: {e}")
    yolo_model = None

app = FastAPI(title="Multi-Camera Monitoring System", version="1.0.0")

def generate_rtsp_url(camera: dict) -> list[str]:
    """Generate possible RTSP URLs for a camera"""
    base_url = f"rtsp://{USERNAME}:{PASSWORD}@{camera['ip']}:{PORT}"
    return [
        f"{base_url}/cam/realmonitor?channel={camera['channel']}&subtype=0",  # Dahua format
        f"{base_url}/Streaming/Channels/{camera['channel']}01",  # Hikvision format
        #f"{base_url}/axis-media/media.amp?videocodec=h264&camera={camera['channel']}"  # Axis format
    ]

async def process_frame_with_yolo(frame):
    """Process frame with YOLO detection"""
    if yolo_model is None:
        return frame

    try:
        # Run YOLO inference
        results = yolo_model.predict(frame, conf=0.3, verbose=False)
        if len(results) > 0 and results[0].boxes is not None:
            # Draw bounding boxes and labels
            annotated_frame = results[0].plot()
            return annotated_frame
    except Exception as e:
        logger.error(f"YOLO processing error: {str(e)}")

    return frame

async def capture_camera_frames(cam_id: int, camera_config: dict):
    """Background task to continuously capture frames from a specific camera"""
    global current_frames, stream_active

    rtsp_urls = generate_rtsp_url(camera_config)
    cap = None
    reconnect_delay = 5
    max_reconnect_delay = 60

    logger.info(f"Starting capture task for camera {cam_id} - {camera_config['name']}")

    while stream_active:
        # Try to connect to camera
        for url in rtsp_urls:
            try:
                logger.info(f"Attempting to connect to camera {cam_id} at {url}")
                cap = cv2.VideoCapture(url)

                # Set buffer size to reduce latency
                cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                cap.set(cv2.CAP_PROP_FPS, 30)

                if cap.isOpened():
                    logger.info(f"Successfully connected to camera {cam_id}")
                    reconnect_delay = 5  # Reset delay on successful connection
                    break
                else:
                    cap.release()
                    cap = None

            except Exception as e:
                logger.error(f"Error connecting to camera {cam_id}: {str(e)}")
                if cap:
                    cap.release()
                cap = None
                continue

        if cap is None or not cap.isOpened():
            logger.warning(f"Could not connect to any RTSP URL for camera {cam_id}")
            await asyncio.sleep(reconnect_delay)
            reconnect_delay = min(reconnect_delay * 2, max_reconnect_delay)
            continue

        # Main frame capture loop
        frame_count = 0
        try:
            while stream_active and cap.isOpened():
                ret, frame = cap.read()

                if not ret:
                    logger.warning(f"Frame read failed for camera {cam_id}")
                    break

                frame_count += 1

                # Process every nth frame with YOLO to reduce CPU load
                if frame_count % 3 == 0:  # Process every 3rd frame
                    frame = await process_frame_with_yolo(frame)

                # Resize frame to reduce bandwidth
                height, width = frame.shape[:2]
                if width > 640:
                    scale = 640 / width
                    new_width = 640
                    new_height = int(height * scale)
                    frame = cv2.resize(frame, (new_width, new_height))

                # Encode frame as JPEG
                encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), 75]
                ret, buffer = cv2.imencode('.jpg', frame, encode_param)

                if ret:
                    with frame_locks[cam_id]:
                        current_frames[cam_id] = buffer.tobytes()

                # Control frame rate
                await asyncio.sleep(0.033)  # ~30 FPS

        except Exception as e:
            logger.error(f"Error in frame capture for camera {cam_id}: {str(e)}")
            logger.error(traceback.format_exc())
        finally:
            if cap:
                cap.release()
                logger.info(f"Released capture for camera {cam_id}")

        # Wait before attempting to reconnect
        if stream_active:
            logger.info(f"Attempting to reconnect to camera {cam_id} in {reconnect_delay} seconds...")
            await asyncio.sleep(reconnect_delay)

async def generate_frames(cam_id: int):
    """Generator function for streaming frames"""
    while True:
        try:
            with frame_locks[cam_id]:
                frame = current_frames[cam_id]

            if frame:
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
            else:
                # Send a placeholder image if no frame available
                placeholder = create_placeholder_frame(f"Camera {cam_id}\nConnecting...")
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + placeholder + b'\r\n')

            await asyncio.sleep(0.033)  # ~30 FPS

        except Exception as e:
            logger.error(f"Error in frame generation for camera {cam_id}: {str(e)}")
            await asyncio.sleep(1)

def create_placeholder_frame(text: str) -> bytes:
    """Create a placeholder frame with text"""
    import numpy as np

    # Create a black image
    img = np.zeros((240, 320, 3), dtype=np.uint8)

    # Add text
    font = cv2.FONT_HERSHEY_SIMPLEX
    font_scale = 0.7
    color = (255, 255, 255)
    thickness = 2

    # Split text into lines
    lines = text.split('\n')
    y_offset = 100

    for line in lines:
        text_size = cv2.getTextSize(line, font, font_scale, thickness)[0]
        x = (img.shape[1] - text_size[0]) // 2
        cv2.putText(img, line, (x, y_offset), font, font_scale, color, thickness)
        y_offset += 40

    # Encode as JPEG
    ret, buffer = cv2.imencode('.jpg', img, [cv2.IMWRITE_JPEG_QUALITY, 80])
    return buffer.tobytes() if ret else b''

@app.on_event("startup")
async def startup_event():
    """Start background tasks for all cameras on startup"""
    logger.info("Starting Multi-Camera Monitoring System")

    for cam_id, config in CAMERAS.items():
        asyncio.create_task(capture_camera_frames(cam_id, config))

    logger.info(f"Started capture tasks for {len(CAMERAS)} cameras")

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    global stream_active
    stream_active = False
    logger.info("Shutting down camera streams")

@app.get("/", response_class=HTMLResponse)
async def index():
    """Home page with all camera feeds in a responsive grid"""
    camera_html = "".join(
        f"""
        <div class="camera">
            <div class="camera-header">
                <h3>Camera {cam_id}</h3>
                <span class="camera-name">{config["name"]}</span>
                <span class="camera-ip">{config["ip"]}</span>
            </div>
            <div class="camera-stream">
                <img src="/video/{cam_id}" alt="Camera {cam_id} Stream" loading="lazy">
            </div>
        </div>
        """
        for cam_id, config in CAMERAS.items()
    )

    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Multi-Camera Monitoring System</title>
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            * {{ box-sizing: border-box; }}
            body {{
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                margin: 0;
                padding: 20px;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
            }}
            .container {{
                max-width: 95%;
                margin: 0 auto;
            }}
            h1 {{
                color: white;
                text-align: center;
                margin-bottom: 30px;
                font-size: 2.5em;
                text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
            }}
            .stats {{
                background: rgba(255,255,255,0.1);
                backdrop-filter: blur(10px);
                border-radius: 10px;
                padding: 20px;
                margin-bottom: 30px;
                text-align: center;
                color: white;
            }}
            .camera-grid {{
                display: grid;
                grid-template-columns: repeat(auto-fill, minmax(350px, 1fr));
                gap: 20px;
                margin-bottom: 20px;
            }}
            .camera {{
                background: rgba(255,255,255,0.95);
                backdrop-filter: blur(10px);
                border-radius: 12px;
                padding: 15px;
                box-shadow: 0 8px 32px rgba(0,0,0,0.1);
                transition: transform 0.3s ease, box-shadow 0.3s ease;
            }}
            .camera:hover {{
                transform: translateY(-5px);
                box-shadow: 0 12px 40px rgba(0,0,0,0.15);
            }}
            .camera-header {{
                margin-bottom: 12px;
            }}
            .camera-header h3 {{
                margin: 0;
                font-size: 18px;
                color: #333;
                font-weight: 600;
            }}
            .camera-name {{
                display: block;
                font-size: 14px;
                color: #666;
                margin-top: 4px;
            }}
            .camera-ip {{
                display: block;
                font-size: 12px;
                color: #999;
                font-family: monospace;
                margin-top: 2px;
            }}
            .camera-stream {{
                position: relative;
                overflow: hidden;
                border-radius: 8px;
            }}
            .camera img {{
                width: 100%;
                height: auto;
                max-height: 250px;
                object-fit: cover;
                border-radius: 8px;
                transition: opacity 0.3s ease;
            }}
            .camera img:hover {{
                opacity: 0.9;
            }}
            @media (max-width: 768px) {{
                .camera-grid {{
                    grid-template-columns: 1fr;
                }}
                h1 {{
                    font-size: 2em;
                }}
            }}
            @media (max-width: 480px) {{
                .container {{
                    padding: 10px;
                }}
                h1 {{
                    font-size: 1.8em;
                }}
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🎥 Multi-Camera Monitoring System</h1>
            <div class="stats">
                <h3>System Status</h3>
                <p>Monitoring {len(CAMERAS)} cameras with AI object detection</p>
                <p>Real-time YOLO inference • Auto-reconnection • 30 FPS streaming</p>
            </div>
            <div class="camera-grid">
                {camera_html}
            </div>
        </div>
    </body>
    </html>
    """

@app.get("/video/{cam_id}")
async def video_feed(cam_id: int):
    """Video streaming endpoint for individual cameras"""
    if cam_id not in CAMERAS:
        return Response("Camera not found", status_code=404)

    return StreamingResponse(
        generate_frames(cam_id),
        media_type="multipart/x-mixed-replace; boundary=frame",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0"
        }
    )

@app.get("/api/cameras")
async def get_cameras():
    """API endpoint to get camera information"""
    return {"cameras": CAMERAS, "total": len(CAMERAS)}

@app.get("/api/camera/{cam_id}")
async def get_camera_info(cam_id: int):
    """API endpoint to get specific camera information"""
    if cam_id not in CAMERAS:
        return Response("Camera not found", status_code=404)

    return {"camera": CAMERAS[cam_id], "cam_id": cam_id}

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    active_cameras = sum(1 for frame in current_frames.values() if frame is not None)
    return {
        "status": "healthy",
        "total_cameras": len(CAMERAS),
        "active_cameras": active_cameras,
        "yolo_loaded": yolo_model is not None
    }

if __name__ == "__main__":
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=5000,
        log_level="info",
        timeout_keep_alive=300,
        access_log=True
    )
