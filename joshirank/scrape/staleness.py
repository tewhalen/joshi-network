"""Staleness policy for determining when wrestler data needs updating."""

import time


class StalenessPolicy:
    """Define staleness thresholds for different types of wrestler data."""

    # Time constants in seconds
    DAY = 86400
    DAYS_14 = 14 * DAY
    DAYS_90 = 90 * DAY
    DAYS_180 = 180 * DAY
    DAYS_365 = 365 * DAY

    def __init__(self, current_year: int = 2026):
        self.current_year = current_year

    def profile_is_stale(self, timestamp: float, is_female: bool) -> bool:
        """Check if a wrestler profile needs updating.

        Female wrestlers: 90 days
        Non-female wrestlers: 365 days
        """
        if timestamp == 0:
            return True

        age = time.time() - timestamp
        threshold = self.DAYS_90 if is_female else self.DAYS_365
        return age > threshold

    def matches_are_stale(
        self, timestamp: float, year: int, is_female: bool, is_active: bool = True
    ) -> bool:
        """Check if match data for a specific year needs updating.

        Current year (2026):
            Active female: 14 days
            Inactive female: Never (they're retired)
            Non-female: Never update
        Previous year (2025):
            Female: 90 days
            Non-female: Never update
        Historical (2024 and earlier):
            Active female: 180 days
            Inactive female: 365 days (check yearly)
            Non-female: Never update
        """
        # Only update matches for female wrestlers
        if not is_female:
            return False

        if timestamp == 0:
            return True

        age = time.time() - timestamp

        if year == self.current_year:
            # Current year: only update for active wrestlers
            if not is_active:
                return False  # Skip retired/inactive wrestlers
            return age > self.DAYS_14
        elif year == self.current_year - 1:
            # Previous year: update every 90 days
            return age > self.DAYS_90
        else:
            # Historical years: longer refresh cycle for inactive wrestlers
            threshold = self.DAYS_180 if is_active else self.DAYS_365
            return age > threshold

    def promotion_is_stale(self, timestamp: float) -> bool:
        """Check if promotion data needs updating.

        Promotions are updated very infrequently (365 days).
        """
        if timestamp == 0:
            return True

        age = time.time() - timestamp
        return age > self.DAYS_365

    def match_priority(self, year: int, is_female: bool, is_active: bool = True) -> int:
        """Calculate priority for match updates based on year and activity.

        Returns priority on 0-100 scale where lower = higher priority.
        Inactive wrestlers get lower priority for all years.
        """
        if not is_female:
            return 99  # Very low priority for non-female wrestlers

        # Inactive wrestlers get lower priority
        if not is_active:
            if year == self.current_year:
                return 99  # Never check current year for inactive
            elif year >= self.current_year - 2:
                return 80  # Low priority for recent years
            else:
                return 80 + min(
                    self.current_year - year, 19
                )  # Very low priority for historical (max 99)

        # Active wrestlers
        if year == self.current_year:
            return 10  # HIGH priority
        elif year == self.current_year - 1:
            return 30  # NORMAL priority
        else:
            # Lower priority as we go further back (50-99)
            years_ago = self.current_year - year
            return min(50 + years_ago, 99)  # LOW to LOWER priority (cap at 99)
