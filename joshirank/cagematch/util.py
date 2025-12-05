"""Utility functions for CageMatch data processing."""

import datetime


def remove_colon(text: str) -> str:
    return text.strip().strip(":").strip()


def parse_cm_date(date_str: str) -> datetime.date:
    """Parse a CageMatch date string (DD.MM.YYYY) into a datetime.date object."""

    return datetime.datetime.strptime(date_str, "%d.%m.%Y").date()
