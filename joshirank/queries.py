import typing

if typing.TYPE_CHECKING:
    from joshirank.joshidb import WrestlerDb

"""Specialized Queries for Joshi Network data."""


def all_tjpw_wrestlers(wrestler_db: WrestlerDb) -> set[int]:
    """Return a set of all wrestlers who have ever wrestled for TJPW.

    Uses the promotions_worked field for efficient querying.
    """
    # TJPW promotion ID on CageMatch is 1467
    TJPW_ID = 1467
    tjpw_wrestlers = set()

    for wid in wrestler_db.all_female_wrestlers():
        # Check all available years for this wrestler using promotions_worked
        for year in wrestler_db.match_years_available(wid):
            match_info = wrestler_db.get_match_info(wid, year)
            promotions = match_info.get("promotions_worked", {})
            # promotions_worked maps promotion_id (as string or int) to count
            if str(TJPW_ID) in promotions or TJPW_ID in promotions:
                tjpw_wrestlers.add(wid)
                # having found a set of matches we know included TJPW
                # we should check all the matches in that year to find all
                # the wrestlers in those TJPW matches
                # because those wrestlers may not have TJPW in their promotions_worked
                matches = wrestler_db.get_matches(wid, year)
                for match in matches:
                    if match.get("promotion") == TJPW_ID:
                        for competitor in match.get("wrestlers", []):
                            tjpw_wrestlers.add(competitor)

    # filter out any non-female wrestlers (in case of data errors)
    tjpw_wrestlers = {wid for wid in tjpw_wrestlers if wrestler_db.is_female(wid)}
    return tjpw_wrestlers


if __name__ == "__main__":
    from joshirank.joshidb import wrestler_db

    tjpw_wrestlers = all_tjpw_wrestlers(wrestler_db)
    print(f"Total TJPW wrestlers found: {len(tjpw_wrestlers)}")
    for wid in sorted(tjpw_wrestlers):
        name = wrestler_db.get_name(wid)
        print(f"{wid}: {name}")
