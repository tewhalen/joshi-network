"""Analysis of wrestler names in matches."""

from collections import Counter

from bs4 import BeautifulSoup

from joshirank.cagematch.cm_match import parse_match
from joshirank.joshidb import wrestler_db


def get_primary_name_for_year(wrestler_id: int, year: int) -> str | None:
    """Determine the primary name the wrestler used in a given year.

    Analyzes the wrestler's matches for the specified year and returns the
    primary name they used. If no matches exist, returns None.

    Args:
        wrestler_id: The wrestler's ID
        year: The year to analyze

    Returns:
        Primary name used by the wrestler in the given year, or None if no matches exist.
    """

    match_info = wrestler_db.get_match_info(wrestler_id, year)

    if match_info["match_count"] == 0:
        # no matches for this wrestler in this year
        return None

    # there's a pre-existing name counter
    # there should already be a promotions_worked dictionary in the match info
    # which is unpacked json! just use that!

    name_counter = Counter(match_info.get("names_used", {}))

    primary_name, count = name_counter.most_common(1)[0]
    return primary_name


if __name__ == "__main__":
    # simple test
    wrestler_id = 4629  # Emi Sakura
    year = 2023
    primary_name = get_primary_name_for_year(wrestler_id, year)
    print(f"Wrestler {wrestler_id} primary name in {year}: {primary_name}")

    primary_name = get_primary_name_for_year(wrestler_id, 1997)
    print(f"Wrestler {wrestler_id} primary name in 1997: {primary_name}")
