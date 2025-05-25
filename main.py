import json
import statistics
from datetime import datetime, date
from typing import Dict, Optional, List, Any
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from loguru import logger
from ollama import AsyncClient
from pydantic import BaseModel
from utils.db import get_traffic_analytics
from utils.holidays import holiday_checker
from utils.llm_output_formatter import (
    create_pdf_from_text,
    get_cleaned_text_only,
)
from utils.whatsapp import whatsapp_messenger

# Getting the current date
today = date.today()
target_date = datetime(today.year, today.month, today.day)


app = FastAPI(title="Foot Traffic Analytics API")
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

# Ollama client for LLM analysis
ollama_client = AsyncClient(host="http://ollama:11434")


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


def calculate_traffic_statistics(traffic_data: List[FootTrafficData]) -> Dict[str, Any]:
    """Calculate basic statistics from foot traffic data"""
    if not traffic_data:
        return {}

    counts = [data.count for data in traffic_data]
    locations = [data.location for data in traffic_data]

    stats = {
        "total_traffic": sum(counts),
        "average_traffic": statistics.mean(counts),
        "median_traffic": statistics.median(counts),
        "max_traffic": max(counts),
        "min_traffic": min(counts),
        "std_deviation": statistics.stdev(counts) if len(counts) > 1 else 0,
        "unique_locations": len(set(locations)),
        "data_points": len(traffic_data),
    }

    # Traffic by location
    location_traffic = {}
    for data in traffic_data:
        if data.location not in location_traffic:
            location_traffic[data.location] = []
        location_traffic[data.location].append(data.count)

    stats["location_breakdown"] = {
        loc: {
            "total": sum(counts),
            "average": statistics.mean(counts),
            "peak": max(counts),
        }
        for loc, counts in location_traffic.items()
    }

    # Time-based analysis
    hourly_traffic = {}
    daily_traffic = {}

    for data in traffic_data:
        try:
            dt = datetime.fromisoformat(data.timestamp.replace("Z", "+00:00"))
            hour = dt.hour
            day = dt.strftime("%Y-%m-%d")

            if hour not in hourly_traffic:
                hourly_traffic[hour] = []
            hourly_traffic[hour].append(data.count)

            if day not in daily_traffic:
                daily_traffic[day] = []
            daily_traffic[day].append(data.count)

        except ValueError:
            continue

    stats["hourly_patterns"] = {
        hour: {"average": statistics.mean(counts), "total": sum(counts)}
        for hour, counts in hourly_traffic.items()
    }

    stats["daily_totals"] = {day: sum(counts) for day, counts in daily_traffic.items()}

    # Peak hours identification
    if hourly_traffic:
        peak_hour = max(hourly_traffic.items(), key=lambda x: statistics.mean(x[1]))
        stats["peak_hour"] = {
            "hour": peak_hour[0],
            "average_traffic": statistics.mean(peak_hour[1]),
        }

    return stats


