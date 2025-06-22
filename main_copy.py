import asyncio
import json
import re
import uuid
from datetime import date, datetime, timezone
from typing import Any, List, Optional, Dict

from utils.db.base import MobileRequestLog, single_insert_query
import valkey
from dotenv import load_dotenv
from fastapi import BackgroundTasks, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from loguru import logger
from ollama import AsyncClient
from pydantic import BaseModel, Field
from concurrent.futures import ProcessPoolExecutor
from contextlib import asynccontextmanager
from routers import auth, cameras
from routers.cameras import (
    detection_processor,
    capture_camera_frames,
    CAMERAS,
    MAX_WORKERS,
    BATCH_SIZE,
)
from utils.app_tools import (
    calculate_traffic_statistics,
    create_recommendations,
    generate_insights,
)
from utils.camera_stats import CameraStats
from utils.db.stats_db import get_traffic_analytics
from utils.report_format import ModernPDFGenerator
from utils.whatsapp.whatsapp import whatsapp_messenger
import os

# Getting the current date
today = date.today()
target_date = datetime(today.year, today.month, today.day)

# load the current environment
load_dotenv()

# Create PDF generator object
pdf_generator = ModernPDFGenerator()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Combined lifespan management for ML models and camera processing"""
    global process_pool, stream_active

    # STARTUP - Load ML models and start background tasks
    logger.info("Starting application...")

    # Initialize process pool for YOLO processing
    process_pool = ProcessPoolExecutor(max_workers=MAX_WORKERS)
    logger.info(f"Process pool initialized with {MAX_WORKERS} workers")

    # Start detection processor
    asyncio.create_task(cameras.detection_processor())
    # Application is ready
    yield

    # SHUTDOWN - Clean up resources
    logger.info("Shutting down application...")

    # Stop camera streams
    stream_active = False

    # Shutdown process pool
    if process_pool:
        process_pool.shutdown(wait=True)
        logger.info("Process pool shut down")

    logger.info("Application shutdown complete")


app = FastAPI(title="Foot Traffic Analytics API", lifespan=lifespan)
llm_model_id: str = "qwen3:0.6b"
# Main file logging
logger.add("./logs/main_app.log", rotation="700 MB")
# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# Add middleware

# app.middleware("http")(auth_middleware)

# Include routers
app.include_router(auth.router)
app.include_router(cameras.router)
# Mount static files
app.mount("/static", StaticFiles(directory="./static"), name="static")


# Simple HTML form for testing the API
templates = Jinja2Templates(directory="templates")


# Define request models
class GenerationRequest(BaseModel):
    prompt: str
    prompt_timestamp: datetime = datetime.now(timezone.utc)
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


# Ollama client for LLM analysis
ollama_client = AsyncClient(host="http://ollama:11434")

# Valkey DB for fast data caching and request verification
valkey_client = valkey.Valkey(host="valkey", port=6379, db=0, decode_responses=True)


class FootTrafficData(BaseModel):
    """Model for foot traffic data input"""

    timestamp: str
    camera_name: str
    count: int
    location: Optional[str] = None  # indoor/outdoor
    weather: Optional[str] = None
    temperature: Optional[float] = None
    day_of_week: Optional[str] = None
    is_holiday: Optional[bool] = None


class BuildingStats(BaseModel):
    """Model for building statistics"""

    building_id: str
    building_name: str
    total_area_sqft: Optional[float] = None
    floors: Optional[int] = None
    capacity: Optional[int] = None
    building_type: Optional[str] = None  # office, retail, residential, mixed
    operating_hours: Optional[str] = None


class AnalysisRequest(BaseModel):
    """Model for analysis request"""

    traffic_data: List[FootTrafficData]
    building_stats: Optional[BuildingStats] = None
    analysis_period: Optional[str] = "daily"  # daily, weekly, monthly
    include_predictions: bool = False


SYSTEM_PROMPT = """You are a Foot Traffic Analytics Specialist for commercial real estate. Your task is to analyze provided foot traffic data and building statistics to generate actionable business intelligence. 

Key Responsibilitivide data-driven recommendations for service improvements

Analysis Framework:
- Visitor Experience: Evaluate dwell times, peak congestion, amenity usage
- Operational Efficiency: Assess staffing levels, cleaning schedules, energy usage
- Safety Compliance: Monitor density metrics, emergency egress capacity
- Revenue Optimization: Suggest space utilization improvements

