import sys
import time

import requests
from loguru import logger

import joshirank.cagematch.cm_parse as cm_parse
from joshirank.joshidb import db as wrestler_db
from joshirank.joshidb import get_name, is_joshi


def refresh_wrestler(wrestler_id: int, year: int) -> dict:
    """Reload wrestler profile and matches from CageMatch.net if older than a week."""
    wrestler_info = wrestler_db.get_wrestler(wrestler_id)
    week = 60 * 60 * 24 * 7

    if "timestamp" not in wrestler_info or (
        time.time() - wrestler_info["timestamp"] > week
    ):
        wrestler = WrestlerScrape(wrestler_id)
        wrestler_info["timestamp"] = time.time()
        wrestler_info["profile"] = wrestler.scrape_data()
        wrestler_db.save_wrestler(wrestler_id, wrestler_info)

        # only load matches if the wrestler is a joshi
        if is_joshi(wrestler_id):
            logger.info(
                "loading matches for joshi wrestler {} ({})",
                get_name(wrestler_id),
                wrestler_id,
            )
            wrestler_info["matches"] = wrestler.scrape_matches(year)
        else:
            logger.debug(
                "Wrestler {} ({}) is not joshi, skipping matches.",
                get_name(wrestler_id),
                wrestler_id,
            )
        wrestler_db.save_wrestler(wrestler_id, wrestler_info)
    else:
        logger.debug(
            "Wrestler {} ({}) data is fresh.",
            get_name(wrestler_id),
            wrestler_id,
        )
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
                matches = list(cm_parse.parse_matches(r.text))
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


def follow_wrestlers(wrestler_id, year):
    wrestler_info = refresh_wrestler(wrestler_id, year)

    colleagues = get_all_colleagues(wrestler_info)
    logger.success(
        "{} ({}) has {} colleagues.",
        get_name(wrestler_id),
        wrestler_id,
        len(colleagues),
    )

    for wid in colleagues:
        refresh_wrestler(wid, year)


def follow_random_wrestlers(count: int, year: int):
    import random

    all_wrestler_ids = wrestler_db.all_wrestler_ids()
    random_ids = random.sample(all_wrestler_ids, count)
    for wid in random_ids:
        follow_wrestlers(int(wid), year)


if __name__ == "__main__":

    logger.info("Starting scrape...")
    logger.remove()

    logger.add(sys.stderr, level="INFO")
    follow_wrestlers(25763, 2025)
    follow_wrestlers(32147, 2025)
    follow_wrestlers(31992, 2025)
    follow_wrestlers(11675, 2025)
    follow_wrestlers(21999, 2025)  # miyuki takase

    for i, wid in enumerate(find_missing_wrestlers(), start=1):
        logger.info("({}) Missing wrestler id: {}", i, wid)
        follow_wrestlers(wid, 2025)
        if i > 50:
            break

    wrestler_db.close()
