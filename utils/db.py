from sqlalchemy import create_engine, func, extract
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, String, DateTime, Numeric, Boolean
from datetime import datetime, date
import polars as pl
from dotenv import load_dotenv
import os
from loguru import logger

# Define logger path
logger.add("./logs/db.log", rotation="700 MB")
load_dotenv()

# Database connection
DATABASE_NAME = os.getenv("DATABASE_NAME")
DATABASE_USER = os.getenv("DATABASE_USER")
DATABASE_PASSWORD = os.getenv("DATABASE_PASSWORD")
DATABASE_URL = (
    "postgresql://DATABASE_USER:DATABASE_PASSWORD@localhost:5432/DATABASE_NAME"
)
engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)
session = Session()

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


def get_traffic_by_date(target_date: datetime) -> pl.DataFrame:
    """Get all traffic records for a specific date using Polars"""
    try:
        query = f"""
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
    WHERE timestamp::date = '{target_date.date()}'
    ORDER BY count DESC
    """
        return pl.read_database(query, engine.connect())
    except ValueError as e:
        logger.debug(f"failed to get traffic by date {e}")


def get_hourly_counts_sorted(target_date: datetime) -> pl.DataFrame:
    """Get hourly aggregated counts using Polars"""
    query = f"""
    SELECT 
        EXTRACT(HOUR FROM timestamp)::int AS hour,
        location,
        SUM(count) AS total_count
    FROM camera_traffic
    WHERE timestamp::date = '{target_date.date()}'
    GROUP BY hour, location
    ORDER BY hour, total_count DESC
    """
    return pl.read_database(query, engine.connect())


def get_top_locations(target_date: datetime, n: int = 5) -> pl.DataFrame:
    """Get top n locations by total count using Polars"""
    query = f"""
    SELECT 
        location,
        SUM(count) AS total_count,
        AVG(count) AS avg_count,
        MAX(count) AS max_count
    FROM camera_traffic
    WHERE timestamp::date = '{target_date.date()}'
    GROUP BY location
    ORDER BY total_count DESC
    LIMIT {n}
    """
    return pl.read_database(query, engine.connect())


def get_traffic_analytics(target_date: datetime, top_n: int = 5) -> dict:
    """
    Combine all traffic analytics queries into a single function and return results as a dictionary.

    Args:
        target_date: The date to analyze
        top_n: Number of top locations to return

    Returns:
        Dictionary containing all query results with descriptive keys
    """
    results = {}

    try:
        # Get all records for the day
        daily_data = get_traffic_by_date(target_date)
        results["daily_traffic_data"] = (
            daily_data.to_dicts() if not daily_data.is_empty() else None
        )

        # Get hourly aggregates
        hourly_data = get_hourly_counts_sorted(target_date)
        results["hourly_aggregates"] = (
            hourly_data.to_dicts() if not hourly_data.is_empty() else None
        )

        # Get top locations
        top_locations = get_top_locations(target_date, top_n)
        results["top_locations"] = (
            top_locations.to_dicts() if not top_locations.is_empty() else None
        )

        # Additional Polars analysis
        if not daily_data.is_empty():
            # Calculate basic statistics
            stats = daily_data.select(
                [
                    pl.col("count").mean().alias("avg_count"),
                    pl.col("count").max().alias("max_count"),
                    pl.col("count").sum().alias("total_count"),
                ]
            )
            results["daily_statistics"] = stats.to_dicts()[0]

            # Group by location and direction
            location_stats = (
                daily_data.group_by(["location", "direction"])
                .agg(
                    pl.col("count").sum().alias("total"),
                    pl.col("count").mean().alias("average"),
                )
                .sort("total", descending=True)
            )
            results["location_direction_analysis"] = location_stats.to_dicts()

            # Additional analysis: Weather impact
            weather_impact = (
                daily_data.group_by("weather")
                .agg(
                    pl.col("count").mean().alias("avg_count"),
                    pl.col("count").sum().alias("total_count"),
                )
                .sort("total_count", descending=True)
            )
            results["weather_impact_analysis"] = weather_impact.to_dicts()

            # Additional analysis: Temperature correlation
            temp_correlation = daily_data.select(
                pl.corr("count", "temperature").alias("count_temp_correlation")
            )
            results["temperature_correlation"] = temp_correlation.to_dicts()[0]

        return results

    except ValueError as e:
        logger.debug(f"Error in get_traffic_analytics: {e}")


# Get all records for the day
# print(get_traffic_analytics(target_date))
"""
daily_data = get_traffic_by_date(target_date)
print("Daily Data:")
print(daily_data)

# Get hourly aggregates
hourly_data = get_hourly_counts_sorted(target_date)
print("\nHourly Aggregates:")
print(hourly_data)

# Get top locations
top_locations = get_top_locations(target_date, 3)
print("\nTop 3 Locations:")
print(top_locations)

# Additional Polars analysis examples
if not daily_data.is_empty():
    # Calculate basic statistics
    stats = daily_data.select(
        [
            pl.col("count").mean().alias("avg_count"),
            pl.col("count").max().alias("max_count"),
            pl.col("count").sum().alias("total_count"),
        ]
    )
    print("\nDaily Statistics:")
    print(stats)

    # Group by location and direction
    location_stats = (
        daily_data.group_by(["location", "direction"])
        .agg(
            pl.col("count").sum().alias("total"),
            pl.col("count").mean().alias("average"),
        )
        .sort("total", descending=True)
    )
    print("\nLocation/Direction Analysis:")
    print(location_stats)
"""
