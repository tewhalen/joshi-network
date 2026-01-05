"""Specialized Queries for Joshi Network data.

This module provides high-level query functions for analyzing the Joshi wrestling
database, including promotion-based wrestler discovery.

For gender prediction functions, see joshirank.analysis.gender module.
"""


# Re-export gender functions for backwards compatibility
# These have been moved to joshirank.analysis.gender and joshirank.analysis.gender_cache
def guess_gender_of_wrestler(wrestler_id: int) -> float:
    """Guess gender of wrestler based on match patterns.

    DEPRECATED: Use joshirank.analysis.gender.guess_gender_of_wrestler instead.
    This wrapper is maintained for backwards compatibility.
    """
    from joshirank.analysis.gender import guess_gender_of_wrestler as _guess

    return _guess(wrestler_id)


def clear_gender_cache():
    """Clear all cached gender predictions.

    DEPRECATED: Use joshirank.analysis.gender_cache.clear_gender_cache instead.
    This wrapper is maintained for backwards compatibility.
    """
    from joshirank.analysis.gender_cache import clear_gender_cache as _clear

    return _clear()


def get_gender_cache_stats() -> dict:
    """Get statistics about the gender prediction cache.

    DEPRECATED: Use joshirank.analysis.gender_cache.get_gender_cache_stats instead.
    This wrapper is maintained for backwards compatibility.
    """
    from joshirank.analysis.gender_cache import get_gender_cache_stats as _stats

    return _stats()


def estimate_intergender_probability(match: dict, wrestler_db=None) -> float:
    """Estimate probability that a match is intergender.

    DEPRECATED: Use joshirank.analysis.gender.estimate_intergender_probability instead.
    This wrapper is maintained for backwards compatibility.

    Note: wrestler_db parameter is ignored (kept for API compatibility).
    """
    from joshirank.analysis.gender import estimate_intergender_probability as _estimate

    return _estimate(match)


# Re-export promotion functions for backwards compatibility
def all_tjpw_wrestlers(wrestler_db=None) -> set[int]:
    """Return a set of all wrestlers who have ever wrestled for TJPW.

    DEPRECATED: Use joshirank.analysis.promotion.all_tjpw_wrestlers instead.
    This wrapper is maintained for backwards compatibility.

    Note: wrestler_db parameter is ignored (kept for API compatibility).
    """
    from joshirank.analysis.promotion import all_tjpw_wrestlers as _all_tjpw

    return _all_tjpw()


if __name__ == "__main__":
    from joshirank.joshidb import wrestler_db

    tjpw_wrestlers = all_tjpw_wrestlers(wrestler_db)
    print(f"Total TJPW wrestlers found: {len(tjpw_wrestlers)}")
    for wid in sorted(tjpw_wrestlers):
        name = wrestler_db.get_name(wid)
        print(f"{wid}: {name}")
