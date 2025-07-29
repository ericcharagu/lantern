# services/nightly_report_service.py
#from pytz import _UTCclass


#from pytz.tzinfo import DstTzInfo, StaticTzInfo
from pytz.tzinfo import BaseTzInfo

import asyncio
import os
import json
from datetime import datetime, time, timedelta, timezone
from loguru import logger

from config import settings
from utils.whatsapp.whatsapp import whatsapp_messenger
import pytz

# Add a logger for this service
logger.add("logs/nightly_reporter.log", rotation="1 week", level="INFO")
#nbo_time: _UTCclass | StaticTzInfo | DstTzInfo=pytz.timezone("Africa/Nairobi") 
nbo_time: BaseTzInfo = pytz.timezone("Africa/Nairobi")

def count_nightly_detections() -> int:
    """
    Reads detection logs and counts human detections between 10 PM of the previous day
    and 4:50 AM of the current day.
    """
    today = datetime.now(nbo_time)
    yesterday = today - timedelta(days=1)
    
    # Define the time window for the report
    # Start: Yesterday at 22:00:00 UTC
    # End: Today at 04:50:00 UTC
    start_time = datetime.combine(yesterday.date(), time(22, 0), tzinfo=timezone.utc)
    end_time = datetime.combine(today.date(), time(4, 50), tzinfo=timezone.utc)
    
    # Log files to check: yesterday's and today's
    log_files_to_check = [
        f"logs/detections/{yesterday.strftime('%Y-%m-%d')}.log",
        f"logs/detections/{today.strftime('%Y-%m-%d')}.log"
    ]
    
    total_nightly_detections = 0
    
    for log_file_path in log_files_to_check:
        if not os.path.exists(log_file_path):
            logger.info(f"Detection log file not found, skipping: {log_file_path}")
            continue

        with open(log_file_path, 'r') as f:
            for line in f:
                try:
                    log_entry = json.loads(line)
                    timestamp_str = log_entry.get("timestamp")
                    human_count = log_entry.get("human_count", 0)

                    if not timestamp_str or human_count == 0:
                        continue

                    log_time_utc = datetime.fromisoformat(timestamp_str)

                    # Check if the log entry is within our night window
                    if start_time<= log_time_utc < end_time:
                        total_nightly_detections += human_count
                except (json.JSONDecodeError, KeyError, TypeError) as e:
                    logger.error(f"Skipping malformed log line in {log_file_path}: {line.strip()}. Error: {e}")
    
    report_date_str = yesterday.strftime("%d %b %Y")
    logger.info(f"Counted {total_nightly_detections} human detections for the night of {report_date_str}.")
    return total_nightly_detections

async def nightly_report_task():
    """
    A long-running task that wakes up at 5 AM UTC every day to send the report.
    """
    while True:
        now: datetime = datetime.now(nbo_time)

        target_time: datetime = now.replace(hour=5, minute=0, second=0, microsecond=0)
        if now > target_time:
            target_time += timedelta(days=1)
        
        sleep_duration = (target_time - now).total_seconds()
        logger.info(f"Nightly reporter sleeping for {sleep_duration / 3600:.2f} hours. Will run at {target_time}.")
        await asyncio.sleep(sleep_duration)

        # It's 5 AM, time to run the report
        try:
            logger.info("Waking up to generate and send the nightly report.")
            
            if not settings.NIGHTLY_REPORT_RECIPIENT_NUMBER:
                logger.error("NIGHTLY_REPORT_RECIPIENT_NUMBER is not set in .env. Cannot send WhatsApp report.")
                await asyncio.sleep(60)
                continue

            count = count_nightly_detections()
            
            report_date = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%A, %d %B %Y")
            
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