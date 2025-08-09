# utils/db/stats_db.py
from datetime import datetime, timedelta
from typing import Dict, Any
from loguru import logger
import pytz
from utils.db.base import execute_query
from utils.timezone import nairobi_tz

logger.add("./logs/stats_db.log", rotation="1 week", level="INFO")

async def get_traffic_analytics(period: str = 'daily') -> Dict[str, Any]:
    """
    Performs a comprehensive analysis of detection logs for a given period.

    Args:
        period (str): 'daily' or 'weekly'. Defaults to 'daily'.

    Returns:
        A dictionary containing various aggregated statistics.
    """
    now_nairobi = datetime.now(nairobi_tz)
    if period == 'weekly':
        start_date = now_nairobi.date() - timedelta(days=now_nairobi.weekday() + 7) # Start of last week (Mon)
        end_date = start_date + timedelta(days=6) # End of last week (Sun)
    else: # Default to daily
        start_date = now_nairobi.date()
        end_date = now_nairobi.date()

    logger.info(f"Running traffic analytics for period: {period} ({start_date} to {end_date})")

    # This single, powerful query uses CTEs to perform all calculations in one pass.
    comprehensive_query = """
    WITH date_filtered_logs AS (
        SELECT
            id,
            timestamp,
            camera_name,
            location,
            object_name,
            EXTRACT(HOUR FROM timestamp AT TIME ZONE 'Africa/Nairobi') AS hour,
            DATE_TRUNC('minute', timestamp AT TIME ZONE 'Africa/Nairobi') as minute
        FROM detection_logs
        WHERE (timestamp AT TIME ZONE 'Africa/Nairobi')::date BETWEEN :start_date AND :end_date
    ),
    basic_stats AS (
        SELECT
            COUNT(*) AS total_detections,
            COUNT(DISTINCT camera_name) AS active_cameras,
            COUNT(DISTINCT location) AS unique_locations
        FROM date_filtered_logs
    ),
    object_breakdown AS (
        SELECT
            object_name,
            COUNT(*) AS count
        FROM date_filtered_logs
        GROUP BY object_name
        ORDER BY count DESC
    ),
    hourly_patterns AS (
        SELECT
            hour::integer,
            COUNT(*) AS count
        FROM date_filtered_logs
        GROUP BY hour
        ORDER BY hour
    ),
    person_hourly_patterns AS (
        SELECT
            hour::integer,
            COUNT(*) AS count
        FROM date_filtered_logs
        WHERE object_name = 'person'
        GROUP BY hour
        ORDER BY hour
    ),
    location_ranking AS (
        SELECT
            location,
            COUNT(*) AS count
        FROM date_filtered_logs
        GROUP BY location
        ORDER BY count DESC
    ),
    peak_minute AS (
        SELECT
            minute,
            COUNT(*) as count
        FROM date_filtered_logs
        GROUP BY minute
        ORDER BY count DESC
        LIMIT 1
    )
    SELECT
        (SELECT jsonb_agg(t) FROM basic_stats t) AS basic_stats,
        (SELECT jsonb_agg(t) FROM object_breakdown t) AS object_breakdown,
        (SELECT jsonb_agg(t) FROM hourly_patterns t) AS hourly_patterns,
        (SELECT jsonb_agg(t) FROM person_hourly_patterns t) AS person_hourly_patterns,
        (SELECT jsonb_agg(t) FROM location_ranking t) AS location_ranking,
        (SELECT jsonb_agg(t) FROM peak_minute t) AS peak_minute;
    """
    
    try:
        results = await execute_query(comprehensive_query, {"start_date": start_date, "end_date": end_date})
        if results:
            return results[0]
        return {}
    except Exception as e:
        logger.error(f"Error in get_traffic_analytics: {e}", exc_info=True)
        return {}

async def get_latest_detections(limit: int = 100) -> list:
    """Gets the most recent detection events from the database."""
    query = """
    SELECT timestamp, camera_name, location, object_name, confidence
    FROM detection_logs
    ORDER BY timestamp DESC
    LIMIT :limit;
    """
    try:
        return await execute_query(query, {"limit": limit})
    except Exception as e:
        logger.error(f"Failed to get latest detections: {e}")
        return []

