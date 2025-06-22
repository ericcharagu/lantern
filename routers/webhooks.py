#!/usr/bin/env python3

import uuid
import valkey
from ollama import AsyncClient
from fastapi import (
    APIRouter,
    Depends,
    BackgroundTasks,
    HTTPException,
    status,
    Request,
    Query,
)
from fastapi.responses import JSONResponse
from typing import Optional
from schemas import AnalysisRequest, AnalysisJob
from dependencies import get_valkey_client, get_ollama_client
from services.analysis_service import process_analysis_in_background

router = APIRouter(
    prefix="/webhooks",
    tags=["WhatsApp webhooks"],
)


@router.post("/webhooks", name="recieve_whatsapp_request")
async def process_whatsapp_request(request: Request):

    try:
        # Get JSON data from request
        data = await request.json()

        if not data:
            raise HTTPException(status_code=400, detail="Empty payload")

        print("Received data:", data)  # For debugging

        # Extract message information and return as dict
        entries = data.get("entry", [])
        test_message = {
            "prompt": "",
            "prompt_timestamp": datetime.now(timezone.utc),
        }

        for entry in entries:
            changes = entry.get("changes", [])
            for change in changes:
                value = change.get("value", {})
                messages = value.get("messages", [])

                for message in messages:
                    if message.get("type") == "text":
                        message_info = {
                            "sender_profile_id": message.get("from"),
                            "prompt": message.get("text").get("body", " "),
                            "message_id": message.get("id"),
                            "prompt_timestamp": message.get("timestamp"),
                        }
                        test_message.update(message_info)
        mobile_request = GenerationRequest(**test_message)
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": mobile_request.prompt},
        ]
        # Generate request to ollama client with unique request ID to avoid reprocessing
        response_json = await process_request(
            mobile_request=mobile_request, messages=messages
        )
        whatsapp_messenger(response_json.get("response", "No response generated"))
        # Log the interaction
        await single_insert_query(MobileRequestLog, response_json)

    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")
    except ValueError as e:
        print(f"Error processing request: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/webhooks", name="verify_whatsapp_request")
async def verify_whatsapp_request(
    hub_mode: Optional[str] = Query(None, alias="hub.mode"),
    hub_verify_token: Optional[str] = Query(None, alias="hub.verify_token"),
    hub_challenge: Optional[str] = Query(None, alias="hub.challenge"),
):
    if hub_mode and hub_verify_token:
        if hub_mode == "subscribe" and hub_verify_token == WHATSAPP_VERIFCATION_TOKEN:
            return PlainTextResponse(content=hub_challenge, status_code=200)
        else:
            raise HTTPException(status_code=403, detail="Verification failed")
    else:
        raise HTTPException(status_code=400, detail="Missing parameters")
