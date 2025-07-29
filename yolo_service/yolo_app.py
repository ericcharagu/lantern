#!/usr/bin/env python3
"""Dedicated Server for web detection. Employs the YOLO model from ultralytics."""
import cv2
import numpy as np
from fastapi import FastAPI, UploadFile, File, HTTPException
from ultralytics import YOLO
from loguru import logger
import supervision as sv

# from role_counter import person_role

# Add logging for the YOLO server
logger.add("./logs/yolo_app.log", rotation="1 week")
# --- Model Loading ---
try:
    model = YOLO("/app/models/yolo11l.pt")
    # Perform a dummy prediction to "warm up" the model
    model.predict(np.zeros((640, 480, 3), dtype=np.uint8), verbose=False)
    logger.info("YOLO model loaded and warmed up successfully.")
except Exception as e:
    logger.error(f"Error loading YOLO model: {e}")
    raise e

app = FastAPI(title="Yolo11 inference")


@app.post("/detect")
@logger.catch()
async def detect_objects(file: UploadFile = File(...)):
    """Accept an image file, performs object detection, and returns the detection results in JSON format."""
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File provided is not an image.")

    try:
        # Read the image file bytes
        contents = await file.read()
        # Convert bytes to a numpy array
        np_arr = np.frombuffer(contents, np.uint8)
        # Decode the numpy array into an image
        frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

        if frame is None:
            raise HTTPException(status_code=400, detail="Could not decode image.")

        # Perform inference
        detection_results = model.predict(
            frame, conf=0.6, verbose=False, classes=[0, 1, 2, 3], stream=True
        )  # Detect person, bicycle, motorbike, car
        # Generating the annotated image/frame to be sent back
        # Assuming clusters correspond to role types based on color
        return {
            "detections": [result.to_json() for result in detection_results],
        }

    except Exception as e:
        logger.error(f"Error during detection: {e}")
        raise HTTPException(
            status_code=500, detail="An error occurred during inference."
        )


@app.get("/health")
def health_check():
    """Check the health of the service."""
    return {"status": "ok"}