Deliverables Must Be in prose form but allowed usage of bullet points:
1. Executive Summary Paragraph (max 2)
2. Trend Analysis with Visual Descriptions
3. Priority Recommendations (categorized by impact/effort)
4. Risk Assessment (safety/capacity concerns)

Tone: Professional yet accessible for mixed audiences (technical ops staff + executive leadership)
"""


# Get LLM analysis
async def gen_response(messages: list[dict]):
    return await ollama_client.chat(
        model=llm_model_id,
        messages=messages,
        options={
            "top_p": 0.95,
            "top_k": 20,
            "min_p": 0,
            "temperature": 0.6,
            # "max_tokens": 1000,
        },
    )


async def process_request(
    mobile_request: GenerationRequest, messages: List
) -> Dict[str, Any]:
    """
    Process a mobile request with request ID, timestamp, and deduplication.

    Args:
        mobile_request: Dictionary containing 'prompt' and 'prompt_timestamp'

    Returns:
        Dictionary with response and metadata
    """
    # Generate unique request ID
    request_id = str(uuid.uuid4())
    timestamp = datetime.now(timezone.utc)

    # Create request payload
    request_payload = {
        "request_id": request_id,
        "client_timestamp": mobile_request.prompt_timestamp,
        "server_timestamp": timestamp,
        "prompt": mobile_request.prompt,
        "status": "received",
    }

    # Check for duplicate request using prompt content hash as key
    prompt_hash = str(hash(mobile_request.prompt))
    cached_response = valkey_client.get(f"request:{prompt_hash}")

    if cached_response:
        # Return cached response
        response = json.loads(cached_response)
        response["status"] = "served_from_cache"
        return response

    # Store request in cache with processing status
    request_payload["status"] = "processing"
    valkey_client.setex(
        f"request:{prompt_hash}",
        3600,  # 1 hour TTL
        json.dumps(request_payload),
    )

    try:
        # Process with Ollama
        ollama_response = await gen_response(messages)

        # Prepare complete response
        response = {
            "request_id": request_id,
            "client_timestamp": mobile_request.prompt_timestamp,
            "server_timestamp": timestamp,
            "prompt": mobile_request.prompt,
            "response": ollama_response.get("message", {}).get("content", ""),
            "status": "completed",
            "metrics": {"response_time": ollama_response.get("total_duration", 0)},
        }

        # Update cache with full response
        valkey_client.setex(
            f"request:{prompt_hash}",
            3600,  # 1 hour TTL
            json.dumps(response),
        )

        return response

    except Exception as e:
        # Update with error status
        error_response = {
            "request_id": request_id,
            "client_timestamp": mobile_request.prompt_timestamp,
            "server_timestamp": timestamp,
            "prompt": mobile_request.prompt,
            "status": "error",
            "error": str(e),
        }

        valkey_client.setex(
            f"request:{prompt_hash}",
            600,  # 10 minutes TTL for errors
            json.dumps(error_response),
        )

        return error_response


def clean_formatting_issues(text):
    """Clean up various formatting issues in the text."""
    text = re.sub(r"^[X\-d;y�Hl]+\s*-\s*", "- ", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*[X\-d;y�Hl]+\s*", "", text, flags=re.MULTILINE)

    # Clean up bullet points
    text = re.sub(r"\s*-\s*\*\*([^*]+)\*\*:\s*", r"\n\n**\1:**\n", text)
    text = re.sub(r"\s*-\s*([^-\n]+)", r"\n- \1", text)

    # Fix section headers
    text = re.sub(r"\*\*(\d+\.\s*[^*]+)\*\*", r"\n\n**\1**\n", text)

    # Clean up excessive spacing
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"^\s+", "", text, flags=re.MULTILINE)

    # Fix punctuation spacing
    text = re.sub(r"\.([A-Z])", r". \1", text)

    return text.strip()


def clean_text_remove_think_tags(text):
    """
    Remove <think> tags and their contents from text, then clean formatting.

    Args:
        text (str): Raw text with <think> tags

    Returns:
        str: Cleaned text without <think> content
    """
    # Remove <think> tags and everything between them
    cleaned_text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)

    # Clean up extra whitespace and formatting issues
    cleaned_text = re.sub(r"\s+", " ", cleaned_text.strip())

    # Fix common formatting issues
    cleaned_text = clean_formatting_issues(cleaned_text)

    return cleaned_text


async def background_analysis(job_id: str, request: AnalysisRequest):
    """Main endpoint for foot traffic analysis."""
    logger.info(f"Starting background analysis for job_id: {job_id}")
    try:
        # Update job status to 'processing'
        valkey_client.set(
            f"job:{job_id}",
            json.dumps(
                {
                    "status": "processing",
                    "submitted_at": datetime.now(timezone.utc).isoformat(),
                }
            ),
            ex=3600,  # 1 hour expiry
        )

        # Get sql statistics for the day
        sql_daily_results = get_traffic_analytics(today)
        # Calculate statistics
        stats = calculate_traffic_statistics(sql_daily_results)

        logger.info(stats)
        # Generate insights and recommendations
        insights = generate_insights(stats, request.building_stats)
        recommendations = create_recommendations(stats, request.building_stats)
        # Get camera statistics
        camera_stats = CameraStats()

        # Prepare data for LLM analysis
        analysis_context = {
            "camera_detection_stats": camera_stats.get_detection_counts(),
            "camera_confidence_stats": camera_stats.get_confidence_stats(),
            "camera_movement_stats": [
                camera_stats.get_movement_stats(camera_id=i) for i in range(32)
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
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": f"""Analyze the following serviced apartment foot traffic data with focus on:
- Client satisfaction indicators (dwell time, repeat visits)
- Operational trends (staffing adequacy, cleaning efficiency)
e Safety compliance (maximum occupancy events, emergency preparedness)


