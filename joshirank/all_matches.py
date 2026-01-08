from collections.abc import Generator

from loguru import logger

import joshirank.cagematch.cm_match as cm_match
from joshirank.joshidb import wrestler_db


def to_tuple(dict_obj):
    return tuple(sorted(dict_obj.items()))


def extract_singles_matches(match_data: list[cm_match.MatchDict]) -> Generator[tuple]:
    """Given a list of matches, yield tuples of info about only singles matches between female wrestlers."""
    for res in match_data:
        # should look at 'sides' if present, and fall back to 'side_a' and 'side_b' if not
        sides = res.get("sides", [[], []])
        side_a, side_b = res.get("side_a", []), res.get("side_b", [])
        if len(sides) == 2 and len(sides[0]) == 1 and len(sides[1]) == 1:
            wrestlers = (sides[0][0], sides[1][0])
        elif len(side_a) == 1 and len(side_b) == 1:
            wrestlers = (side_a[0], side_b[0])
        else:
            continue

        if -1 in wrestlers:
            # unknown wrestler ID
            continue

        if type(res["date"]) is not str:
            logger.warning("Match with unknown date: {}", res)
            continue

        if wrestler_db.is_female(wrestlers[0]) and wrestler_db.is_female(wrestlers[1]):
            yield (
                ("date", res["date"]),
                ("side_a", (wrestlers[0],)),
                ("side_b", (wrestlers[1],)),
                ("is_victory", res["is_victory"]),
            )


def all_matches(year: int) -> set:
    all_matches = set()
    j_count = 0
    for wrestler in wrestler_db.all_female_wrestlers_with_matches_in_year(year=year):
        wdata = wrestler_db.get_wrestler(wrestler)
        if not wrestler_db.is_female(wrestler):
            continue
        j_count += 1
        for match in extract_singles_matches(
            wrestler_db.get_matches(wrestler, year=year)
        ):
            # print(match)
            all_matches.add(match)

    # print(f"Total singles matches: {len(all_matches)}")
    # print(f"Total female wrestlers: {j_count}")
    return all_matches
