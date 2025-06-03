import json
import statistics
from datetime import datetime, date, timezone
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
    clean_text_remove_think_tags,
    create_pdf_from_text,
    get_cleaned_text_only,
)
from utils.whatsapp import whatsapp_messenger
from decimal import Decimal
from utils.camera_stats import CameraStats

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


def calculate_traffic_statistics(sql_results: Dict[str, Any]) -> Dict[str, Any]:
    """Calculate comprehensive statistics from SQL daily results"""
    if not sql_results:
        return {}

    # Extract basic daily statistics
    daily_stats = sql_results.get("daily_statistics", {})
    location_analysis = sql_results.get("location_direction_analysis", [])
    weather_analysis = sql_results.get("weather_impact_analysis", [])
    hourly_data = sql_results.get("hourly_aggregates", [])
    location_stats = sql_results.get("location_statistics", [])
    temperature_correlation = sql_results.get("temperature_correlation", {})
    raw_data = sql_results.get("daily_traffic_data", [])

    stats = {
        # Core metrics from daily statistics
        "total_traffic": daily_stats.get("total_count", 0),
        "average_traffic": daily_stats.get("avg_count", 0),
        "max_traffic": daily_stats.get("max_count", 0),
        "data_points": daily_stats.get("record_count", 0),
    }

    # Calculate additional statistics from raw data if available
    if raw_data:
        counts = [item["count"] for item in raw_data]
        if len(counts) > 1:
            stats["median_traffic"] = statistics.median(counts)
            stats["min_traffic"] = min(counts)
            stats["std_deviation"] = statistics.stdev(counts)
        else:
            stats["median_traffic"] = counts[0] if counts else 0
            stats["min_traffic"] = counts[0] if counts else 0
            stats["std_deviation"] = 0

    # Location and direction breakdown
    if location_analysis:
        stats["location_breakdown"] = {}
        stats["direction_analysis"] = {}

        for item in location_analysis:
            location = item["location"]
            direction = item["direction"]

            # Location stats
            if location not in stats["location_breakdown"]:
                stats["location_breakdown"][location] = {"total": 0, "directions": {}}

            stats["location_breakdown"][location]["total"] += item["total"]
            stats["location_breakdown"][location]["directions"][direction] = {
                "total": item["total"],
                "average": item["average"],
            }

            # Direction stats
            if direction not in stats["direction_analysis"]:
                stats["direction_analysis"][direction] = {"total": 0, "locations": []}
            stats["direction_analysis"][direction]["total"] += item["total"]
            stats["direction_analysis"][direction]["locations"].append(
                {"location": location, "count": item["total"]}
            )

    # Weather impact analysis
    if weather_analysis:
        stats["weather_impact"] = {}
        for weather_item in weather_analysis:
            weather = weather_item["weather"]
            stats["weather_impact"][weather] = {
                "total_count": weather_item["total_count"],
                "average_count": weather_item["avg_count"],
            }

        # Find best and worst weather conditions
        best_weather = max(weather_analysis, key=lambda x: x["avg_count"])
        worst_weather = min(weather_analysis, key=lambda x: x["avg_count"])

        stats["weather_insights"] = {
            "best_conditions": {
                "weather": best_weather["weather"],
                "avg_count": best_weather["avg_count"],
            },
            "worst_conditions": {
                "weather": worst_weather["weather"],
                "avg_count": worst_weather["avg_count"],
            },
        }

    # Hourly patterns
    if hourly_data:
        stats["hourly_patterns"] = {}
        for hour_item in hourly_data:
            hour = hour_item["hour"]
            stats["hourly_patterns"][hour] = {
                "location": hour_item["location"],
                "total_count": hour_item["total_count"],
            }

        # Find peak hour
        peak_hour_data = max(hourly_data, key=lambda x: x["total_count"])
        stats["peak_hour"] = {
            "hour": peak_hour_data["hour"],
            "location": peak_hour_data["location"],
            "traffic_count": peak_hour_data["total_count"],
        }

        # Find quiet hour
        quiet_hour_data = min(hourly_data, key=lambda x: x["total_count"])
        stats["quiet_hour"] = {
            "hour": quiet_hour_data["hour"],
            "location": quiet_hour_data["location"],
            "traffic_count": quiet_hour_data["total_count"],
        }

    # Location performance ranking
    if location_stats:
        stats["location_ranking"] = []
        for loc_stat in location_stats:
            stats["location_ranking"].append(
                {
                    "location": loc_stat["location"],
                    "total_count": loc_stat["total_count"],
                    "avg_count": loc_stat["avg_count"],
                    "max_count": loc_stat["max_count"],
                }
            )

        # Sort by total count
        stats["location_ranking"].sort(key=lambda x: x["total_count"], reverse=True)

        # Calculate location utilization distribution
        total_all_locations = sum(loc["total_count"] for loc in location_stats)
        if total_all_locations > 0:
            stats["location_distribution"] = {
                loc["location"]: round(
                    (loc["total_count"] / total_all_locations) * 100, 2
                )
                for loc in location_stats
            }

    # Temperature correlation
    if temperature_correlation:
        correlation_value = temperature_correlation.get("count_temp_correlation", 0)
        stats["temperature_correlation"] = {
            "correlation_coefficient": correlation_value,
            "correlation_strength": get_correlation_strength(correlation_value),
        }

    # Calculate unique metrics
    if location_analysis:
        stats["unique_locations"] = len(
            set(item["location"] for item in location_analysis)
        )
        stats["unique_directions"] = len(
            set(item["direction"] for item in location_analysis)
        )

    return stats