ANALYSIS CONTEXT:
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

        # whatsapp_messenger(output_file)

        return JSONResponse(status_code=200, content=analysis_result)

    except ValueError as e:
        logger.debug(f"Analysis error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


@logger.catch()
@app.post("/analyse")
async def analyze_foot_traffic(
    request: AnalysisRequest, background_tasks: BackgroundTasks
):
    job_id = str(uuid.uuid4())
    logger.info(f"Received analysis request. Assigning job_id: {job_id}")

    # Add the long-running function to the background tasks
    background_tasks.add_task(background_analysis, job_id, request)

    # Return a 202 Accepted response with the job ID and a status URL
    return {
        "job_id": job_id,
        "message": "Analysis request accepted and is being processed in the background.",
        "status_url": f"/analyse/status/{job_id}",
    }


@app.get("/analyse/status/{job_id}")
async def get_analysis_status(job_id: str):
    """
    Poll this endpoint with the job ID to check the status of the analysis.
    """
    job_data = valkey_client.get(f"job:{job_id}")

    if not job_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Job ID not found."
        )

    job_info = json.loads(job_data)
    return JSONResponse(content=job_info)


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "Foot Traffic Analytics API",
        "timestamp": datetime.now(timezone.utc),
    }


# Whatsapp messaging endpoint
with open("/app/secrets/whatsapp_secrets.txt", "r") as f:
    WHATSAPP_VERIFCATION_TOKEN = f.read().strip()


@app.api_route("/webhooks", methods=["GET", "POST"])
async def handle_whatsapp(
    request: Request,
    background_tasks: BackgroundTasks,
    # GET parameters for webhook verification
    hub_mode: Optional[str] = Query(None, alias="hub.mode"),
    hub_verify_token: Optional[str] = Query(None, alias="hub.verify_token"),
    hub_challenge: Optional[str] = Query(None, alias="hub.challenge"),
):
    if request.method == "GET":
        # WhatsApp webhook verification
        if hub_mode and hub_verify_token:
            if (
                hub_mode == "subscribe"
                and hub_verify_token == WHATSAPP_VERIFCATION_TOKEN
            ):
                return PlainTextResponse(content=hub_challenge, status_code=200)
            else:
                raise HTTPException(status_code=403, detail="Verification failed")
        else:
            raise HTTPException(status_code=400, detail="Missing parameters")

    elif request.method == "POST":
        # Verify the signature if needed (commented out like in original)
        """
        signature = request.headers.get("x-hub-signature-256", "").split("sha256=")[-1].strip()
        if not verify_signature(await request.body(), signature):
            raise HTTPException(status_code=403, detail="Invalid signature")
        """

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


@app.get("/")
async def root(request: Request):
    """Root endpoint with API information"""
    return {"request_id": request.state.request_id}
    # return templates.TemplateResponse("dash.html", {"request": request})


"""
# Main entry point
if __name__ == "__main__":
    print("Starting Foot Traffic Analytics API server on http://localhost:8000")
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)"""