def generate_insights(
    stats: Dict[str, Any], building_stats: Optional[BuildingStats] = None
) -> List[str]:
    """Generate business insights from traffic statistics"""
    insights = []

    if not stats:
        return ["No data available for analysis"]

    # Traffic volume insights
    total_traffic = stats.get("total_traffic", 0)
    avg_traffic = stats.get("average_traffic", 0)

    if total_traffic > 0:
        insights.append(f"Total foot traffic recorded: {total_traffic:,} people")
        insights.append(f"Average traffic per measurement: {avg_traffic:.1f} people")

    # Peak hour insights
    if "peak_hour" in stats:
        peak_info = stats["peak_hour"]
        hour = peak_info["hour"]
        peak_time = f"{hour}:00-{hour + 1}:00"
        insights.append(
            f"Peak traffic occurs between {peak_time} with average of {peak_info['average_traffic']:.1f} people"
        )

    # Location insights
    if "location_breakdown" in stats:
        locations = stats["location_breakdown"]
        if locations:
            busiest_location = max(locations.items(), key=lambda x: x[1]["total"])
            insights.append(
                f"Busiest location: {busiest_location[0]} with {busiest_location[1]['total']} total visitors"
            )

    # Capacity utilization (if building stats provided)
    if building_stats and building_stats.capacity and "max_traffic" in stats:
        max_traffic = stats["max_traffic"]
        utilization = (max_traffic / building_stats.capacity) * 100
        insights.append(
            f"Peak capacity utilization: {utilization:.1f}% ({max_traffic}/{building_stats.capacity})"
        )

        if utilization > 80:
            insights.append(
                "⚠️ High capacity utilization detected - consider crowd management strategies"
            )
        elif utilization < 30:
            insights.append(
                "💡 Low capacity utilization - opportunity for increased marketing or events"
            )

    # Variability insights
    if "std_deviation" in stats and stats["average_traffic"] > 0:
        cv = stats["std_deviation"] / stats["average_traffic"]
        if cv > 0.5:
            insights.append(
                "📊 High traffic variability detected - consider analyzing patterns for better planning"
            )
        elif cv < 0.2:
            insights.append(
                "📊 Consistent traffic patterns observed - good for predictable operations"
            )

    # Daily pattern insights
    if "daily_totals" in stats and len(stats["daily_totals"]) > 1:
        daily_values = list(stats["daily_totals"].values())
        if len(daily_values) >= 7:
            recent_trend = sum(daily_values[-3:]) / 3 - sum(daily_values[:3]) / 3
            if recent_trend > 0:
                insights.append("📈 Recent upward trend in foot traffic observed")
            elif recent_trend < 0:
                insights.append("📉 Recent downward trend in foot traffic observed")

    return insights


def create_recommendations(
    stats: Dict[str, Any], building_stats: Optional[BuildingStats] = None
) -> List[str]:
    """Generate actionable recommendations based on analysis"""
    recommendations = []

    if not stats:
        return ["Insufficient data for recommendations"]

    # Peak hour recommendations
    if "peak_hour" in stats:
        peak_hour = stats["peak_hour"]["hour"]
        if 9 <= peak_hour <= 11:
            recommendations.append(
                "Consider increasing morning staff levels and opening additional service points"
            )
        elif 12 <= peak_hour <= 14:
            recommendations.append(
                "Optimize lunch-hour operations and consider express service options"
            )
        elif 17 <= peak_hour <= 19:
            recommendations.append(
                "Prepare for evening rush - ensure adequate staffing and queue management"
            )

    # Capacity recommendations
    if building_stats and building_stats.capacity:
        max_traffic = stats.get("max_traffic", 0)
        if max_traffic > building_stats.capacity * 0.9:
            recommendations.append("Implement crowd control measures during peak times")
            recommendations.append(
                "Consider capacity expansion or better flow management"
            )

    # Location-specific recommendations
    if "location_breakdown" in stats:
        locations = stats["location_breakdown"]
        if len(locations) > 1:
            location_traffic = [(loc, data["total"]) for loc, data in locations.items()]
            location_traffic.sort(key=lambda x: x[1], reverse=True)

            if location_traffic[0][1] > location_traffic[-1][1] * 3:
                recommendations.append(
                    f"Redistribute traffic from {location_traffic[0][0]} to underutilized areas"
                )
                recommendations.append(
                    "Consider relocating services or improving signage for better flow distribution"
                )

    # Operational recommendations
    if "hourly_patterns" in stats:
        hourly_data = stats["hourly_patterns"]
        quiet_hours = [
            hour
            for hour, data in hourly_data.items()
            if data["average"] < stats["average_traffic"] * 0.5
        ]
        if quiet_hours:
            recommendations.append(
                f"Schedule maintenance and deep cleaning during low-traffic hours: {', '.join(map(str, sorted(quiet_hours)))}"
            )

    # Data collection recommendations
    if stats.get("data_points", 0) < 100:
        recommendations.append(
            "Increase data collection frequency for more accurate analysis"
        )

    return recommendations


