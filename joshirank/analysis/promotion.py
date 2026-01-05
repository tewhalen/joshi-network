"""Analysis by promotion"""

import typing
from collections import Counter

from joshirank.joshidb import WrestlerDb, get_promotion_name, wrestler_db


def get_promotion_with_location(wrestler_id: int) -> str:
    wrestler_info = wrestler_db.get_wrestler(wrestler_id)
    promotion = wrestler_info.get("promotion", "")
    if promotion == "" or promotion == "Freelancer":
        location = wrestler_info.get("location", "Unknown")
        if location != "Unknown":
            promotion = f"Freelancer ({location})"
        else:
            promotion = "Freelancer"
    return promotion


def get_primary_promotion_for_year(wrestler_id: int, year: int) -> str:
    """Determine the primary promotion for a wrestler in a given year.

    Analyzes the wrestler's matches for the specified year and returns the
    promotion where they wrestled the most. If no clear primary promotion
    exists, returns "Freelancer" with location.

    Args:
        wrestler_id: The wrestler's ID
        year: The year to analyze

    Returns:
        Promotion name, or "Freelancer (location)" if no clear primary
    """
    matches = wrestler_db.get_matches(wrestler_id, year)

    if not matches:
        # No matches this year, fall back to current profile
        return get_promotion_with_location(wrestler_id)

    # Count matches by promotion
    promotion_counter = Counter()
    for match in matches:
        promotion_id = match.get("promotion")
        if promotion_id:
            promotion_counter[promotion_id] += 1

    if not promotion_counter:
        # No promotion data in matches, fall back
        return get_promotion_with_location(wrestler_id)

    # Get the most common promotion
    most_common_promo_id, count = promotion_counter.most_common(1)[0]
    total_matches = len(matches)

    # If this promotion represents at least 40% of matches, use it
    if count / total_matches >= 0.4:
        promo_name = get_promotion_name(most_common_promo_id)
        return promo_name

    # Otherwise, they're a freelancer
    wrestler_info = wrestler_db.get_wrestler(wrestler_id)
    location = wrestler_info.get("location", "")
    if location and location != "Unknown":
        return f"Freelancer ({location})"
    return "Freelancer"


def ever_worked_promotion(promotion_id: int) -> set[int]:
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


def all_tjpw_wrestlers() -> set[int]:
    """Return a set of all wrestlers who have ever wrestled for TJPW.

    Uses the promotions_worked field for efficient querying.
    """
    # TJPW promotion ID on CageMatch is 1467
    return ever_worked_promotion(1467)
