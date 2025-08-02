# services/nightly_report_service.py
import asyncio
from datetime import datetime, time, timedelta
from sqlalchemy import select, func, and_
from loguru import logger

from config import settings
from utils.whatsapp.whatsapp import whatsapp_messenger
from utils.db.base import AsyncSessionLocal, DetectionLog
from utils.timezone import nairobi_tz

# Add a logger for this service
logger.add("logs/nightly_reporter.log", rotation="1 week", level="INFO")

async def count_nightly_detections() -> int:
    """
    Queries the database to count human detections between 10 PM of the previous day
    and 4:50 AM of the current day in Nairobi time.
    """
    async with AsyncSessionLocal() as session:
        now_nairobi = datetime.now(nairobi_tz)
        today_date = now_nairobi.date()
        yesterday_date = today_date - timedelta(days=1)

        # Define the time window in Nairobi time
        start_time_nairobi = nairobi_tz.localize(datetime.combine(yesterday_date, time(22, 0)))
        end_time_nairobi = nairobi_tz.localize(datetime.combine(today_date, time(4, 50)))

        # Convert to UTC for database query, as timestamps are stored in UTC
        start_time_utc = start_time_nairobi.astimezone(pytz.utc)
        end_time_utc = end_time_nairobi.astimezone(pytz.utc)

        logger.info(f"Querying for detections between {start_time_utc} (UTC) and {end_time_utc} (UTC).")

        stmt = (
            select(func.count(DetectionLog.id))
            .where(
                and_(
                    DetectionLog.object_name == 'person',
                    DetectionLog.timestamp >= start_time_utc,
                    DetectionLog.timestamp < end_time_utc
                )
            )
        )

        result = await session.execute(stmt)
        count = result.scalar_one_or_none() or 0
        
        report_date_str = yesterday_date.strftime("%d %b %Y")
        logger.info(f"Counted {count} human detections for the night of {report_date_str}.")
        return count

async def nightly_report_task():
    """
    A long-running task that wakes up at 5 AM Nairobi time every day to send the report.
    """
    while True:
        now_nairobi = datetime.now(nairobi_tz)
        # Target 5:00 AM Nairobi time
        target_time = now_nairobi.replace(hour=5, minute=0, second=0, microsecond=0)
        if now_nairobi > target_time:
            target_time += timedelta(days=1)
        
        sleep_duration = (target_time - now_nairobi).total_seconds()
        logger.info(f"Nightly reporter sleeping for {sleep_duration / 3600:.2f} hours. Will run at {target_time}.")
        await asyncio.sleep(sleep_duration)

        # It's 5 AM, time to run the report
        try:
            logger.info("Waking up to generate and send the nightly report.")
            
            if not settings.NIGHTLY_REPORT_RECIPIENT_NUMBER:
                logger.error("NIGHTLY_REPORT_RECIPIENT_NUMBER is not set in .env. Cannot send WhatsApp report.")
                await asyncio.sleep(60)
                continue

            count = await count_nightly_detections()
            
            report_date = (datetime.now(nairobi_tz) - timedelta(days=1)).strftime("%A, %d %B %Y")
            
            report_message = (
                f"--- Nightly Security Report ---\n"
                f"Date: {report_date}\n\n"
                f"Total human detections between 10:00 PM and 4:50 AM: *{count}*\n\n"
                f"This is an automated message from the Lantern Security System."
            )

            whatsapp_messenger(
                llm_text_output=report_message,
                recipient_number=settings.NIGHTLY_REPORT_RECIPIENT_NUMBER
            )
            logger.success(f"Successfully sent nightly report to {settings.NIGHTLY_REPORT_RECIPIENT_NUMBER}.")
        
        except Exception as e:
            logger.error(f"Failed to run nightly report task: {e}", exc_info=True)
            await asyncio.sleep(60)