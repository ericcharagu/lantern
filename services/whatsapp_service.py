#!/usr/bin/env python3
"""Handle whats app chatbot interactions."""
import json
from datetime import datetime, timezone
from loguru import logger
from ollama import AsyncClient

from config import settings
from utils.whatsapp.whatsapp import send_whatsapp_message
from utils.db.base import single_insert_query, MobileRequestLog
from dependencies import get_ollama_client  # If you have this pattern
from schemas import GenerationRequest  # Assuming this is the correct schema
from prompts import PROMPT_WHATSAPP_ASSISTANT


async def handle_incoming_message(payload: dict):
    """
    Process a validated message payload from the WhatsApp webhook.

    This function will:
    1. Extract relevant message details.
    2. Call the LLM for a response.
    3. Send the response back to the user via WhatsApp.
    4. Log the interaction to the database.
    """
    try:
        # 1. Extract message details
        message_info = extract_message_info(payload)
        if not message_info:
            logger.warning("Could not extract a valid text message from the payload.")
            return

        sender_id = message_info["sender_id"]
        prompt_text = message_info["prompt"]
        message_id = message_info["message_id"]

        logger.info(f"Processing message from {sender_id}: '{prompt_text}'")

        # 2. Call the LLM for a response
        messages = [
            {"role": "system", "content": PROMPT_WHATSAPP_ASSISTANT},
            {"role": "user", "content": prompt_text},
        ]

        # TODO: get the ollama_client via dependency injection in a real-world scenario,

        ollama_client = AsyncClient(host=settings.OLLAMA_HOST)
        llm_response = await ollama_client.chat(
            model=settings.LLM_MODEL_ID, messages=messages
        )
        response_text = llm_response.get("message", {}).get(
            "content", "Sorry, I encountered an error and cannot respond right now."
        )

        # 3. Send the response back to the user
        send_whatsapp_message(recipient_number=sender_id, message_text=response_text)

        # 4. Log the interaction (Example - adapt to your DB schema/function)
        log_entry = {
            "id": message_id,
            "prompt": prompt_text,
            "response": response_text,
            "status": "completed",
            "model": settings.LLM_MODEL_ID,
            # Add other relevant fields like timestamps, prompt_hash, etc.
        }
        await single_insert_query(MobileRequestLog, log_entry)

    except Exception as e:
        logger.error(f"Failed to process incoming WhatsApp message: {e}")


def extract_message_info(payload: dict) -> dict | None:
    """Helper function to safely extract message details from the complex payload."""
    try:
        changes = payload["entry"][0]["changes"][0]
        if changes["field"] != "messages":
            return None

        message_data = changes["value"]["messages"][0]
        if message_data["type"] != "text":
            return None  # We only handle text messages for now

        return {
            "sender_id": message_data["from"],
            "prompt": message_data["text"]["body"],
            "message_id": message_data["id"],
        }
    except (KeyError, IndexError):
        logger.warning("Payload structure is not as expected.")
        return None
