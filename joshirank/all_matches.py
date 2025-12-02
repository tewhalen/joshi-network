from bs4 import BeautifulSoup
from loguru import logger

import joshirank.cagematch.cm_match as cm_match
from joshirank.joshidb import db as wrestler_db
from joshirank.joshidb import is_joshi


def to_tuple(dict_obj):
    return tuple(sorted(dict_obj.items()))


def all_singles_matches(wrestler_data: dict):
    for match in wrestler_data.get("matches", []):
        t = BeautifulSoup(match["raw_html"], "html.parser")
        res = cm_match.parse_match(t)
        del res["raw_html"]

        if len(res["side_a"]) == 1 and len(res["side_b"]) == 1:
            if is_joshi(res["side_a"][0]) and is_joshi(res["side_b"][0]):
                yield to_tuple(res)


def all_matches() -> set:
    all_matches = set()
    for wrestler in wrestler_db.all_wrestler_ids():
        wdata = wrestler_db.get_wrestler(int(wrestler))
        if not is_joshi(int(wrestler)):
            continue
        for match in all_singles_matches(wdata):
            # print(match)
            all_matches.add(match)

    print(f"Total singles matches: {len(all_matches)}")
    return all_matches
