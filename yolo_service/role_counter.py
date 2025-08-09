#!/usr/bin/env python3
import asyncio
import numpy as np
from umap import UMAP
from sklearn.cluster import KMeans
from tqdm import tqdm
from transformers import AutoImageProcessor, AutoModel
from typing import Any, Dict, List
import torch
import cv2
from collections import Counter
from sklearn.preprocessing import StandardScaler
import supervision as sv
from ultralytics import YOLO

# Models
IMAGE_EMBEDDING_MODEL = AutoModel.from_pretrained("facebook/dinov2-small")
IMAGE_EMBEDDING_PROCESSOR = AutoImageProcessor.from_pretrained("facebook/dinov2-small")
STRIDE = 30  # FPS
BATCH_SIZE = 32
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

# Clustering
REDUCER = UMAP(n_components=3)
CLUSTERING_MODEL = KMeans(n_clusters=5)  # 5 role types

# Color thresholds (HSV ranges) for uniform identification
COLOR_RANGES = {
    "maintenance": ([10, 50, 50], [20, 255, 255]),  # Brown
    "security": ([20, 100, 100], [30, 255, 255]),  # Yellow
    "kitchen": ([200, 50, 50], [220, 255, 255]),  # Light Blue
    "cleaning": ([100, 50, 50], [140, 255, 255]),  # Navy Blue
    "guest": ([0, 0, 0], [180, 255, 255]),  # Other colors
}
role_counts = {"Maintenance": 0, "Security": 0, "Kitchen": 0, "Cleaning": 0, "Guest": 0}


def extract_dominant_colors(image: np.ndarray, k: int = 3) -> List[float]:
    """Extract top-k dominant colors in HSV space"""
    pixels = image.reshape(-1, 3)
    pixels = cv2.cvtColor(pixels, cv2.COLOR_RGB2HSV)

    # Use k-means to find dominant colors
    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 200, 0.1)
    _, labels, centroids = cv2.kmeans(
        pixels.astype(np.float32), k, None, criteria, 10, cv2.KMEANS_RANDOM_CENTERS
    )

    # Get the most dominant colors
    counts = Counter(labels.flatten())
    dominant_colors = [centroids[i] for i, _ in counts.most_common(k)]
    return np.concatenate(dominant_colors)  # Flatten to 1D array


async def person_role(yolo_results: Any) -> Dict[str, int]:
    """Classify detected persons by uniform color and visual features"""
    detections = sv.Detections.from_ultralytics(yolo_results)
    detections = detections.with_nms(threshold=0.5, class_agnostic=True)

    # Process each detection
    embeddings_list = []
    color_features_list = []

    for xyxy in detections.xyxy:
        crop = sv.crop_image(yolo_results.orig_img, xyxy)

        # 1. Extract DINOv2 embeddings
        inputs = IMAGE_EMBEDDING_PROCESSOR(crop, return_tensors="pt").to(DEVICE)
        with torch.no_grad():
            outputs = IMAGE_EMBEDDING_MODEL(**inputs)
        embedding = torch.mean(outputs.last_hidden_state, dim=1).cpu().numpy().flatten()

        # 2. Extract dominant colors (focus on torso area)
        torso = crop[
            int(crop.shape[0] * 0.2) : int(crop.shape[0] * 0.8)
        ]  # Avoid head/legs
        color_features = extract_dominant_colors(torso)

        embeddings_list.append(embedding)
        color_features_list.append(color_features)

    # Combine features
    embeddings = np.array(embeddings_list)
    color_features = np.array(color_features_list)
    features = np.hstack([embeddings, color_features])

    # Normalize features
    features = StandardScaler().fit_transform(features)

    # Dimensionality reduction and clustering
    projections = REDUCER.fit_transform(features)
    clusters = CLUSTERING_MODEL.fit_predict(projections)

    # Classify clusters based on color dominance
    role_counts = {k: 0 for k in COLOR_RANGES.keys()}
    for cluster_id in np.unique(clusters):
        cluster_colors = color_features[clusters == cluster_id]
        avg_hue = np.mean(cluster_colors[:, 0])  # Average Hue value

        # Determine role type by color
        if 10 <= avg_hue <= 20:
            role_type = "maintenance"
        elif 20 <= avg_hue <= 30:
            role_type = "security"
        elif 200 <= avg_hue <= 220:
            role_type = "kitchen"
        elif 100 <= avg_hue <= 140:
            role_type = "cleaning"
        else:
            role_type = "guest"

        role_counts[role_type] += np.sum(clusters == cluster_id)

    return role_counts
"""
For testing
async def main():
    model = YOLO("yolo11l.pt")
    yolo_results = model.predict(source=0, show=True, stream=True)
    return await person_role(yolo_results=yolo_results)
if __name__=="__main__":
    asyncio.run(main())
"""