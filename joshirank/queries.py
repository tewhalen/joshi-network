"""Specialized Queries for Joshi Network data.

This module provides high-level query functions for analyzing the Joshi wrestling
database, including promotion-based wrestler discovery.

For gender prediction functions, see joshirank.analysis.gender module.
"""

import typing

if typing.TYPE_CHECKING:
    from joshirank.joshidb import WrestlerDb


def ever_worked_promotion(wrestler_db: WrestlerDb, promotion_id: int) -> set[int]:
    promotion_wrestlers = set()

    for wid in wrestler_db.all_female_wrestlers():
        # Check all available years for this wrestler using promotions_worked
        for year in wrestler_db.match_years_available(wid):
            match_info = wrestler_db.get_match_info(wid, year)
            promotions = match_info.get("promotions_worked", {})
            # promotions_worked maps promotion_id (as string or int) to count
            if str(promotion_id) in promotions or promotion_id in promotions:
                promotion_wrestlers.add(wid)
                # having found a set of matches we know included the promotion
                # we should check all the matches in that year to find all
                # the wrestlers in those promotion matches
                # because those wrestlers may not have the promotion in their promotions_worked
                matches = wrestler_db.get_matches(wid, year)
                for match in matches:
                    if match.get("promotion") == promotion_id:
                        for competitor in match.get("wrestlers", []):
                            promotion_wrestlers.add(competitor)

    # filter out any non-female wrestlers (in case of data errors)
    # promotion_wrestlers = {
    #    wid for wid in promotion_wrestlers if wrestler_db.is_female(wid)
    # }
    return promotion_wrestlers


def all_tjpw_wrestlers(wrestler_db: WrestlerDb) -> set[int]:
    """Return a set of all wrestlers who have ever wrestled for TJPW.

    Uses the promotions_worked field for efficient querying.
    """
    # TJPW promotion ID on CageMatch is 1467
    return ever_worked_promotion(wrestler_db, 1467)


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


if __name__ == "__main__":
    from joshirank.joshidb import wrestler_db

    tjpw_wrestlers = all_tjpw_wrestlers(wrestler_db)
    print(f"Total TJPW wrestlers found: {len(tjpw_wrestlers)}")
    for wid in sorted(tjpw_wrestlers):
        name = wrestler_db.get_name(wid)
        print(f"{wid}: {name}")
