# services/nightly_report_service.py
import asyncio
from datetime import datetime, time, timedelta
from typing import List, Dict, Any
import uuid
import pytz
from dependencies import valkey_client
from sqlalchemy import select, func, and_
from loguru import logger

from config import settings
from utils.whatsapp.whatsapp import whatsapp_messenger
from utils.db.base import AsyncSessionLocal, DetectionLog
from utils.timezone import nairobi_tz
# Add a logger for this service
logger.add("logs/nightly_reporter.log", rotation="1 week", level="INFO")

async def _acquire_lock(lock_key: str) -> bool:
    """
    Tries to acquire a lock by setting a key in Valkey if it does not exist.
    The key is set with a 25-hour TTL to automatically expire.
    This operation is atomic.

    Args:
        lock_key: The unique key for the daily lock.

    Returns:
        True if the lock was acquired, False otherwise.
    """
    was_set = await valkey_client.set(lock_key, "locked", ex=90000, nx=True)
    return was_set == 0
async def get_nightly_activity_summary() -> list[dict[str, Any]]:
    """
    Queries the database for a summary of each unique person tracked during the night.

    Returns:
        A list of dictionaries, each summarizing a unique tracker's activity.
    """
    async with AsyncSessionLocal() as session:
        now_nairobi = datetime.now(nairobi_tz)
        today_date = now_nairobi.date()
        yesterday_date = today_date - timedelta(days=1)

        # Define the time window in Nairobi time and convert to UTC for the query
        start_time_nairobi = nairobi_tz.localize(datetime.combine(yesterday_date, time(hour=settings.NIGHT_CAPTURE_START_HOUR,minute=settings.NIGHT_CAPTURE_START_MINUTE)))
        end_time_nairobi = nairobi_tz.localize(datetime.combine(today_date, time(hour=settings.NIGHT_CAPTURE_END_HOUR, minute=settings.NIGHT_CAPTURE_END_MINUTE)))
        start_time_utc = start_time_nairobi.astimezone(pytz.utc)
        end_time_utc = end_time_nairobi.astimezone(pytz.utc)

        logger.info(f"Querying for activity between {start_time_utc} (UTC) and {end_time_utc} (UTC).")

        # CTE to find the first appearance (camera and timestamp) for each tracker_id
        first_appearance_cte = (
            select(
                DetectionLog.tracker_id,
                DetectionLog.camera_name.label("first_camera"),
                func.row_number().over(
                    partition_by=DetectionLog.tracker_id,
                    order_by=DetectionLog.timestamp.asc()
                ).label("rn")
            )
            .where(
                DetectionLog.object_name == 'person',
                DetectionLog.timestamp.between(start_time_utc, end_time_utc),
                DetectionLog.tracker_id.isnot(None)
            )
            .cte("first_appearance")
        )

        # Main query to aggregate data, joining with the CTE to get the first camera
        stmt = (
            select(
                DetectionLog.tracker_id,
                func.min(DetectionLog.timestamp).label("first_seen"),
                func.max(DetectionLog.timestamp).label("last_seen"),
                func.count(DetectionLog.id).label("detection_count"),
                func.max(first_appearance_cte.c.first_camera).label("first_camera")
            )
            .join(
                first_appearance_cte,
                and_(
                    DetectionLog.tracker_id == first_appearance_cte.c.tracker_id,
                    first_appearance_cte.c.rn == 1
                )
            )
            .where(
                DetectionLog.object_name == 'person',
                DetectionLog.timestamp.between(start_time_utc, end_time_utc)
            )
            .group_by(DetectionLog.tracker_id)
            .order_by(func.min(DetectionLog.timestamp).asc())
        )

        result = await session.execute(stmt)
        activity_summary = result.mappings().all()
        logger.info(f"Found {len(activity_summary)} unique individuals during the night.")
        return activity_summary

