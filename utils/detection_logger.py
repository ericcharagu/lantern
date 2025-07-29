# utils/detection_logger.py
from loguru import logger
import json
from datetime import datetime, timezone

# Configure a specific logger for detections that rotates daily.
# The filename will automatically include the date.
logger.add(
    "logs/detections/{time:YYYY-MM-DD}.log",
    rotation="00:00",  # New file at midnight
    compression="zip",
    format="{message}",
    level="INFO",
    enqueue=True, # Make it thread-safe and asynchronous
    serialize=False # We are writing json strings ourselves
)
# Create a specific logger instance to avoid conflicts.
detection_logger = logger.bind(name="detection_logger")


def log_human_detection(camera_name: str, location: str, yolo_response: dict):
    """
    Parses a YOLO response from the detection service, counts the number of 'person'
    detections, and logs the result to a daily file if any are found.
    """
    try:
        now = datetime.now(timezone.utc)
        human_count = 0
        
        detection_json_strings = yolo_response.get("detections", [])

        if not detection_json_strings:
            return  # No detections in the response

        # Each item in detection_json_strings is a JSON string representing a list of detections for a frame.
        for result_str in detection_json_strings:
            detections_list = json.loads(result_str)
            for detection in detections_list:
                if detection.get("name") == "person":
                    human_count += 1
        
        if human_count > 0:
            log_entry = {
                "timestamp": now.isoformat(),
                "camera_name": camera_name,
                "location": location,
                "human_count": human_count,
            }
            # Log the JSON string to the dedicated detection log file.
            detection_logger.info(json.dumps(log_entry))

    except json.JSONDecodeError as e:
        from loguru import logger as main_logger
        main_logger.error(f"Error decoding YOLO JSON response: {e}. Response: {yolo_response}")
    except Exception as e:
        from loguru import logger as main_logger
        main_logger.error(f"An unexpected error occurred in log_human_detection: {e}")