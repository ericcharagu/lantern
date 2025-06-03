import cv2
from flask import Flask, Response
from ultralytics import YOLO
import threading
import time
import socket

# RTSP Configuration
username = "admin"
password = "Lantern@2030"
ip_address = "192.168.1."
port = 554
# Try different RTSP URL formats for your camera
rtsp_urls = [
    f"rtsp://{username}:{password}@{ip_address}:{port}/cam/realmonitor?channel=30&subtype=0",
    # f"rtsp://{username}:{password}@{ip_address}:{port}/cam/realmonitor?channel=channel&subtype=0",
    # f"rtsp://{username}:{password}@{ip_address}:{port}/h264Preview_01_main",
    # f"rtsp://{username}:{password}@{ip_address}:{port}/h264Preview_01_sub",
    # f"rtsp://{username}:{password}@{ip_address}:{port}/live/ch00_0",
    # f"rtsp://{username}:{password}@{ip_address}:{port}/live/main",
    # f"rtsp://{username}:{password}@{ip_address}:{port}/stream1",
    # f"rtsp://{username}:{password}@{ip_address}:{port}/stream2",
]


def test_network_connection():
    """Test if the camera IP is reachable"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        result = sock.connect_ex((ip_address, port))
        sock.close()
        return result == 0
    except Exception as e:
        print(f"Network test error: {e}")
        return False


def find_working_rtsp_url():
    """Try different RTSP URL formats to find one that works"""
    if not test_network_connection():
        print(f"ERROR: Cannot reach camera at {ip_address}:{port}")
        print("Please check:")
        print("1. Camera IP address and port")
        print("2. Network connectivity")
        print("3. Camera is powered on")
        return None

    print(f"Camera is reachable at {ip_address}:{port}")
    print("Testing RTSP URL formats...")

    for i, url in enumerate(rtsp_urls):
        print(f"Testing URL {i + 1}/{len(rtsp_urls)}: {url}")
        cap = cv2.VideoCapture(url)

        # Set connection parameters
        cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 10000)  # 10 second timeout
        cap.set(cv2.CAP_PROP_READ_TIMEOUT_MSEC, 10000)  # 10 second read timeout
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

        if cap.isOpened():
            # Try to read a frame to confirm it works
            success, frame = cap.read()
            cap.release()
            if success and frame is not None:
                print(f"✓ SUCCESS: Found working URL: {url}")
                return url
            else:
                print(f"✗ URL opens but cannot read frames: {url}")
        else:
            print(f"✗ Cannot open URL: {url}")

    print("ERROR: No working RTSP URL found!")
    return None


app = Flask(__name__)

# Global variables for frame management
current_frame = None
frame_lock = threading.Lock()


def capture_frames():
    """Background thread to continuously capture frames from RTSP stream"""
    global current_frame

    # Find a working RTSP URL
    working_url = find_working_rtsp_url()
    if not working_url:
        print("FATAL: No working RTSP URL found. Exiting capture thread.")
        return

    reconnect_attempts = 0
    max_reconnect_attempts = 5

    while reconnect_attempts < max_reconnect_attempts:
        print(f"Connecting to RTSP stream... (Attempt {reconnect_attempts + 1})")

        cap = cv2.VideoCapture(working_url)

        # Set OpenCV parameters for better RTSP handling
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # Minimize buffer
        cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 15000)  # 15 second connection timeout
        cap.set(cv2.CAP_PROP_READ_TIMEOUT_MSEC, 15000)  # 15 second read timeout
        cap.set(cv2.CAP_PROP_FPS, 15)  # Request 15 FPS
        cap.set(
            cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc("H", "2", "6", "4")
        )  # Force H264

        if not cap.isOpened():
            print(f"Error: Could not open RTSP stream: {working_url}")
            reconnect_attempts += 1
            time.sleep(5)
            continue

        print("✓ Successfully connected to RTSP stream")
        reconnect_attempts = 0  # Reset on successful connection

        consecutive_failures = 0
        max_consecutive_failures = 30  # Allow some frame drops

        while True:
            success, frame = cap.read()

            if not success or frame is None:
                consecutive_failures += 1
                print(
                    f"Frame read failed ({consecutive_failures}/{max_consecutive_failures})"
                )

                if consecutive_failures >= max_consecutive_failures:
                    print("Too many consecutive frame failures. Reconnecting...")
                    break

                time.sleep(0.1)  # Short delay before retry
                continue

            # Successfully read frame
            consecutive_failures = 0

            # Basic frame validation
            if frame.shape[0] < 50 or frame.shape[1] < 50:
                print("Warning: Frame too small, skipping...")
                continue

            with frame_lock:
                current_frame = frame.copy()

            time.sleep(0.033)  # ~30 FPS cap

        cap.release()
        reconnect_attempts += 1
        if reconnect_attempts < max_reconnect_attempts:
            print(
                f"Reconnecting in 5 seconds... ({reconnect_attempts}/{max_reconnect_attempts})"
            )
            time.sleep(5)

    print("FATAL: Max reconnection attempts reached. Stopping capture thread.")


def generate_frames():
    """Generator function for Flask streaming"""
    global current_frame

    # Load YOLO model
    try:
        model = YOLO("yolo11l.pt")  # Using nano model for faster inference
        print("YOLO model loaded successfully")
    except Exception as e:
        print(f"Error loading YOLO model: {e}")
        return

    while True:
        with frame_lock:
            if current_frame is None:
                continue
            frame = current_frame.copy()

        try:
            # Make predictions
            results = model.predict(frame, conf=0.3, verbose=False)

            # Draw results on frame
            if len(results) > 0:
                frame = results[0].plot()

            # Encode frame as JPEG
            success, buffer = cv2.imencode(
                ".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 80]
            )
            if not success:
                continue

            frame_bytes = buffer.tobytes()

            yield (
                b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + frame_bytes + b"\r\n"
            )

        except Exception as e:
            print(f"Error in frame processing: {e}")
            continue


@app.route("/")
def index():
    """Home page with video feed"""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Lantern Service Apartments Stream</title>
        <style>
            body { 
                font-family: Arial, sans-serif; 
                text-align: center; 
                background-color: #f0f0f0;
                margin: 0;
                padding: 20px;
            }
            .container {
                max-width: 1200px;
                margin: 0 auto;
                background-color: white;
                padding: 20px;
                border-radius: 10px;
                box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
            }
            h1 { color: #333; }
            img { 
                max-width: 100%; 
                height: auto; 
                border: 2px solid #333;
                border-radius: 5px;
            }
            .info {
                margin-top: 20px;
                padding: 10px;
                background-color: #e7f3ff;
                border-radius: 5px;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>RTSP YOLO Object Detection Stream</h1>
            <img src="/video" alt="RTSP Stream with YOLO Detection">
            <div class="info">
                <p><strong>Stream Source:</strong> RTSP Camera</p>
                <p><strong>Detection Model:</strong> YOLO11</p>
                <p><strong>Confidence Threshold:</strong> 30%</p>
            </div>
        </div>
    </body>
    </html>
    """


