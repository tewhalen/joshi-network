import datetime
import sys
import time
from collections import Counter

import requests
from loguru import logger

import joshirank.cagematch.cm_match as cm_match
import joshirank.cagematch.profile as profile
from joshirank.joshidb import db as wrestler_db
from joshirank.joshidb import get_name, is_female

WEEK = 60 * 60 * 24 * 7


def refresh_this_wrestler(wrestler_id: int) -> bool:
    """Return True if the wrestler should be refreshed."""
    wrestler_info = wrestler_db.get_wrestler(wrestler_id)
    if not wrestler_info:
        return True
    elif not wrestler_db.is_female(wrestler_id):
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
    wrestler = WrestlerScrape(wrestler_id)
    scraped_profile = wrestler.scrape_data()
    wrestler_db.save_profile_for_wrestler(wrestler_id, scraped_profile.profile_data)
    wrestler_db.update_wrestler_from_profile(wrestler_id)

    wrestler_info = wrestler_db.get_wrestler(wrestler_id)

    time.sleep(0.5)  # be polite to CageMatch
    # only load matches if the wrestler is a joshi
    if wrestler_info["is_female"]:
        logger.info(
            "loading matches {} ({})",
            wrestler_info.get("name", ""),
            wrestler_id,
        )
        matches = wrestler.scrape_matches(year)

        wrestler_db.save_matches(wrestler_id, matches)
        wrestler_db.update_matches_from_matches(wrestler_id)
        wrestler_db.update_wrestler_from_matches(wrestler_id)

        print("matches:", wrestler_db.get_matches(wrestler_id))

        # update
        wrestler_info = wrestler_db.get_wrestler(wrestler_id)
        # sleep is built into scrape_matches

    else:
        logger.debug(
            "Wrestler {} ({}) is not female*, skipping matches.",
            wrestler_info.get("name", ""),
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
        result = profile.CMProfile.from_html(self.wrestler_id, data_page.text)

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


def find_missing_wrestlers():
    """Yield all wrestlers present in matches but missing from the database."""
    appearance_counter = Counter()
    for wrestler_id in wrestler_db.all_wrestler_ids():

        colleagues = wrestler_db.get_all_colleagues(int(wrestler_id))
        for wid in colleagues:
            if not wrestler_db.wrestler_exists(wid):
                appearance_counter[wid] += 1
    for wid, count in appearance_counter.most_common():
        yield wid, count


def follow_wrestlers(wrestler_id, year, deep=False):
    refresh_wrestler(wrestler_id, year)

    colleagues = wrestler_db.get_all_colleagues(int(wrestler_id))
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
        match_count = len(wrestler_db.get_matches(int(wid)))
        wrestler_match_counts.append((int(wid), match_count))
    return sorted(wrestler_match_counts, key=lambda x: x[1], reverse=True)


if __name__ == "__main__":

    logger.info("Starting scrape...")
    # logger.remove()

    # logger.add(sys.stderr, level="INFO")
    res = refresh_wrestler(28004, 2025, force=True)
    print(res)
    print(wrestler_db.get_match_info(28004))
    sys.exit(0)
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
    for i, (wid, count) in enumerate(find_missing_wrestlers(), start=1):
        logger.info("({}) Missing wrestler id: {}", i, wid)
        follow_wrestlers(wid, 2025, deep=True)

        if i > 50:
            break

    follow_random_wrestlers(10, 2025)
    wrestler_db.close()
