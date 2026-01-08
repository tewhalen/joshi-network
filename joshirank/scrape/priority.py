"""Priority calculation logic for scraping work queue.

Priority scale: 0-100, where lower numbers = higher priority.
"""

import time

from joshirank.analysis.gender import guess_gender_of_wrestler

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


def calculate_missing_wrestler_priority(
    n_opponents: int,
    wrestler_id: int = None,
    wrestler_db=None,
    opponent_ids: set[int] = None,
) -> int:
    """Calculate priority for a missing wrestler based on network size and gender prediction.

    Uses statistical gender prediction (guess_gender_of_wrestler) to prioritize
    likely female wrestlers over likely male wrestlers. This ensures scraping
    resources are focused on Joshi wrestlers first.

    Args:
        n_opponents: Number of unique opponents/connections
        wrestler_id: ID of the missing wrestler (for gender prediction)
        wrestler_db: Database instance (for gender prediction)
        opponent_ids: Set of opponent wrestler IDs (used for fallback)

    Returns:
        Priority value (1-99 range)

    Priority logic with gender prediction:
    - Confidence >= 0.95 (very confident female): URGENT priority
      - 20+ opponents: 1-3
      - 10+ opponents: 5-8
      - 5+ opponents: 10-15
    - Confidence >= 0.75 (likely female): HIGH priority
      - 20+ opponents: 10-12
      - 10+ opponents: 15-18
      - 5+ opponents: 20-25
    - Confidence 0.5-0.75 (uncertain): NORMAL priority
      - Base on opponent count: 30-60
    - Confidence < 0.3 (likely male): LOW priority
      - Heavily deprioritized: 70-95
    """
    # Base priority from opponent count (classic tier system)
    if n_opponents >= 20:
        base_priority = PRIORITY_URGENT
    elif n_opponents >= 10:
        base_priority = PRIORITY_HIGH
    elif n_opponents >= 5:
        base_priority = PRIORITY_NORMAL
    elif n_opponents >= 3:
        base_priority = 60 + (4 - n_opponents)  # 60-62
    else:
        base_priority = 90 + (2 - n_opponents)  # 90-92

    # If we have database access, use sophisticated gender prediction
    if wrestler_id:
        try:
            # Get cached or calculated confidence score
            confidence = guess_gender_of_wrestler(wrestler_id)

            # Apply gender-based priority adjustments
            # For wrestlers with very few opponents, keep priority below NORMAL
            # even if we're confident they're female (insufficient data)
            if n_opponents < 5:
                # Keep below NORMAL (>30) regardless of gender confidence
                if confidence >= 0.75:
                    # Likely female but few opponents
                    return max(40, base_priority)  # 40-92 range
                else:
                    # Not confident female + few opponents
                    return base_priority  # Use base (60-92 range)

            # For wrestlers with sufficient opponents, apply full gender-based priority
            if confidence >= 0.95:
                # Very confident female (100% precision thresholds)
                # Strongest boost - these are almost certainly Joshi wrestlers
                if n_opponents >= 20:
                    return 1 + min(int((1.0 - confidence) * 20), 2)  # 1-3
                elif n_opponents >= 10:
                    return 5 + min(int((1.0 - confidence) * 30), 3)  # 5-8
                else:  # 5-9 opponents
                    return 10 + min(int((1.0 - confidence) * 50), 5)  # 10-15

            elif confidence >= 0.75:
                # Likely female (high confidence)
                # Moderate boost
                if n_opponents >= 20:
                    return 10 + int((0.95 - confidence) * 10)  # 10-12
                elif n_opponents >= 10:
                    return 15 + int((0.95 - confidence) * 15)  # 15-18
                else:  # 5-9 opponents
                    return 20 + int((0.95 - confidence) * 25)  # 20-25

            elif confidence >= 0.5:
                # Uncertain or slightly female-leaning
                # Use base priority with minor adjustment
                return base_priority

            elif confidence >= 0.3:
                # Likely male
                # Deprioritize moderately (fixed floor of 70)
                return max(70, min(95, base_priority + 20))

            else:
                # Very likely male (confidence < 0.3)
                # Heavily deprioritize (fixed floor of 80)
                return max(80, min(98, base_priority + 40))

        except Exception:
            # If gender prediction fails, fall back to base priority
            # This ensures scraping continues even if prediction breaks
            pass

    # No match data or prediction unavailable - use base priority
    return base_priority


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
        base = 90 if in_transition else PRIORITY_HIGH
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
