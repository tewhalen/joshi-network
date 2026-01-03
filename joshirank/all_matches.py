from typing import Generator

from bs4 import BeautifulSoup
from loguru import logger

import joshirank.cagematch.cm_match as cm_match
from joshirank.joshidb import wrestler_db


def to_tuple(dict_obj):
    return tuple(sorted(dict_obj.items()))


def extract_singles_matches(match_data: list[dict]) -> Generator[tuple]:
    """Given a list of matches, yield tuples of info about only singles matches between joshi wrestlers."""
    for res in match_data:
        if len(res["side_a"]) == 1 and len(res["side_b"]) == 1:
            if type(res["date"]) is not str:
                logger.warning("Match with unknown date: {}", res)
                continue
            if wrestler_db.is_female(res["side_a"][0]) and wrestler_db.is_female(
                res["side_b"][0]
            ):
                yield (
                    ("date", res["date"]),
                    ("side_a", (res["side_a"][0],)),
                    ("side_b", (res["side_b"][0],)),
                    ("is_victory", res["is_victory"]),
                )


def all_matches() -> set:
    all_matches = set()
    j_count = 0
    for wrestler in wrestler_db.all_wrestler_ids():
        wdata = wrestler_db.get_wrestler(wrestler)
        if not wrestler_db.is_female(wrestler):
            continue
        j_count += 1
        for match in extract_singles_matches(wrestler_db.get_matches(wrestler)):
            # print(match)
            all_matches.add(match)

    print(f"Total singles matches: {len(all_matches)}")
    print(f"Total joshi wrestlers: {j_count}")
    return all_matches
