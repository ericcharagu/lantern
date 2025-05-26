from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, String, DateTime, Numeric, Boolean
from datetime import datetime, date
from dotenv import load_dotenv
import os
from loguru import logger
from typing import Any

# Define logger path
logger.add("./logs/db.log", rotation="700 MB")
load_dotenv()

# Database connection
DATABASE_NAME = os.getenv("DB_HOST", "postgres")
DATABASE_USER = os.getenv("DB_USER", "postgres")
DATABASE_PASSWORD = os.getenv("POSTGRESS_PASSWORD_FILE")
DATABASE_PORT = os.getenv("DB_PORT", "5432")
DATABASE_URL = (
    f"postgresql://{DATABASE_USER}:{DATABASE_PASSWORD}@postgres:5432/{DATABASE_NAME}"
)


def get_connection_string():
    with open("/run/secrets/postgres_secrets", "r") as f:
        password = f.read().strip()

    return f"postgresql://{os.getenv('DB_USER', 'postgres')}:{password}@{os.getenv('DB_HOST', 'postgres')}:{os.getenv('DB_PORT', 5432)}/{os.getenv('DB_NAME', 'postgres')}"


engine = create_engine(get_connection_string(), pool_pre_ping=True, pool_recycle=300)
Session = sessionmaker(bind=engine)
Base = declarative_base()


class CameraTraffic(Base):
    __tablename__ = "camera_traffic"
    id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime(timezone=True))
    camera_name = Column(String(50))
    count = Column(Integer)
    location = Column(String(50))
    direction = Column(String(10))
    weather = Column(String(20))
    temperature = Column(Numeric(5, 2))
    day_of_week = Column(String(10))
    is_holiday = Column(Boolean)


def execute_query(query: str, params: dict) -> list:
    """Execute a query and return results as list of dictionaries"""
    try:
        with engine.connect() as conn:
            result = conn.execute(text(query), params or {})
            columns = result.keys()
            return [dict(zip(columns, row)) for row in result.fetchall()]
    except Exception as e:
        logger.error(f"Query execution failed: {e}")
        return []


def get_traffic_by_date(target_date: Any) -> list:
    """Get all traffic records for a specific date - optimized query"""
    query = """
    SELECT 
        timestamp,
        camera_name,
        count,
        location,
        direction,
        weather,
        temperature,
        day_of_week,
        is_holiday
    FROM camera_traffic
    WHERE DATE(timestamp) = :target_date
    ORDER BY count DESC;
    """
    return execute_query(query, {"target_date": target_date})


def get_hourly_counts_sorted(target_date: Any) -> list:
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
    return execute_query(query, {"target_date": target_date.date()})


def get_top_locations(target_date: Any, n: int = 5) -> list:
    """Get top n locations by total count - optimized aggregation"""
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
    return execute_query(query, {"target_date": target_date.date(), "limit_n": n})


def get_traffic_analytics(target_date: datetime, top_n: int = 5) -> dict:
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
                weather,
                temperature,
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
        weather_stats AS (
            SELECT 
                weather,
                ROUND(AVG(count::NUMERIC), 2) AS avg_count,
                SUM(count) AS total_count
            FROM daily_stats
            GROUP BY weather
            ORDER BY total_count DESC
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
        correlation_data AS (
            SELECT 
                CORR(count, temperature) AS count_temp_correlation
            FROM daily_stats
            WHERE temperature IS NOT NULL
        )
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
            'weather_impact_analysis' AS query_type,
            json_agg(weather_stats.*) AS data
        FROM weather_stats
        
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
        
        UNION ALL
        
        SELECT 
            'temperature_correlation' AS query_type,
            json_agg(correlation_data.*) AS data
        FROM correlation_data;
        """

        # Execute comprehensive query
        comprehensive_results = execute_query(
            comprehensive_query, {"target_date": target_date, "top_n": top_n}
        )

        # Process results into organized dictionary
        for row in comprehensive_results:
            query_type = row["query_type"]
            data = row["data"]

            if query_type == "basic_stats" and data:
                results["daily_statistics"] = data[0]
            elif query_type == "temperature_correlation" and data:
                results["temperature_correlation"] = data[0]
            else:
                results[query_type] = data if data else []

        # Get detailed daily data separately (for memory efficiency)
        daily_data = get_traffic_by_date(target_date)
        results["daily_traffic_data"] = daily_data if daily_data else None

        return results

    except ValueError as e:
        logger.debug(f"Error in get_traffic_analytics: {e}")


def get_traffic_summary(target_date: datetime) -> dict:
    """
    Get a quick traffic summary - ultra-optimized single query
    """
    query = """
    SELECT 
        COUNT(*) AS total_records,
        SUM(count) AS total_traffic,
        ROUND(AVG(count::NUMERIC), 2) AS avg_traffic,
        MAX(count) AS peak_traffic,
        COUNT(DISTINCT location) AS unique_locations,
        COUNT(DISTINCT camera_name) AS active_cameras,
        json_agg(DISTINCT weather) AS weather_conditions
    FROM camera_traffic
    WHERE DATE(timestamp) = :target_date;
    """

    result = execute_query(query, {"target_date": target_date})
    return result[0] if result else {}


# Example usage:
# target_date = datetime(2024, 1, 15)
# analytics = get_traffic_analytics(target_date)
# summary = get_traffic_summary(target_date)
# print("Analytics:", analytics)
# print("Summary:", summary)
