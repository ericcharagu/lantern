# utils/timezone.py
import pytz
from loguru import logger

def get_nairobi_timezone():
    """
    Returns a pytz timezone object for Africa/Nairobi.
    """
    try:
        return pytz.timezone("Africa/Nairobi")
    except pytz.UnknownTimeZoneError:
        logger.error("Could not find the 'Africa/Nairobi' timezone. Defaulting to UTC.")
        return pytz.utc

# Global instance for use across the application
nairobi_tz = get_nairobi_timezone()