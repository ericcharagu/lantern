#!/usr/bin/env python3
import numpy as np
import umap
from sklearn.cluster import KMeans
from tqdm import tqdm
from transformers import AutoImageProcessor, AutoModel
from typing import Any
import torch

IMAGE_EMBEDDING_MODEL = AutoModel.from_pretrained("facebook/dinov2-small")
IMAGE_EMBEDDING_PROCESSOR = AutoImageProcessor.from_pretrained("facebook/dinov2-small")
STRIDE = 30  # FPS
BATCH_SIZE = 32
# K-Means clustering
REDUCER = umap.UMAP(n_components=3)

# Number of clusters depends on the numbe of visitor types: Maintenance, Kitchen , Security ,Cleaning, General Visitors(Based on the color coded scheme of their clothes)
CLUSTERING_MODEL = KMeans(n_clusters=5)
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
# global vairables
crops = []
data = []


async def count_staff_detected(yolo_results: Any):
    """Check if the person detected matches the color schemes of the staff."""
    detections = sv.Detections.from_ultralytics(yolo_results)
    detections = detections.with_nms(threshold=0.5, class_agnostic=True)
    # print(detections.class_id) # Keep this line for debugging if needed

    person_crops = [sv.crop_image(frame, xyxy) for xyxy in detections.xyxy]
    crops.extend(
        [np.array(crop) for crop in person_crops]
    )  # Ensure crops are numpy arrays

    # sv.plot_images_grid(crops[:10], grid_size=(10, 10)) Test the varierty of people detected

    # The EMBEDDINGS_PROCESSOR can handle numpy arrays directly, so no conversion to Pillow is needed here.
    batches = chunked(crops, BATCH_SIZE)
    EMBEDDINGS_MODEL.to(DEVICE)
    with torch.no_grad():
        for batch in tqdm(batches, desc="embedding extraction"):
            # EMBEDDINGS_PROCESSOR can handle a list of numpy arrays
            inputs = IMAGE_EMBEDDINGS_PROCESSOR(images=batch, return_tensors="pt").to(
                DEVICE
            )
            outputs = IMAGE_EMBEDDINGS_MODEL(**inputs)
            embeddings = torch.mean(outputs.last_hidden_state, dim=1).cpu().numpy()
            data.append(embeddings)

    data = np.concatenate(data)

    projections = REDUCER.fit_transform(data)
    clusters = CLUSTERING_MODEL.fit_predict(projections)
