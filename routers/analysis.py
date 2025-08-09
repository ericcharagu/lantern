#!/usr/bin/env python3

import uuid
from valkey.asyncio import Valkey as AsyncValkey
from ollama import AsyncClient
from fastapi import APIRouter, Depends, BackgroundTasks, HTTPException, status
from fastapi.responses import JSONResponse

from dependencies import get_valkey_client, get_ollama_client, require_managerial_user
import json
router = APIRouter(
    prefix="/analyse",
    tags=["Analysis"],
)

@router.get("/status/{job_id}", name="get_analysis_status")
async def get_analysis_status(
    job_id: str, valkey_client: AsyncValkey = Depends(get_valkey_client)
):
    job_data = valkey_client.get(f"job:{job_id}")
    if not job_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Job ID not found."
        )
    return JSONResponse(content=json.loads(job_data))  
