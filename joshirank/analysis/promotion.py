"""Analysis of Wrestler promotion and location.

There's a profile-level "promotion" field, which indicates the wrestler's
promotion as of the time of scraping, which doesn't necessarily mean
where they wrestled most of the time, but instead reflects their
contract status. For example, Maki Itoh was listed as a freelancer on
her profile even while wrestling primarily for TJPW.

Each match also has a promotion field, indicating the promotion
under which the match took place. By analyzing the matches a wrestler
has worked in a given year, we can determine their "primary" promotion
for that year, based on where they wrestled the most. If no single promotion
accounts for a significant portion of their matches, we can consider them
a freelancer for that year.

Location is similar, although there is no profile-level location field. The
use of the location field is primarily to provide context for freelancers,
indicating where they are primarily based out of. We can attempt to guess
a wrestler's location based on the countries they have worked matches in. This
needs to be a year-by-year determination as well, since wrestlers may relocate
over time.
For this reason, the use of the location field in the wrestler table is discouraged.

"""

import json
from collections import Counter

from joshirank.joshidb import get_promotion_name, wrestler_db


def wrestler_is_retired(wrestler_id: int) -> bool:
    """Determine if a wrestler is retired based on profile data.

    A wrestler is considered retired if there's a end date in their profile.

    Args:
        wrestler_id: The wrestler's ID
    """

    wrestler_info = wrestler_db.get_wrestler(wrestler_id)
    career_end = wrestler_info.get("career_end", None)
    if career_end:
        return True
    return False


def get_promotion_with_location(wrestler_id: int) -> str:
    """Get the wrestler's most-recent primary promotion, including location if freelancer."""
    years_available = wrestler_db.match_years_available(wrestler_id)

    if not years_available or wrestler_is_retired(wrestler_id):
        return "Inactive"

    promotion = None
    # get most recent year with matches
    for year in sorted(years_available, reverse=True):
        promotion = get_primary_promotion_for_year(wrestler_id, year)
        if promotion is not None:
            break
    if promotion is None:
        # no matches found at all?
        return "Inactive"
    else:
        return promotion


def get_primary_promotion_for_year(wrestler_id: int, year: int) -> str | None:
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

    match_info = wrestler_db.get_match_info(wrestler_id, year)
    match_count = match_info.get("match_count", 0)

    if match_count == 0:
        # no matches for this wrestler in this year
        return None

    # there should already be a promotions_worked dictionary in the match info
    # which is unpacked json! just use that!

    promotion_counter = Counter(match_info.get("promotions_worked", {}))

    # Get the most common promotion
    most_common_promo_id, count = promotion_counter.most_common(1)[0]

    # If this promotion represents at least 40% of matches, use it
    if count / match_count >= 0.4:
        promo_name = get_promotion_name(most_common_promo_id)
        return promo_name

    # Otherwise, they're a freelancer

    # see if there's a location we can include
    location = _get_primary_location_for_year(match_info)
    if location:
        return f"Freelancer ({location})"
    else:
        return "Freelancer"


def get_primary_location_for_year(wrestler_id: int, year: int) -> str | None:
    """Determine the primary location for a wrestler in a given year.

    Analyzes the wrestler's matches for the specified year and returns the
    country where they wrestled the most.

    Args:
        wrestler_id: The wrestler's ID
        year: The year to analyze

    Returns:
        Country name, or None if no matches exist.
    """

    match_info = wrestler_db.get_match_info(wrestler_id, year)
    return _get_primary_location_for_year(match_info)


def _get_primary_location_for_year(match_info: dict) -> str | None:
    match_count = match_info.get("match_count", 0)

    if match_count == 0:
        # no matches for this wrestler in this year
        return None

    country_counter = Counter(match_info.get("countries_worked", {}))

    if not country_counter:
        return None

    most_common_country, count = country_counter.most_common(1)[0]

    return most_common_country


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


def guess_location_from_matches(wrestler_id: int):
    """Guess the wrestler's location based on countries worked in matches."""
    # get countries worked from matches
    rows = wrestler_db._select_and_fetchall(
        """SELECT countries_worked FROM matches WHERE wrestler_id=?""",
        (wrestler_id,),
    )
    if not rows:
        return

    country_counter = Counter()
    for row in rows:
        if row and row[0]:
            # should be a dict stored as json
            countries_worked = json.loads(row[0])
            country_counter.update(countries_worked)

    if country_counter:
        # get the most common country
        return max(country_counter.items(), key=lambda x: x[1])[0]
