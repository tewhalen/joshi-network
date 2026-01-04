"""Priority calculation logic for scraping work queue.

Priority scale: 0-100, where lower numbers = higher priority.
"""

import time

# Priority constants (0-100 scale, lower = higher priority)
PRIORITY_URGENT = 1  # Missing wrestler profiles
PRIORITY_HIGH = 10  # Current year matches, stale female profiles
PRIORITY_NORMAL = 30  # Previous year matches, stale non-female profiles
PRIORITY_LOW = 50  # Historical matches (base)


def is_year_transition_period() -> bool:
    """Check if we're in early January (first 2 weeks).

    During this period, previous year data is prioritized over current year
    since current year has minimal data but previous year can be finalized.
    """
    current = time.localtime()
    return current.tm_mon == 1 and current.tm_mday <= 14


def adjust_priority_by_importance(base_priority: int, importance: float) -> int:
    """Adjust priority based on wrestler importance.

    More important wrestlers get better (lower) priority.

    Args:
        base_priority: Starting priority value (0-100)
        importance: Wrestler importance score (0.0-1.0)

    Returns:
        Adjusted priority (minimum 1)

    Adjustment range: -5 to 0 (subtract up to 5 from base priority).
    """
    adjustment = int(importance * 5)  # 0-5 point boost
    return max(1, base_priority - adjustment)  # Ensure priority stays >= 1


def calculate_missing_wrestler_priority(n_opponents: int) -> int:
    """Calculate priority for a missing wrestler based on their network size.

    Args:
        n_opponents: Number of unique opponents/connections

    Returns:
        Priority value (1-40 range)
    """
    if n_opponents >= 20:
        # Very connected wrestler
        return PRIORITY_URGENT
    elif n_opponents >= 10:
        return PRIORITY_HIGH
    else:
        # Less connected - lower priority, scaled by connections
        return PRIORITY_NORMAL + 10 - n_opponents


def get_profile_refresh_priority(is_female: bool) -> int:
    """Get priority for refreshing a stale wrestler profile.

    Args:
        is_female: Whether the wrestler is female

    Returns:
        Priority value (HIGH for female, NORMAL for non-female)
    """
    return PRIORITY_HIGH if is_female else PRIORITY_NORMAL


def get_match_refresh_priority(
    year: int, current_year: int, is_active: bool, importance: float = 0.0
) -> int:
    """Calculate priority for refreshing match data for a specific year.

    Args:
        year: The year to refresh
        current_year: The current year
        is_active: Whether the wrestler is recently active
        importance: Wrestler importance score (0.0-1.0)

    Returns:
        Priority value, adjusted for year and importance

    Priority logic:
    - During year transition (early January):
        - Previous year: HIGH (finalize complete dataset)
        - Current year: LOW (minimal data exists)
    - Normal period:
        - Current year: HIGH (keep current data fresh)
        - Previous year: NORMAL
    - Historical years: LOW+ (increases with age)
    """
    in_transition = is_year_transition_period()

    if year == current_year:
        # Current year
        if not is_active:
            # Skip inactive wrestlers for current year
            return 999  # Very low priority (effectively skip)
        base = PRIORITY_LOW if in_transition else PRIORITY_HIGH
        return adjust_priority_by_importance(base, importance)

    elif year == current_year - 1:
        # Previous year
        if in_transition:
            # Boost priority during transition to finalize previous year
            return adjust_priority_by_importance(PRIORITY_HIGH, importance)
        else:
            return PRIORITY_NORMAL

    else:
        # Historical years - priority increases with age
        years_ago = current_year - year
        base = PRIORITY_LOW + years_ago
        return min(99, base)  # Cap at 99


def get_gender_diverse_match_priority(
    year: int, current_year: int, importance: float = 0.0
) -> int:
    """Get priority for gender-diverse wrestler match refresh.

    Gender-diverse wrestlers always get current year checks regardless of
    activity, since their imputed gender depends on opponent data.

    Args:
        year: The year to refresh
        current_year: The current year
        importance: Wrestler importance score (0.0-1.0)

    Returns:
        Priority value
    """
    in_transition = is_year_transition_period()
    base = PRIORITY_LOW if in_transition else PRIORITY_HIGH
    return adjust_priority_by_importance(base, importance)