def format_report_message(activity_summary: list[dict[str, Any]], report_date_str: str) -> str:
    """Formats the structured activity data into a human-readable string for WhatsApp."""
    total_individuals = len(activity_summary)
    
    # Start with the header and overall summary
    header = (
        f"--- Nightly Security Report ---\n"
        f"Date: {report_date_str}\n\n"
        f"Summary: *{total_individuals}* unique individuals were detected between 10:00 PM and 4:50 AM.\n"
    )

    if not activity_summary:
        return header + "\nNo human activity detected during this period."

    # Build the detailed list of events
    details = ["\n*Timeline of First Detections:*"]
    
    # Limit the report details to avoid excessively long messages
    max_details = 10
    for i, activity in enumerate(activity_summary[:max_details]):
        first_seen_utc = activity["first_seen"]
        # Convert UTC timestamp from DB to Nairobi time for the report
        first_seen_nairobi = first_seen_utc.astimezone(nairobi_tz)
        time_str = first_seen_nairobi.strftime("%I:%M %p") # e.g., 11:34 PM

        details.append(
            f"- *{time_str}*: Person (ID: {activity['tracker_id']}) first spotted at *{activity['first_camera']}*."
        )

    if total_individuals > max_details:
        details.append(f"\n...and {total_individuals - max_details} other individuals.")

    footer = "\n\nThis is an automated message from the Lantern Security System."
    
    return header + "\n".join(details) + footer

async def nightly_report_task():
    """
    A long-running task that wakes up at 5 AM Nairobi time every day to send the report.
    """
    while True:
        now_nairobi: datetime = datetime.now(nairobi_tz)
        target_time: datetime = now_nairobi.replace(hour=settings.SEND_NIGHT_REPORT_HOUR, minute=settings.SEND_NIGHT_REPORT_MINUTE, second=0, microsecond=0)
        if now_nairobi > target_time:
            target_time += timedelta(days=1)
        
        sleep_duration: float = (target_time - now_nairobi).total_seconds()
        logger.info(f"Nightly reporter sleeping for {sleep_duration / 3600:.2f} hours. Will run at {target_time}.")
        await asyncio.sleep(sleep_duration)

        try:
            logger.info("Waking up to generate and send the nightly report.")
            report_date = (datetime.now(nairobi_tz) - timedelta(days=1))
            lock_key = f"nightly_report_lock:{report_date.strftime('%Y-%m-%d')}"
            # --- LOCKING MECHANISM ---
            if not await _acquire_lock(lock_key):
                logger.warning(f"Could not acquire lock for {lock_key}. Report for this day has likely already been sent. Skipping.")
                # Sleep for a minute to avoid a tight loop if something is wrong
                await asyncio.sleep(60)
                continue
            
            # --- PROCEED WITH SENDING REPORT (LOCK ACQUIRED) ---
            logger.info(f"Lock acquired for {lock_key}. Generating and sending the nightly report.")
            if not settings.NIGHTLY_REPORT_RECIPIENT_NUMBER:
                logger.error("NIGHTLY_REPORT_RECIPIENT_NUMBER is not set in .env. Cannot send WhatsApp report.")
                await asyncio.sleep(60)
                continue

            # 1. Get the structured activity data from the database
            activity_summary = await get_nightly_activity_summary()
            
            # 2. Format the data into a message
            report_date = (datetime.now(nairobi_tz) - timedelta(days=1)).strftime("%A, %d %B %Y")
            report_message = format_report_message(activity_summary, report_date)
            
            # 3. Send the message
            for number in settings.NIGHTLY_REPORT_RECIPIENT_NUMBER:
                try:
                    whatsapp_messenger(
                        llm_text_output=report_message,
                        recipient_number=number.strip() # .strip() to remove any whitespace
                    )
                    logger.success(f"Successfully sent nightly report to {number}.")
                except Exception as e:
                    logger.error(f"Failed to send report to {number}. Error: {e}")
            
        except Exception as e:
            logger.error(f"Failed to run nightly report task: {e}", exc_info=True)
            await asyncio.sleep(60)