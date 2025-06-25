#!/usr/bin/env python3

import numpy as np
import supervision as sv

from ultralytics import YOLO
from supervision.assets import download_assets, VideoAssets
import asyncio
from typing import Any

#Declaring function variables
bounding_box_annotator = sv.BoundingBoxAnnotator(thickness=4)
annotated_frame = bounding_box_annotator.annotate(frame.copy(), detections)

#Get line positions for each camera used.
#TODO:Implement the relationship in the sql database. If required
camera_line_config=[{"camera_id":4, "START":sv.point(0, 180), "END":sv.point(190, 200)}, #Main gate
                    {"camera_id":15, "START":sv.point(0, 180), "END":sv.point(190, 200)}, #Reception Area
                    {"camera_id":26, "START":sv.point(0, 180), "END":sv.point(190, 200)}, #Borehole Area: Deliverires
                    {"camera_id":30, "START":sv.point(0, 180), "END":sv.point(190, 200)}  #Staff entrance
                    ]

def callback(frame: np.ndarray, index:int,results:list, model:Any) -> np.ndarray:
    detections = sv.Detections.from_ultralytics(results)
    detections = byte_tracker.update_with_detections(detections)

    labels = [
        f"#{tracker_id} {model.model.names[class_id]} {confidence:0.2f}"
        for confidence, class_id, tracker_id
        in zip(detections.confidence, detections.class_id, detections.tracker_id)
    ]

    annotated_frame = frame.copy()

    annotated_frame = bounding_box_annotator.annotate(
        scene=annotated_frame,
        detections=detections)


    line_zone.trigger(detections)

    return  line_zone_annotator.annotate(annotated_frame, line_counter=line_zone)
async def direction(cam_id:int, model:Any, frame):
    try:
        annotated_frame = frame.copy()
        annotated_frame = bounding_box_annotator.annotate(annotated_frame, detections)
        #annotated_frame = label_annotator.annotate(annotated_frame, detections, labels)

        line_count_config=next(filter(y:lambda y["camera_id"]=cam_id, camera_line_config), None)

        #Get the camera specific line cordinates
        if line_count_config != None:
            START=line_count_config.get("START")
            END=line_count_config.get("END")
            line_zone = sv.LineZone(start=START, end=END)

            line_zone_annotator = sv.LineZoneAnnotator(
                thickness=4,
                text_thickness=4,
                text_scale=2)

            annotated_frame = frame.copy()
            annotated_frame = line_zone_annotator.annotate(annotated_frame, line_counter=line_zone)
            return sv.process_video(
                source_path = SOURCE_VIDEO_PATH,
                target_path = TARGET_VIDEO_PATH,
                callback=callback
            )

        else:
            pass
    except ValueError as e:
        logger.debug(f"Error counting objects crossing the line {e}")
