from dotenv import load_dotenv
from loguru import logger
from typing import Any
from datetime import datetime
from utils.db.base import execute_query

# Define logger path
logger.add("./logs/db.log", rotation="700 MB")


async def get_traffic_by_date(target_date: Any) -> list:
    """Get all traffic records for a specific date - optimized query"""
    query = """
    SELECT 
        timestamp,
        camera_name,
        count,
        location,
        direction,
        day_of_week,
        is_holiday
    FROM camera_traffic
    WHERE DATE(timestamp) = :target_date
    ORDER BY count DESC;
    """
    return await execute_query(query, {"target_date": target_date})


async def get_hourly_counts_sorted(target_date: Any) -> list:
    """Get hourly aggregated counts - optimized with index hints"""
    query = """
    SELECT 
        EXTRACT(HOUR FROM timestamp)::INTEGER AS hour,
        location,
        SUM(count) AS total_count
    FROM camera_traffic
    WHERE DATE(timestamp) = :target_date
    GROUP BY EXTRACT(HOUR FROM timestamp), location
    ORDER BY hour, total_count DESC;
    """
    return await execute_query(query, {"target_date": target_date.date()})


async def get_top_locations(target_date: Any, n: int = 5) -> list:
    """Get top n locations by total count - optimized aggregation"""
    try:
        query = """
    SELECT 
        location,
        SUM(count) AS total_count,
        ROUND(AVG(count::NUMERIC), 2) AS avg_count,
        MAX(count) AS max_count
    FROM camera_traffic
    WHERE DATE(timestamp) = :target_date
    GROUP BY location
    ORDER BY total_count DESC
    LIMIT :limit_n;
    """
        return await execute_query(
            query, {"target_date": target_date.date(), "limit_n": n}
        )
    except ValueError as e:
        logger.debug(f"Failed to get locations statistics due to {e}")
        return []


async def get_traffic_analytics(target_date: datetime, top_n: int = 5) -> dict:
    """
    Get comprehensive traffic analytics using optimized single-pass queries.
    Args:
        target_date: The date to analyze
        top_n: Number of top locations to return
    Returns:
        Dictionary containing all query results
    """
    results = {}

    try:
        # Single comprehensive query for multiple analytics
        comprehensive_query = """
        WITH daily_stats AS (
            SELECT 
                timestamp,
                camera_name,
                count,
                location,
                direction,
                day_of_week,
                is_holiday,
                EXTRACT(HOUR FROM timestamp)::INTEGER AS hour
            FROM camera_traffic
            WHERE DATE(timestamp) = :target_date
        ),
        basic_stats AS (
            SELECT 
                ROUND(AVG(count::NUMERIC), 2) AS avg_count,
                MAX(count) AS max_count,
                SUM(count) AS total_count,
                COUNT(*) AS record_count
            FROM daily_stats
        ),
        location_direction_stats AS (
            SELECT 
                location,
                direction,
                SUM(count) AS total,
                ROUND(AVG(count::NUMERIC), 2) AS average
            FROM daily_stats
            GROUP BY location, direction
            ORDER BY total DESC
        ),

        hourly_stats AS (
            SELECT 
                hour,
                location,
                SUM(count) AS total_count
            FROM daily_stats
            GROUP BY hour, location
            ORDER BY hour, total_count DESC
        ),
        top_locations AS (
            SELECT 
                location,
                SUM(count) AS total_count,
                ROUND(AVG(count::NUMERIC), 2) AS avg_count,
                MAX(count) AS max_count
            FROM daily_stats
            GROUP BY location
            ORDER BY total_count DESC
            LIMIT :top_n
        ),
        SELECT 
            'basic_stats' AS query_type,
            json_agg(basic_stats.*) AS data
        FROM basic_stats
        
        UNION ALL
        
        SELECT 
            'location_direction_analysis' AS query_type,
            json_agg(location_direction_stats.*) AS data
        FROM location_direction_stats
        
        UNION ALL
        
       
        
        SELECT 
            'hourly_aggregates' AS query_type,
            json_agg(hourly_stats.*) AS data
        FROM hourly_stats
        
        UNION ALL
        
        SELECT 
            'top_locations' AS query_type,
            json_agg(top_locations.*) AS data
        FROM top_locations
        
   
        """

        # Execute comprehensive query
        comprehensive_results = await execute_query(
            comprehensive_query, {"target_date": target_date, "top_n": top_n}
        )

        # Process results into organized dictionary
        for row in comprehensive_results:
            query_type = row["query_type"]
            data = row["data"]

            if query_type == "basic_stats" and data:
                results["daily_statistics"] = data[0]
            else:
                results[query_type] = data if data else []

        # Get detailed daily data separately (for memory efficiency)
        daily_data = await get_traffic_by_date(target_date)
        results["daily_traffic_data"] = daily_data if daily_data else None

        return results

    except ValueError as e:
        logger.debug(f"Error in get_traffic_analytics: {e}")
        return {}


async def get_traffic_summary(target_date: datetime) -> dict:
    """
    Get a quick traffic summary - ultra-optimized single query
    """
    try:
        query = """
    SELECT 
        COUNT(*) AS total_records,
        SUM(count) AS total_traffic,
        ROUND(AVG(count::NUMERIC), 2) AS avg_traffic,
        MAX(count) AS peak_traffic,
        COUNT(DISTINCT location) AS unique_locations,
        COUNT(DISTINCT camera_name) AS active_cameras,
    FROM camera_traffic
    WHERE DATE(timestamp) = :target_date;
    """

        result = await execute_query(query, {"target_date": target_date})
        return result[0]
    except ValueError as e:
        logger.debug(f"Results misisng for the date due to {e}")
        return {}
