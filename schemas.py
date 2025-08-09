#!/usr/bin/env python3

import uuid
from datetime import datetime, timezone
from typing import Any, List, Optional

from pydantic import BaseModel, Field
from utils.timezone import nairobi_tz


# ---- Request/Response Schemas for /analyse ----
class AnalysisJob(BaseModel):
    job_id: str
    message: str
    status_url: str


# ---- Schemas for Webhooks and LLM Interaction ----
class LlmRequestPayload(BaseModel):
    user_message:str 
    user_number:str
    messages:list[Any]

class ConversationData(BaseModel):
    user_message: Any
    prompt_timestamp: datetime
    llm_response: str
    llm_response_timestamp: datetime
    category: str
    source: str
    interaction_timestamp: datetime = Field(
        default_factory=lambda: datetime.now(nairobi_tz)
    )
    prompt_id: uuid.UUID


# Schemas for the YOLO services
