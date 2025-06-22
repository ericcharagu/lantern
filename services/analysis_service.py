#!/usr/bin/env python3
import json
from datetime import date, datetime, timezone

from loguru import logger
from ollama import AsyncClient
import valkey

from app.schemas import AnalysisRequest
from app.config import settings
from utils.app_tools import (
    calculate_traffic_statistics,
    generate_insights,
    create_recommendations,
)
from utils.camera_stats import CameraStats
from utils.db.stats_db import get_traffic_analytics
from utils.report_format import ModernPDFGenerator

# ... other necessary imports like SYSTEM_PROMPT (which could also be in config)

# Assume SYSTEM_PROMPT is defined here or imported from a config/constants file
SYSTEM_PROMPT = "You are a Foot Traffic Analytics Specialist..."

pdf_generator = ModernPDFGenerator()


async def gen_response(ollama_client: AsyncClient, messages: list[dict]):
    return await ollama_client.chat(
        model=settings.LLM_MODEL_ID, messages=messages, options={"temperature": 0.6}
    )


async def process_analysis_in_background(
    job_id: str,
    request: AnalysisRequest,
    valkey_client: valkey.Valkey,
    ollama_client: AsyncClient,
):
    logger.info(f"Starting background analysis for job_id: {job_id}")
    try:
        valkey_client.set(
            f"job:{job_id}",
            json.dumps(
                {
                    "status": "processing",
                    "submitted_at": datetime.now(timezone.utc).isoformat(),
                }
            ),
            ex=3600,
        )

        today = date.today()
        sql_daily_results = get_traffic_analytics(today)
        stats = calculate_traffic_statistics(sql_daily_results)
        insights = generate_insights(stats, request.building_stats)
        recommendations = create_recommendations(stats, request.building_stats)

        # ... more logic from the original function ...

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": "Analyze..."},
        ]
        response = await gen_response(ollama_client, messages)
        llm_report = response.get("message", {}).get(
            "content", "Unable to generate LLM analysis"
        )

        analysis_result = {
            "detailed_report": llm_report,
            "raw_statistics": stats,
        }  # simplified for example

        # ... generate PDF, etc. ...

        final_status = {"status": "completed", "result": analysis_result}
        valkey_client.set(
            f"job:{job_id}", json.dumps(final_status, default=str), ex=3600
        )
        logger.info(f"Successfully completed analysis for job_id: {job_id}")

    except Exception as e:
        logger.error(f"Analysis failed for job_id: {job_id}. Error: {e}")
        error_status = {"status": "failed", "error": str(e)}
        valkey_client.set(f"job:{job_id}", json.dumps(error_status), ex=3600)
