#!/usr/bin/env python3
"""Dedicated Server for web detection. Employs the YOLO model from ultralytics."""
import cv2
import numpy as np
from fastapi import FastAPI, UploadFile, File, HTTPException
from ultralytics import YOLO
from loguru import logger

# --- Model Loading ---
try:
    model = YOLO("/app/models/yolo11l.pt")
    # Perform a dummy prediction to "warm up" the model
    model.predict(np.zeros((640, 480, 3), dtype=np.uint8), verbose=False)
    logger.info("YOLO model loaded and warmed up successfully.")
except Exception as e:
    logger.error(f"Error loading YOLO model: {e}")
    raise e

app = FastAPI(title="YOLOv8 Inference Service")


@app.post("/detect")
async def detect_objects(file: UploadFile = File(...)):
    """
    Accepts an image file, performs object detection, and returns
    the detection results in JSON format.
    """
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
        results = model.predict(
            frame, conf=0.6, classes=[0], verbose=False
        )  # Detect only 'person' class

        # --- Process and Format Results ---
        # Extract the relevant data to send back.
        # We want to keep the response payload small and efficient.
        detections = []
        if len(results) > 0 and len(results[0].boxes) > 0:
            boxes = results[0].boxes
            person_detections = boxes[boxes.cls == 0]

            for box in person_detections:
                detections.append(
                    {
                        "confidence": box.conf.cpu().numpy().tolist()[0],
                        "bounding_box": box.xyxy.cpu().numpy().tolist()[0],
                    }
                )

        return {"person_count": len(detections), "detections": detections}

    except Exception as e:
        logger.error(f"Error during detection: {e}")
        raise HTTPException(
            status_code=500, detail="An error occurred during inference."
        )


@app.get("/health")
def health_check():
    return {"status": "ok"}
