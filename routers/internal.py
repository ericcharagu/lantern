#!/usr/bin/env python3

from fastapi import APIRouter, Depends, Body, HTTPException
from pydantic import BaseModel
from typing import Annotated

from ollama import AsyncClient
from app.dependencies import (
    get_ollama_client,
    get_current_active_user,
)  # Your auth dependency
from app.prompts import PROMPT_INTERNAL_ASSISTANT
from models.user_db import User  # Import your User model for typing

router = APIRouter(
    prefix="/internal",
    tags=["Internal Assistant"],
    dependencies=[
        Depends(get_current_active_user)
    ],  # This secures all endpoints in this file
)


class SummarizationRequest(BaseModel):
    text_content: str
    query: str = "Summarize the following text and provide the key takeaways."


@router.post("/summarize")
async def process_document(
    request: SummarizationRequest,
    current_user: Annotated[
        User, Depends(get_current_active_user)
    ],  # Get user info for logging
    ollama_client: AsyncClient = Depends(get_ollama_client),
):
    """
    Takes a block of text and a query, and uses the Internal Assistant
    to provide a secure summary or answer.
    """
    if len(request.text_content) > 20000:  # Add a reasonable character limit
        raise HTTPException(status_code=413, detail="Text content is too long.")

    user_prompt = f"""
    **CONTEXT DOCUMENT:**
    ---
    {request.text_content}
    ---

    **STAFF QUERY:**
    {request.query}
    """

    messages = [
        {"role": "system", "content": PROMPT_INTERNAL_ASSISTANT},
        {"role": "user", "content": user_prompt},
    ]

    # In a real app, you would log that 'current_user.username' made this request
    response = await ollama_client.chat(model="qwen3:0.6b", messages=messages)

    return {
        "user": current_user.username,
        "query": request.query,
        "response": response["message"]["content"],
    }
