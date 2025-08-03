from datetime import date, datetime, timezone
from loguru import logger
from utils.timezone import nairobi_tz

logger.add("./logs/holiday_checker.log", rotation="1 week")


def calculate_easter(year):
    """Calculates Easter date for a given year using Gauss's algorithm"""
    a = year % 19
    b = year // 100
    c = year % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = ((h + l - 7 * m + 114) % 31) + 1
    return date(year, month, day)


def get_kenyan_holidays(year=None):
    """Returns all Kenyan holidays for a given year"""
    if year is None:
        year = date.today().year

    easter = calculate_easter(year)

    holidays = {
        "January": [{"date": 1, "name": "New Year's Day"}],
        "February": [],
        "March": [],
        "April": [
            {"date": easter.day - 2, "name": "Good Friday"},
            {"date": easter.day + 1, "name": "Easter Monday"},
        ],
        "May": [{"date": 1, "name": "Labour Day"}],
        "June": [{"date": 1, "name": "Madaraka Day"}],
        "July": [],
        "August": [],
        "September": [],
        "October": [
            {"date": 10, "name": "Huduma Day"},
            {"date": 20, "name": "Mashujaa Day"},
        ],
        "November": [],
        "December": [
            {"date": 12, "name": "Jamhuri Day"},
            {"date": 25, "name": "Christmas Day"},
            {"date": 26, "name": "Boxing Day"},
        ],
    }

    # Handle cases where Easter crosses month boundaries
    if easter.month == 3:  # March
        holidays["March"].extend(
            [
                {"date": easter.day - 2, "name": "Good Friday"},
                {"date": easter.day + 1, "name": "Easter Monday"},
            ]
        )
        holidays["April"] = []
    elif easter.month == 4:  # April (normal case)
        pass  # Already handled in default

    return holidays


# Yearly holidays
current_year = date.today().year
holidays = get_kenyan_holidays(current_year)

current_time_utc = datetime.now(nairobi_tz)
formatted_time = current_time_utc.strftime("%Y-%m-%dT%H:%M:%SZ")


@logger.catch()
def holiday_checker(
    date_string: str = formatted_time, holidays: dict = holidays
) -> bool:
    """
    Convert the string datetime into actual dates and check if date is in holiday list
    """

    # Parse ISO format (handles 'Z' timezone)
    dt = datetime.fromisoformat(date_string.replace("Z", "+00:00"))
    month = dt.strftime("%B")  # Full month name (e.g., "January")
    day = dt.day

    # Check if month exists in holidays
    if month in holidays:
        for holiday in holidays[month]:
            if holiday["date"] == day:
                return True
    return False


"""
# Example usage:
if __name__ == "__main__":
    # Holiday example
    holiday_checker("2024-12-25T23:59:59Z", holidays)

    # Not a holiday
    holiday_checker"2024-01-15T09:00:00Z", holidays)
"""
