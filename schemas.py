#!/usr/bin/env python3

import uuid
from datetime import datetime, timezone
from typing import Any, List, Optional

from pydantic import BaseModel, Field


# ---- Request/Response Schemas for /analyse ----
class FootTrafficData(BaseModel):
    timestamp: str
    camera_name: str
    count: int
    location: Optional[str] = None
    weather: Optional[str] = None
    temperature: Optional[float] = None
    day_of_week: Optional[str] = None
    is_holiday: Optional[bool] = None


class BuildingStats(BaseModel):
    building_id: str
    building_name: str
    total_area_sqft: Optional[float] = None
    floors: Optional[int] = None
    capacity: Optional[int] = None
    building_type: Optional[str] = None
    operating_hours: Optional[str] = None


class AnalysisRequest(BaseModel):
    traffic_data: List[FootTrafficData]
    building_stats: Optional[BuildingStats] = None
    analysis_period: Optional[str] = "daily"
    include_predictions: bool = False


class AnalysisJob(BaseModel):
    job_id: str
    message: str
    status_url: str


# ---- Schemas for Webhooks and LLM Interaction ----
class GenerationRequest(BaseModel):
    prompt: str
    prompt_timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    sender_profile_id: str
    prompt_id: str


class ConversationData(BaseModel):
    user_message: Any
    prompt_timestamp: datetime
    llm_response: str
    llm_response_timestamp: datetime
    category: str
    source: str
    interaction_timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    prompt_id: uuid.UUID


# Schemas for the YOLO services