@app.route("/video")
def video():
    """Video streaming route"""
    return Response(
        generate_frames(), mimetype="multipart/x-mixed-replace; boundary=frame"
    )


@app.route("/status")
def status():
    """Status endpoint to check if stream is working"""
    global current_frame
    with frame_lock:
        if current_frame is not None:
            return {"status": "streaming", "message": "RTSP stream is active"}
        else:
            return {"status": "error", "message": "No frames available"}


if __name__ == "__main__":
    print("=" * 60)
    print("Maitho Application")
    print("=" * 60)

    # Test network connectivity first
    print("Step 1: Testing network connectivity...")
    if not test_network_connection():
        print("FATAL ERROR: Cannot reach camera!")
        print("\nTroubleshooting steps:")
        print("1. Ping the camera IP: ping", ip_address)
        print("2. Check if camera web interface works: http://{}".format(ip_address))
        print("3. Verify camera is powered on and network connected")
        print("4. Check firewall settings")
        exit(1)

    print("Step 2: Finding working RTSP URL...")
    working_url = find_working_rtsp_url()
    if not working_url:
        print("FATAL ERROR: No working RTSP URL found!")
        print("\nTroubleshooting steps:")
        print("1. Check camera documentation for correct RTSP path")
        print("2. Verify username and password are correct")
        print("3. Try accessing RTSP stream with VLC media player")
        print("4. Check if RTSP is enabled on camera")
        exit(1)

    print("Step 3: Starting capture thread...")
    # Start the frame capture thread
    capture_thread = threading.Thread(target=capture_frames, daemon=True)
    capture_thread.start()

    print("Step 4: Starting Flask web server...")
    print(f"Working RTSP URL: {working_url}")
    print("Access the stream at: http://localhost:5000")
    print("Direct video feed: http://localhost:5000/video")
    print("Status check: http://localhost:5000/status")
    print("=" * 60)

    # Give the capture thread time to initialize
    print("Waiting for first frames...")
    time.sleep(5)

    try:
        app.run(debug=True, threaded=True, host="0.0.0.0", port=5000)
    except KeyboardInterrupt:
        print("\nShutting down application...")
    except Exception as e:
        print(f"Flask error: {e}")
