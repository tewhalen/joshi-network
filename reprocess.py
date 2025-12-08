"""Script to reprocess profiles and matches without scraping."""

import pprint

from bs4 import BeautifulSoup
from loguru import logger

from joshirank.cagematch.cm_match import parse_match
from joshirank.joshidb import db as wrestler_db

WEEK = 60 * 60 * 24 * 7

LOAD_COUNT = 0


def refresh_wrestler(wrestler_id: int) -> dict:
    """Reload wrestler profile and matches from CageMatch.net if older than a week."""
    wrestler_db.update_wrestler_from_profile(wrestler_id)
    reprocess_matches_for_wrestler(wrestler_id)


def reprocess_matches_for_wrestler(wrestler_id: int) -> None:
    """Reprocess matches for a wrestler."""
    matches = list(wrestler_db.get_matches(wrestler_id))
    new_matches = []
    # pprint.pprint(matches)
    if not matches:
        return
    # print(f"Reprocessing {len(matches)} matches for wrestler {wrestler_id}")
    # print(list(range(len(matches))))

    for match_index in range(len(matches)):

        match = matches[match_index]

        match_soup = BeautifulSoup(match["raw_html"], "lxml")

        parsed_match = parse_match(match_soup)

        new_matches.append(parsed_match)

    wrestler_db.save_matches_for_wrestler(wrestler_id, new_matches)
    if new_matches:
        wrestler_db.update_matches_from_matches(wrestler_id)
        wrestler_db.update_wrestler_from_matches(wrestler_id)


if __name__ == "__main__":

    logger.info("Starting reprocess...")
    refresh_wrestler(32674)
    for i, wrestler_id in enumerate(wrestler_db.all_wrestler_ids(), start=1):

        refresh_wrestler(int(wrestler_id))

    wrestler_db.close()
    logger.info("Reprocess complete.")
