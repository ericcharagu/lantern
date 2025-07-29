# utils/routers/webhooks.py
from datetime import datetime, timezone
import hashlib
import hmac
import os
from typing import Any, Optional
import uuid

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse
import httpx
from loguru import logger
from schemas import GenerationRequest, LlmRequestPayload
from services.analysis_service import gen_response
from utils.text_processing import convert_llm_output_to_readable
from utils.whatsapp.whatsapp import whatsapp_messenger

# Add logging path
logger.add("./logs/webhooks.log", rotation="1 week")
router = APIRouter(
    prefix="/webhooks",
    tags=["Webhooks"],
)

# Ensure media directory exists
os.makedirs("media_files", exist_ok=True)

# Load secrets securely from environment variables
VERIFY_TOKEN = os.getenv("WHATSAPP_VERIFY_TOKEN")
with open(file="/app/secrets/whatsapp_secrets.txt", mode="r") as f:
    APP_SECRET = f.read().strip()


def verify_signature(payload: bytes, signature: str) -> bool:
    """Verify the X-Hub-Signature-256 header matches the payload signature."""
    if not APP_SECRET:
        # If no secret is configured, skip verification (useful for dev)
        return True

    expected_signature = hmac.new(
        key=APP_SECRET.encode("utf-8"), msg=payload, digestmod=hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(expected_signature, signature)


async def process_message_in_background(
    request: Request,
    user_message: str,
    user_number: str,
 
):
    """This function runs in the background to process and respond to messages."""
    logger.info(f"Background task started for user {user_number}.")
    try:

        llm_messages=[{"role": "user","content":user_message }]
        llm_response = await gen_response(messages=llm_messages)
        logger.info(llm_response)
        if not llm_response or "message" not in llm_response:
            logger.error(f"Received invalid or None response from LLM pipeline for user {user_number}.")
            # Send a generic error message
            whatsapp_messenger(
                llm_text_output="I'm sorry, I'm having trouble processing your request right now. Please try again in a moment.",
                recipient_number=user_number
            )
            return
        content: str = llm_response.get("message", {}).get("content", "")
        if not content:
             logger.warning(f"LLM returned empty content for user {user_number}. Sending fallback.")
             content = "I'm not sure how to respond to that. Could you please rephrase your request?"
        cleaned_response = convert_llm_output_to_readable(content)
        whatsapp_messenger(
            llm_text_output=cleaned_response, recipient_number=user_number
        )
        logger.success(f"Response {cleaned_response} sent to {user_number}.")
    except ValueError as e:
        logger.error(f"Background task failed for {user_number}: {e}", exc_info=True)


@router.get("")
async def verify_whatsapp_webhook(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_verify_token: str = Query(None, alias="hub.verify_token"),
    hub_challenge: str = Query(None, alias="hub.challenge"),
):
    """Handles webhook verification for the WhatsApp platform."""
    if hub_mode == "subscribe" and hub_verify_token == VERIFY_TOKEN:
        return PlainTextResponse(content=hub_challenge, status_code=200)
    raise HTTPException(status_code=403, detail="Verification failed")


@router.post("")
async def handle_whatsapp_message(request: Request, background_tasks: BackgroundTasks):
    """Handles incoming messages from WhatsApp."""
    # signature = (
    #     request.headers.get("x-hub-signature-256", "").split("sha256=")[-1].strip()
    # )
    # if not verify_signature(await request.body(), signature):
    #     raise HTTPException(status_code=403, detail="Invalid signature")

    try:
        data = await request.json()
        if not data.get("entry"):
            raise HTTPException(status_code=400, detail="Invalid payload structure")
        value = data["entry"][0]["changes"][0].get("value", {})
        if not value:
            return PlainTextResponse("OK")

        user_message: str = ""
        media_id: str = ""
        user_number: str = ""
        image_caption: str = ""
        for entry in data.get("entry", []):
            for change in entry.get("changes", []):
                contact_info = change.get("value", {}).get("contacts", [])
                if contact_info:
                    user_number = contact_info[0].get("wa_id")
                messages = change.get("value", {}).get("messages", [])
                if messages and messages[0].get("type") == "text":
                    user_message = messages[0].get("text", {}).get("body")
                    break
            if user_message or media_id:
                break

        if not (user_message or media_id):
            logger.info("Webhook received, but no processable text message found.")
            return PlainTextResponse("No text message found", status_code=200)

        # Queue the processing and response to happen in the background
        background_tasks.add_task(
            process_message_in_background,
            request,
            user_message,
            user_number,
        )

        logger.info(
            f"Webhook from {user_number} acknowledged and queued for processing."
        )
        return PlainTextResponse("Message processed", status_code=200)

    except ValueError as e:
        logger.error(f"Error processing request {e}")
        raise HTTPException(
            status_code=500, detail=f"Error processing request: {str(e)}"
        )