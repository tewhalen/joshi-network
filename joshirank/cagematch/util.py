"""Utility functions for CageMatch data processing."""

import datetime
import re


def remove_colon(text: str) -> str:
    return text.strip().strip(":").strip()


def parse_cm_date(date_str: str) -> datetime.date:
    """Parse a CageMatch date string (DD.MM.YYYY) into a datetime.date object."""
    return datetime.datetime.strptime(date_str, "%d.%m.%Y").date()


def parse_cm_date_flexible(date_str: str) -> datetime.date | None:
    """Parse a CageMatch date string in any format: DD.MM.YYYY, MM.YYYY, or YYYY.

    Tries formats in order of specificity:
    1. DD.MM.YYYY (full date) -> datetime.date(year, month, day)
    2. MM.YYYY (month-year) -> datetime.date(year, month, 1)
    3. YYYY (year only) -> datetime.date(year, 1, 1)

    Returns:
        datetime.date object with ISO format, or None if parsing fails

    Examples:
        '25.09.2001' -> datetime.date(2001, 9, 25)
        '09.2001' -> datetime.date(2001, 9, 1)
        '1987' -> datetime.date(1987, 1, 1)
        'invalid' -> None
    """
    if not date_str:
        return None

    date_str = str(date_str).strip()

    # Try DD.MM.YYYY format
    full_date_re = re.compile(r"^(\d{2})\.(\d{2})\.(\d{4})$")
    m = full_date_re.match(date_str)
    if m:
        try:
            return parse_cm_date(m.group(0))
        except ValueError:
            pass

    # Try MM.YYYY format
    month_year_re = re.compile(r"^(\d{2})\.(\d{4})$")
    m = month_year_re.match(date_str)
    if m:
        try:
            return datetime.datetime.strptime(m.group(0), "%m.%Y").date()
        except ValueError:
            pass

    # Try YYYY format (year only)
    year_only_re = re.compile(r"^(\d{4})$")
    m = year_only_re.match(date_str)
    if m:
        try:
            return datetime.datetime.strptime(m.group(0), "%Y").date()
        except ValueError:
            pass

    return None