def get_correlation_strength(correlation: float) -> str:
    """Categorize correlation strength"""
    abs_corr = abs(correlation)
    if abs_corr >= 0.7:
        return "Strong"
    elif abs_corr >= 0.5:
        return "Moderate"
    elif abs_corr >= 0.3:
        return "Weak"
    else:
        return "Very Weak"


def generate_insights(
    stats: Dict[str, Any], building_stats: Optional[Any] = None
) -> List[str]:
    """Generate business insights from SQL-based traffic statistics"""
    insights = []

    if not stats:
        return ["No data available for analysis"]

    # Overall traffic insights
    total_traffic = stats.get("total_traffic", 0)
    avg_traffic = stats.get("average_traffic", 0)
    max_traffic = stats.get("max_traffic", 0)
    data_points = stats.get("data_points", 0)

    if total_traffic > 0:
        insights.append(
            f"📊 Total foot traffic recorded: {total_traffic:,} people across {data_points} measurement points"
        )
        insights.append(f"📈 Average traffic per location: {avg_traffic:.1f} people")
        insights.append(f"🔝 Peak single location traffic: {max_traffic} people")

    # Peak hour insights
    if "peak_hour" in stats:
        peak_info = stats["peak_hour"]
        hour = peak_info["hour"]
        location = peak_info["location"]
        count = peak_info["traffic_count"]
        time_period = f"{hour:02d}:00-{(hour + 1):02d}:00"
        insights.append(
            f"⏰ Peak activity occurs at {time_period} at {location} with {count} people"
        )

    # Quiet hour insights
    if "quiet_hour" in stats:
        quiet_info = stats["quiet_hour"]
        hour = quiet_info["hour"]
        location = quiet_info["location"]
        count = quiet_info["traffic_count"]
        time_period = f"{hour:02d}:00-{(hour + 1):02d}:00"
        insights.append(
            f"🔽 Lowest activity at {time_period} at {location} with {count} people"
        )

    # Location performance insights
    if "location_ranking" in stats and stats["location_ranking"]:
        top_location = stats["location_ranking"][0]
        bottom_location = stats["location_ranking"][-1]

        insights.append(
            f"🏆 Busiest location: {top_location['location']} ({top_location['total_count']} total visitors)"
        )
        insights.append(
            f"📍 Least busy location: {bottom_location['location']} ({bottom_location['total_count']} total visitors)"
        )

        # Location distribution insight
        if "location_distribution" in stats:
            top_percentage = max(stats["location_distribution"].values())
            if top_percentage > 40:
                insights.append(
                    f"⚠️ Traffic concentration: {top_percentage}% of all traffic flows through the busiest location"
                )

    # Direction flow insights
    if "direction_analysis" in stats:
        direction_stats = stats["direction_analysis"]
        if "entry" in direction_stats and "exit" in direction_stats:
            entry_total = direction_stats["entry"]["total"]
            exit_total = direction_stats["exit"]["total"]
            flow_balance = (
                abs(entry_total - exit_total) / max(entry_total, exit_total) * 100
            )

            if flow_balance < 10:
                insights.append("⚖️ Well-balanced entry/exit flow patterns observed")
            elif entry_total > exit_total:
                insights.append(
                    f"📥 Higher entry traffic ({entry_total}) vs exit traffic ({exit_total}) - {flow_balance:.1f}% imbalance"
                )
            else:
                insights.append(
                    f"📤 Higher exit traffic ({exit_total}) vs entry traffic ({entry_total}) - {flow_balance:.1f}% imbalance"
                )

    # Weather impact insights
    if "weather_insights" in stats:
        weather_info = stats["weather_insights"]
        best_weather = weather_info["best_conditions"]
        worst_weather = weather_info["worst_conditions"]

        insights.append(
            f"☀️ Best weather for foot traffic: {best_weather['weather']} (avg: {best_weather['avg_count']:.1f} people)"
        )
        insights.append(
            f"🌧️ Challenging weather conditions: {worst_weather['weather']} (avg: {worst_weather['avg_count']:.1f} people)"
        )

    # Temperature correlation insights
    if "temperature_correlation" in stats:
        temp_corr = stats["temperature_correlation"]
        correlation = temp_corr["correlation_coefficient"]
        strength = temp_corr["correlation_strength"]

        if correlation > 0.5:
            insights.append(
                f"🌡️ {strength} positive correlation between temperature and foot traffic ({correlation:.2f})"
            )
        elif correlation < -0.5:
            insights.append(
                f"🌡️ {strength} negative correlation between temperature and foot traffic ({correlation:.2f})"
            )
        else:
            insights.append(
                f"🌡️ {strength} temperature correlation with foot traffic ({correlation:.2f})"
            )

    # Capacity utilization insights (if building stats provided)
    if (
        building_stats
        and hasattr(building_stats, "capacity")
        and building_stats.capacity
    ):
        utilization = (max_traffic / building_stats.capacity) * 100
        insights.append(
            f"🏢 Peak capacity utilization: {utilization:.1f}% ({max_traffic}/{building_stats.capacity})"
        )

        if utilization > 80:
            insights.append(
                "⚠️ High capacity utilization - consider crowd management strategies"
            )
        elif utilization < 30:
            insights.append(
                "💡 Low capacity utilization - opportunity for increased marketing or events"
            )

    # Traffic variability insights
    if "std_deviation" in stats and avg_traffic > 0:
        cv = stats["std_deviation"] / avg_traffic
        if cv > 0.5:
            insights.append(
                "📊 High traffic variability - consider analyzing patterns for predictable operations"
            )
        elif cv < 0.2:
            insights.append(
                "📊 Consistent traffic patterns - good for predictable resource planning"
            )

    return insights


