import datetime
import sys
import time

import requests
from loguru import logger

import joshirank.cagematch.cm_match as cm_match
import joshirank.cagematch.cm_parse as cm_parse
from joshirank.joshidb import db as wrestler_db
from joshirank.joshidb import get_name, is_female

WEEK = 60 * 60 * 24 * 7


def refresh_this_wrestler(wrestler_id: int) -> bool:
    """Return True if the wrestler should be refreshed."""
    wrestler_info = wrestler_db.get_wrestler(wrestler_id)
    if not wrestler_info:
        return True
    elif not is_female(wrestler_id, wrestler_info):
        return False
    elif "timestamp" not in wrestler_info or (
        time.time() - wrestler_info["timestamp"] > WEEK
    ):
        return True
    else:
        return False


def refresh_wrestler(wrestler_id: int, year: int, force=False) -> dict:
    """Reload wrestler profile and matches from CageMatch.net if older than a week."""
    if not refresh_this_wrestler(wrestler_id) and not force:
        return wrestler_db.get_wrestler(wrestler_id)
    wrestler_info = wrestler_db.get_wrestler(wrestler_id)

    wrestler = WrestlerScrape(wrestler_id)
    wrestler_info["timestamp"] = time.time()
    wrestler_info["profile"] = wrestler.scrape_data()
    wrestler_db.save_wrestler(wrestler_id, wrestler_info)
    time.sleep(0.5)  # be polite to CageMatch
    # only load matches if the wrestler is a joshi
    if is_female(wrestler_id, wrestler_info):
        logger.info(
            "loading matches {} ({})",
            get_name(wrestler_id),
            wrestler_id,
        )
        wrestler_info["matches"] = wrestler.scrape_matches(year)
        # sleep is built into scrape_matches

    else:
        logger.debug(
            "Wrestler {} ({}) is not female*, skipping matches.",
            get_name(wrestler_id),
            wrestler_id,
        )
    wrestler_db.save_wrestler(wrestler_id, wrestler_info)

    return wrestler_info


class WrestlerScrape:
    wrestler_id: int

    @property
    def wrestler_url(self):
        return f"https://www.cagematch.net/?id=2&nr={self.wrestler_id}"

    def __init__(self, wrestler_id: int):
        self.wrestler_id = wrestler_id

    def scrape_data(self):
        data_page = requests.get(
            self.wrestler_url, headers={"accept-encoding": "compress"}
        )
        result = cm_parse.parse_wrestler_profile_page(data_page.text)
        result["id"] = self.wrestler_id
        return result

    def scrape_matches(self, year: int) -> list[dict]:
        self.matches = self.load_matches(year)
        return self.matches

    def load_matches(self, year: int, start=0) -> list[dict]:
        """Get all the matches for that wrestler_id for the given year."""
        matches_url = (
            f"https://www.cagematch.net/?id=2&nr={self.wrestler_id}&page=4&year={year}"
        )
        with requests.Session() as s:
            # print(matches_url.format(wrestler_id=wrestler_id, year=year))
            time.sleep(0.25)
            if start:
                url = matches_url + f"&s={start}"
            else:
                url = matches_url
            r = s.get(
                url,
                headers={"accept-encoding": "compress"},
            )
            if r:
                matches = list(cm_match.extract_match_data_from_match_page(r.text))
                if len(matches) == 100:
                    return matches + self.load_matches(year, start + 100)
                else:
                    return matches
            else:
                return []


def get_all_colleagues(wrestler_info: dict) -> set[int]:
    colleagues = set()
    for match in wrestler_info.get("matches", []):
        for wid in match["wrestlers"]:
            if wid != wrestler_info.get("id"):
                colleagues.add(wid)
    return colleagues


def find_missing_wrestlers():
    """Yield all wrestlers present in matches but missing from the database."""

    for wrestler_id in wrestler_db.all_wrestler_ids():
        wrestler_info = wrestler_db.get_wrestler(int(wrestler_id))
        colleagues = get_all_colleagues(wrestler_info)
        for wid in colleagues:
            if not wrestler_db.wrestler_exists(wid):
                yield wid


def follow_wrestlers(wrestler_id, year, deep=False):
    wrestler_info = refresh_wrestler(wrestler_id, year)

    colleagues = get_all_colleagues(wrestler_info)
    if colleagues:
        logger.success(
            "{} ({}) has {} colleagues.",
            get_name(wrestler_id),
            wrestler_id,
            len(colleagues),
        )

    for wid in colleagues:

        if deep:
            follow_wrestlers(wid, year)
        else:
            refresh_wrestler(wid, year)


def follow_random_wrestlers(count: int, year: int):
    import random

    all_wrestler_ids = wrestler_db.all_wrestler_ids()
    random_ids = random.sample(all_wrestler_ids, count)
    for wid in random_ids:
        follow_wrestlers(int(wid), year)


def wrestlers_sorted_by_match_count():
    "return a list of wrestler ids sorted by number of matches  descending"
    wrestler_match_counts = []
    for wid in wrestler_db.all_wrestler_ids():
        wrestler_info = wrestler_db.get_wrestler(int(wid))
        match_count = len(wrestler_info.get("matches", []))
        wrestler_match_counts.append((int(wid), match_count))
    return sorted(wrestler_match_counts, key=lambda x: x[1], reverse=True)


if __name__ == "__main__":

    logger.info("Starting scrape...")
    logger.remove()

    logger.add(sys.stderr, level="INFO")
    # refresh_wrestler(3387, 2025, force=True)
    # follow_wrestlers(10962, 2025, deep=True)  # mercedes
    # follow_wrestlers(32147, 2025)
    # follow_wrestlers(31992, 2025)
    # follow_wrestlers(11675, 2025)
    # follow_wrestlers(21999, 2025)

    refresh_count = 0
    for i, (wrestler_id, match_count) in enumerate(wrestlers_sorted_by_match_count()):
        if refresh_this_wrestler(wrestler_id):
            logger.info(
                "{} Refreshing wrestler {} ({}) with {} matches",
                i + 1,
                get_name(wrestler_id),
                wrestler_id,
                match_count,
            )
            follow_wrestlers(wrestler_id, 2025, deep=True)
            refresh_count += 1
        if refresh_count >= 20:
            break
    for i, wid in enumerate(find_missing_wrestlers(), start=1):
        logger.info("({}) Missing wrestler id: {}", i, wid)
        follow_wrestlers(wid, 2025, deep=True)

        if i > 50:
            break

    follow_random_wrestlers(10, 2025)
    wrestler_db.close()
