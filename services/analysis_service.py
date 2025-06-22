#!/usr/bin/env python3
import json
from datetime import date, datetime, timezone

from loguru import logger
from ollama import AsyncClient
import valkey

from schemas import AnalysisRequest
from config import settings
from utils.app_tools import (
    calculate_traffic_statistics,
    generate_insights,
    create_recommendations,
)
from utils.report_format import ModernPDFGenerator
from prompts import PROMPT_REPORT_ANALYST

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
        # Prepare data for LLM analysis
        analysis_context = {
            "camera_detection_stats": await camera_stats.get_detection_counts(),
            "camera_confidence_stats": await camera_stats.get_confidence_stats(),
            "camera_movement_stats": [
                await camera_stats.get_movement_stats(camera_id=i) for i in range(32)
            ],
            "statistics": stats,
            "insights": insights,
            "recommendations": recommendations,
            "building_info": (
                request.building_stats.model_dump() if request.building_stats else None
            ),
            "data_points": len(request.traffic_data),
        }
        messages = [
            {"role": "system", "content": PROMPT_REPORT_ANALYST},
            {
                "role": "user",
                "content": f"""Analyze ANALYSIS_CONTEXT:
                    {json.dumps(analysis_context, indent=2, default=str), sql_daily_results}

                    ANALYSIS PERIOD: {request.analysis_period}
                    BUILDING TYPE: {request.building_stats.building_type if request.building_stats else "Not specified"}
                    """,
            },
        ]

        response = await gen_response(messages)
        # Extract response content
        if "message" in response and "content" in response["message"]:
            llm_report = response["message"]["content"]
        else:
            llm_report = "Unable to generate LLM analysis"

        # Compile final response
        analysis_result = {
            "executive_summary": {
                "total_traffic": stats.get("total_traffic", 0),
                "analysis_period": request.analysis_period,
                "data_points_analyzed": len(request.traffic_data),
                "building_info": (
                    request.building_stats.dict() if request.building_stats else None
                ),
            },
            "raw_statistics": stats,
            "key_insights": insights,
            "recommendations": recommendations,
            "detailed_report": clean_text_remove_think_tags(llm_report),
            "analysis_metadata": {
                "generated_at": datetime.now(timezone.utc),
                "model_used": llm_model_id,
                "include_predictions": request.include_predictions,
            },
        }
        # Generate PDF
        output_file = pdf_generator.generate_pdf(
            analysis_result, f"./utils/reports/Traffic_report_{today}.pdf"
        )
        final_status = {"status": "completed", "result": analysis_result}
        valkey_client.set(
            f"job:{job_id}", json.dumps(final_status, default=str), ex=3600
        )
        logger.info(f"Successfully completed analysis for job_id: {job_id}")

    except Exception as e:
        logger.error(f"Analysis failed for job_id: {job_id}. Error: {e}")
        error_status = {"status": "failed", "error": str(e)}
        valkey_client.set(f"job:{job_id}", json.dumps(error_status), ex=3600)