def create_recommendations(
    stats: Dict[str, Any], building_stats: Optional[Any] = None
) -> List[str]:
    """Generate actionable recommendations based on SQL analysis"""
    recommendations = []

    if not stats:
        return ["Insufficient data for recommendations"]

    # Peak hour staffing recommendations
    if "peak_hour" in stats:
        peak_hour = stats["peak_hour"]["hour"]
        peak_location = stats["peak_hour"]["location"]

        if 6 <= peak_hour <= 9:
            recommendations.append(
                f"🌅 Morning rush preparation: Increase staffing at {peak_location} between {peak_hour:02d}:00-{(peak_hour + 2):02d}:00"
            )
        elif 11 <= peak_hour <= 14:
            recommendations.append(
                f"🍽️ Lunch hour optimization: Deploy additional resources at {peak_location} during midday peak"
            )
        elif 17 <= peak_hour <= 20:
            recommendations.append(
                f"🌆 Evening rush management: Prepare for high traffic at {peak_location} during evening hours"
            )

        recommendations.append(
            f"📍 Focus operational excellence efforts on {peak_location} during peak hours"
        )

    # Location-based recommendations
    if "location_ranking" in stats and len(stats["location_ranking"]) > 1:
        top_location = stats["location_ranking"][0]
        bottom_locations = stats["location_ranking"][-2:]  # Bottom 2 locations

        # Traffic redistribution
        if top_location["total_count"] > sum(
            loc["total_count"] for loc in bottom_locations
        ):
            recommendations.append(
                f"🔄 Redistribute traffic from {top_location['location']} to underutilized areas"
            )
            recommendations.append(
                "🚪 Improve signage and wayfinding to promote alternative entry/exit points"
            )

        # Underutilized space optimization
        for location in bottom_locations:
            if location["total_count"] < stats["average_traffic"] * 0.5:
                recommendations.append(
                    f"💡 Optimize {location['location']} utilization through targeted marketing or service relocation"
                )

    # Flow balance recommendations
    if "direction_analysis" in stats:
        direction_stats = stats["direction_analysis"]
        if "entry" in direction_stats and "exit" in direction_stats:
            entry_total = direction_stats["entry"]["total"]
            exit_total = direction_stats["exit"]["total"]

            if abs(entry_total - exit_total) / max(entry_total, exit_total) > 0.2:
                recommendations.append(
                    "⚖️ Investigate entry/exit flow imbalance - consider additional exit points or flow management"
                )

    # Weather-based operational recommendations
    if "weather_insights" in stats:
        weather_info = stats["weather_insights"]
        best_weather = weather_info["best_conditions"]["weather"]
        worst_weather = weather_info["worst_conditions"]["weather"]

        recommendations.append(
            f"☀️ Plan special events and promotions during {best_weather} weather conditions"
        )
        recommendations.append(
            f"🌧️ Develop contingency plans for {worst_weather} weather to maintain service levels"
        )

    # Temperature-based recommendations
    if "temperature_correlation" in stats:
        correlation = stats["temperature_correlation"]["correlation_coefficient"]
        if abs(correlation) > 0.5:
            if correlation > 0:
                recommendations.append(
                    "🌡️ Consider climate control and comfort measures during warmer periods"
                )
            else:
                recommendations.append(
                    "🌡️ Implement warming stations or comfort measures during cooler periods"
                )

    # Maintenance and operational timing
    if "quiet_hour" in stats:
        quiet_hour = stats["quiet_hour"]["hour"]
        quiet_location = stats["quiet_hour"]["location"]
        recommendations.append(
            f"🔧 Schedule maintenance activities during low-traffic period: {quiet_hour:02d}:00-{(quiet_hour + 1):02d}:00 at {quiet_location}"
        )

    # Capacity and infrastructure recommendations
    if (
        building_stats
        and hasattr(building_stats, "capacity")
        and building_stats.capacity
    ):
        max_traffic = stats.get("max_traffic", 0)
        utilization = (max_traffic / building_stats.capacity) * 100

        if utilization > 85:
            recommendations.append(
                "🏗️ Consider capacity expansion or queue management systems"
            )
            recommendations.append(
                "📱 Implement real-time occupancy monitoring and communication"
            )
        elif utilization < 25:
            recommendations.append(
                "💰 Evaluate space optimization opportunities or revenue-generating activities"
            )

    # Data collection and monitoring improvements
    data_points = stats.get("data_points", 0)
    if data_points < 20:
        recommendations.append(
            "📊 Increase monitoring frequency for more granular traffic analysis"
        )

    if "unique_locations" in stats and stats["unique_locations"] < 5:
        recommendations.append(
            "📍 Consider adding monitoring points at additional strategic locations"
        )

    # Operational efficiency recommendations
    if "location_distribution" in stats:
        max_concentration = max(stats["location_distribution"].values())
        if max_concentration > 50:
            recommendations.append(
                "🚦 Implement traffic flow management systems to reduce bottlenecks"
            )

    return recommendations


@logger.catch
@app.post("/analyse")
async def analyze_foot_traffic(request: AnalysisRequest):
    """Main endpoint for foot traffic analysis"""
    try:
        # Get sql statistics for the day
        sql_daily_results = get_traffic_analytics(today)
        # Calculate statistics
        stats = calculate_traffic_statistics(sql_daily_results)
        current_time_utc = datetime.now(timezone.utc)
        formatted_time = current_time_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
        logger.info(holiday_checker(formatted_time))
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
{json.dumps(analysis_context, indent=2, default=str), sql_daily_results}

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
        create_pdf_from_text(clean_text_remove_think_tags(llm_report))

        # whatsapp_messenger("Analysis complete")

        return JSONResponse(status_code=200, content=analysis_result)

    except ValueError as e:
        logger.debug(f"Analysis error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


@app.post("/quick-stats")
async def get_quick_stats(traffic_data: Any):
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
    except ValueError as e:
        logger.debug(f"Quick stats error: {str(e)}")


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