@logger.catch
@app.post("/analyse")
async def analyze_foot_traffic(request: AnalysisRequest):
    """Main endpoint for foot traffic analysis"""
    try:
        # Calculate statistics
        stats = calculate_traffic_statistics(request.traffic_data)
        logger.info(holiday_checker(request.traffic_data[0].timestamp))

        # Generate insights and recommendations
        insights = generate_insights(stats, request.building_stats)
        recommendations = create_recommendations(stats, request.building_stats)
        # Get sql statistics for the day
        sql_daily_results = get_traffic_analytics(today)
        logger.info(sql_daily_results)
        # Prepare data for LLM analysis
        analysis_context = {
            "statistics": sql_daily_results,
            "insights": insights,
            "recommendations": recommendations,
            "building_info": request.building_stats.dict()
            if request.building_stats
            else None,
            "data_points": len(request.traffic_data),
        }

        # Create system prompt for LLM
        SYSTEM_PROMPT = """You are a foot traffic analytics specialist. Analyze the provided foot traffic data and building statistics to create a comprehensive report.

Your analysis should include:
1. Executive Summary
2. Key Findings
3. Traffic Patterns Analysis
4. Operational Insights
5. Strategic Recommendations
6. Risk Assessment (if applicable)

Use the provided statistics, insights, and recommendations as a foundation, but add your own analytical perspective. Present findings in a clear, professional format suitable for building managers and business stakeholders.

Focus on actionable insights thvercelat can improve operations, enhance visitor experience, and optimize resource allocation."""

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": f"""Please analyze this foot traffic data and create a comprehensive report:

ANALYSIS CONTEXT:
{json.dumps(analysis_context, indent=2, default=str)}

ANALYSIS PERIOD: {request.analysis_period}
BUILDING TYPE: {request.building_stats.building_type if request.building_stats else "Not specified"}

Generate a detailed analytical report with specific recommendations for improving foot traffic management and building operations.""",
            },
        ]

        # Get LLM analysis
        response = await ollama_client.chat(
            model=llm_model_id,
            messages=messages,
            options={
                "temperature": 0.3,
                "max_tokens": 1000,
            },
        )

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
                "building_info": request.building_stats.dict()
                if request.building_stats
                else None,
            },
            "raw_statistics": stats,
            "key_insights": insights,
            "recommendations": recommendations,
            "detailed_report": llm_report,
            "analysis_metadata": {
                "generated_at": datetime.now().isoformat(),
                "model_used": llm_model_id,
                "include_predictions": request.include_predictions,
            },
        }
        cleaned_llm_report = get_cleaned_text_only(llm_report)
        create_pdf_from_text(llm_report)

        whatsapp_messenger("Analysis complete")

        return JSONResponse(status_code=200, content=analysis_result)

    except ValueError as e:
        logger.debug(f"Analysis error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


@app.post("/quick-stats")
async def get_quick_stats(traffic_data: List[FootTrafficData]):
    """Endpoint for quick statistical overview without LLM analysis"""
    try:
        stats = calculate_traffic_statistics(traffic_data)
        insights = generate_insights(stats)

        return JSONResponse(
            status_code=200,
            content={
                "statistics": stats,
                "quick_insights": insights,
                "generated_at": datetime.now().isoformat(),
            },
        )
    except Exception as e:
        logger.error(f"Quick stats error: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Statistics calculation failed: {str(e)}"
        )


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "Foot Traffic Analytics API",
        "timestamp": datetime.now().isoformat(),
    }


@app.get("/")
async def root():
    """Root endpoint with API information"""
    return {
        "service": "Foot Traffic Analytics API",
        "version": "1.0.0",
        "endpoints": {
            "analyse": "POST /analyse - Comprehensive foot traffic analysis",
            "quick-stats": "POST /quick-stats - Quick statistical overview",
            "health": "GET /health - Health check",
        },
        "description": "API for analyzing foot traffic data and generating insights for building management",
    }


"""
# Main entry point
if __name__ == "__main__":
    print("Starting Foot Traffic Analytics API server on http://localhost:8000")
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)"""
