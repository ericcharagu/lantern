#!/usr/bin/env python3

import uuid
import valkey
from ollama import AsyncClient
from fastapi import APIRouter, Depends, BackgroundTasks, HTTPException, status
from fastapi.responses import JSONResponse

from schemas import AnalysisRequest, AnalysisJob
from dependencies import get_valkey_client, get_ollama_client
from services.analysis_service import process_analysis_in_background

router = APIRouter(
    prefix="/analyse",
    tags=["Analysis"],
)


@router.post("", response_model=AnalysisJob, status_code=status.HTTP_202_ACCEPTED)
async def start_analysis(
    request: AnalysisRequest,
    background_tasks: BackgroundTasks,
    valkey_client: valkey.Valkey = Depends(get_valkey_client),
    ollama_client: AsyncClient = Depends(get_ollama_client),
):
    job_id = str(uuid.uuid4())
    background_tasks.add_task(
        process_analysis_in_background, job_id, request, valkey_client, ollama_client
    )
    return {
        "job_id": job_id,
        "message": "Analysis request accepted.",
        "status_url": router.url_path_for("get_analysis_status", job_id=job_id),
    }


@router.get("/status/{job_id}", name="get_analysis_status")
async def get_analysis_status(
    job_id: str, valkey_client: valkey.Valkey = Depends(get_valkey_client)
):
    job_data = valkey_client.get(f"job:{job_id}")
    if not job_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Job ID not found."
        )
    return JSONResponse(content=json.loads(job_data))
