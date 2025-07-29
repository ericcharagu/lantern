#!/usr/bin/env python3
from ultralytics import YOLO
from supervision.assets import download_assets, VideoAssets
import supervision as sv  # Added missing import
import asyncio
from typing import Any
import numpy as np  # Added missing import
from collections import defaultdict  # For counting in/out

# Initialize annotators
bounding_box_annotator = sv.BoundingBoxAnnotator(thickness=4)
byte_tracker = sv.ByteTrack()

# Camera line configurations
camera_line_config = [
    {"camera_id": 4, "START": sv.Point(0, 180), "END": sv.Point(190, 200)},  # Main gate
    {
        "camera_id": 15,
        "START": sv.Point(0, 180),
        "END": sv.Point(190, 200),
    },  # Reception
    {"camera_id": 26, "START": sv.Point(0, 180), "END": sv.Point(190, 200)},  # Borehole
    {
        "camera_id": 30,
        "START": sv.Point(0, 180),
        "END": sv.Point(190, 200),
    },  # Staff entrance
]

# Dictionary to store counts per camera
camera_counts = defaultdict(lambda: {"in": 0, "out": 0})


def callback(frame: np.ndarray, index: int, results: Any, model: Any) -> np.ndarray:
    listed_results = list(results)
    detections = sv.Detections.from_ultralytics(listed_results[-1])
    detections = byte_tracker.update_with_detections(detections)

    annotated_frame = frame.copy()
    annotated_frame = bounding_box_annotator.annotate(
        scene=annotated_frame, detections=detections
    )
    annotated_frame = label_annotator.annotate(
        scene=annotated_frame, detections=detections
    )

    line_zone.trigger(detections)

    # Update counts
    camera_counts[line_zone.camera_id]["in"] += line_zone.in_count
    camera_counts[line_zone.camera_id]["out"] += line_zone.out_count

    return line_zone_annotator.annotate(annotated_frame, line_counter=line_zone)


async def direction(cam_id: int, model: Any, frame: np.ndarray) -> dict:
    try:
        # Find the camera config
        line_count_config = next(
            (cfg for cfg in camera_line_config if cfg["camera_id"] == cam_id), None
        )

        if line_count_config:
            line_zone = sv.LineZone(
                start=line_count_config["START"], end=line_count_config["END"]
            )
            line_zone.camera_id = cam_id  # Store camera ID for reference

            line_zone_annotator = sv.LineZoneAnnotator(
                thickness=4, text_thickness=4, text_scale=2
            )

            results = model(frame)[0]  # Run detection
            # annotated_frame = callback(frame, 0, results, model)

            # Return current counts for this frame
            return {
                "camera_id": cam_id,
                "in_count": line_zone.in_count,
                "out_count": line_zone.out_count,
                "total_in": camera_counts[cam_id]["in"],
                "total_out": camera_counts[cam_id]["out"],
            }
        else:
            return {"error": f"No configuration found for camera {cam_id}"}

    except Exception as e:
        return {"error": f"Error processing camera {cam_id}: {str(e)}"}
