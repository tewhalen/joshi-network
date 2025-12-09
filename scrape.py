"""Script to scrape wrestler profiles and matches from CageMatch.net."""

import random
import sys
import time
from collections import Counter, defaultdict

from loguru import logger

import joshirank.cagematch.data as cm_data
from joshirank.cagematch.scraper import CageMatchScraper
from joshirank.joshidb import db as wrestler_db
from joshirank.joshidb import get_name

WEEK = 60 * 60 * 24 * 7


class ScrapingSession:
    def __init__(self):
        self.scraper = CageMatchScraper()

    def wrestler_info_is_stale(self, wrestler_id: int) -> bool:
        """Return True if the wrestler should be refreshed."""
        wrestler_info = wrestler_db.get_wrestler(wrestler_id)

        if "timestamp" not in wrestler_info or (
            time.time() - wrestler_info["timestamp"] > WEEK
        ):
            # info is stale, refresh
            return True
        else:
            return False

    def wrestler_profile_missing(self, wrestler_id: int) -> bool:
        """Return True if the wrestler profile is missing."""
        if wrestler_db in cm_data.missing_profiles:
            return False  # we know this profile is missing, don't try to reload it
        try:
            wrestler_info = wrestler_db.get_wrestler(wrestler_id)
        except KeyError:
            # wrestler not in DB, definitely refresh
            return True

        if not wrestler_info:
            # wrestler in DB but no info, definitely refresh
            return True
        return False

    def profile_age(self, wrestler_id: int) -> str:
        """Return the age of the wrestler profile in a nice human-readable string."""
        wrestler_info = wrestler_db.get_wrestler(wrestler_id)
        if not wrestler_info or "last_updated" not in wrestler_info:
            return "never"
        age_seconds = time.time() - wrestler_info["timestamp"]
        if age_seconds < 60:
            return f"{int(age_seconds)} seconds"
        elif age_seconds < 3600:
            return f"{int(age_seconds / 60)} minutes"
        elif age_seconds < 86400:
            return f"{int(age_seconds / 3600)} hours"
        else:
            return f"{int(age_seconds / 86400)} days"

    def refresh_wrestler(
        self,
        wrestler_id: int,
        year: int,
        force=False,
        force_matches=False,
        skip_gender_check=False,
    ) -> dict:
        """Reload wrestler profile and matches from CageMatch.net if older than a week."""
        report_results = False
        if self.wrestler_profile_missing(wrestler_id) or force:
            report_results = True
            pass
        elif self.wrestler_info_is_stale(wrestler_id):
            if skip_gender_check:
                pass
            elif wrestler_db.is_female(wrestler_id):
                pass
            else:
                return wrestler_db.get_wrestler(wrestler_id)
        else:
            return wrestler_db.get_wrestler(wrestler_id)
        try:
            logger.info(
                "Refresh: {} ({}) after {}",
                get_name(wrestler_id),
                wrestler_id,
                self.profile_age(wrestler_id),
            )
        except KeyError:
            logger.info("New Wrestler: {}", wrestler_id)
        scraped_profile = self.scraper.scrape_profile(wrestler_id)
        wrestler_db.save_profile_for_wrestler(wrestler_id, scraped_profile.profile_data)
        wrestler_db.update_wrestler_from_profile(wrestler_id)

        # only load matches if the wrestler is a joshi
        if wrestler_db.is_female(wrestler_id) or force_matches:

            self.scrape_matches(wrestler_id, year)

        if report_results:
            if wrestler_db.is_female(wrestler_id):
                logger.info(
                    "\t{} ({}) has {} matches and {} colleagues",
                    get_name(wrestler_id),
                    wrestler_id,
                    wrestler_db.get_match_info(wrestler_id)["match_count"],
                    len(wrestler_db.get_all_colleagues(wrestler_id)),
                )
            else:
                logger.info(
                    "\t{} ({}) is not considered relevant.",
                    get_name(wrestler_id),
                    wrestler_id,
                )

        return wrestler_db.get_wrestler(wrestler_id)

    def scrape_matches(self, wrestler_id: int, year: int):
        name = wrestler_db.get_name(wrestler_id)

        matches = self.scraper.scrape_matches(wrestler_id, year)

        wrestler_db.save_matches_for_wrestler(wrestler_id, matches, year)

        wrestler_db.update_matches_from_matches(wrestler_id)
        wrestler_db.update_wrestler_from_matches(wrestler_id)

    def find_missing_wrestlers(self):
        """Yield all wrestlers present in matches but missing from the database."""
        appearance_counter = Counter()
        opponent_tracker = defaultdict(set)
        for wrestler_id in wrestler_db.all_wrestler_ids():

            colleagues = wrestler_db.get_all_colleagues(int(wrestler_id))
            for wid in colleagues:
                if not wrestler_db.wrestler_exists(wid):
                    appearance_counter[wid] += 1
                    opponent_tracker[wid].add(wrestler_id)
        for wid, count in appearance_counter.most_common():
            yield wid, count, opponent_tracker[wid]

    def follow_wrestlers(self, wrestler_id: int, year, deep=False):
        self.refresh_wrestler(wrestler_id, year)

        colleagues = wrestler_db.get_all_colleagues(int(wrestler_id))
        if colleagues:
            logger.info(
                "Follow: {} ({}) has {} colleagues.",
                get_name(wrestler_id),
                wrestler_id,
                len(colleagues),
            )

        for wid in colleagues:

            if deep:
                self.follow_wrestlers(wid, year)
            else:
                self.refresh_wrestler(wid, year)

    def follow_random_wrestlers(self, count: int, year: int):

        all_wrestler_ids = wrestler_db.all_wrestler_ids()
        random_ids = random.sample(all_wrestler_ids, count)
        for wid in random_ids:
            self.follow_wrestlers(int(wid), year)

    def follow_random_wrestler(self, year: int):

        all_wrestler_ids = wrestler_db.all_wrestler_ids()
        wid = random.choice(all_wrestler_ids)
        self.follow_wrestlers(wid, year)

    def update_gender_diverse_wrestlers(self):
        """Update all wrestlers whose gender is not male or female."""
        logger.info("Updating gender-diverse wrestlers...")
        for wrestler_id in wrestler_db.gender_diverse_wrestlers():
            if not self.scraper.keep_going():
                break
            self.refresh_wrestler(
                wrestler_id, 2025, force_matches=True, skip_gender_check=True
            )

    def update_missing_wrestlers(self):
        """Update all wrestlers who are missing from the database but appear in matches."""
        logger.info("Updating missing wrestlers...")
        for i, (wid, count, opponents) in enumerate(
            self.find_missing_wrestlers(), start=1
        ):
            if not self.scraper.keep_going():
                break
            logger.info(
                "Missing wrestler {} appears in {} matches against {}.",
                wid,
                count,
                list(map(lambda x: "{} ({})".format(get_name(x), x), opponents)),
            )
            self.follow_wrestlers(wid, 2025, deep=True)

    def update_wrestlers_without_profiles(self):
        """Yield all wrestler ids that have matches but no profile."""
        logger.info("Updating wrestlers without profiles...")
        for wrestler_id in wrestler_db.all_wrestler_ids():
            if not self.scraper.keep_going():
                break
            wrestler_info = wrestler_db.get_cm_profile_for_wrestler(wrestler_id)

            if not wrestler_info:
                self.refresh_wrestler(wrestler_id, 2025, force=True)

    def update_top_wrestlers(self):
        """Work through the top wrestlers by match count."""
        logger.info("Following wrestlers in descending match count order...")

        mc_wrestlers = wrestler_db.wrestlers_sorted_by_match_count()

        for i, (wrestler_id, match_count) in enumerate(mc_wrestlers, start=1):
            if not self.scraper.keep_going():
                break
            if self.wrestler_profile_missing(
                wrestler_id
            ) or self.wrestler_info_is_stale(wrestler_id):
                self.follow_wrestlers(wrestler_id, 2025)

    def update_random_wrestlers(self):
        """Update a number of random wrestlers."""
        logger.info("Updating wrestlers at random...")
        all_wrestler_ids = wrestler_db.all_female_wrestlers()
        random_ids = random.sample(all_wrestler_ids, 10)
        for wid in random_ids:
            if not self.scraper.keep_going():
                break
            self.refresh_wrestler(wid, 2025, force=True)

    def seed_database(self):
        """Seed the database known missing profiles..."""
        logger.info("Seeding database with known missing profiles...")
        missing_wrestlers = [9232]
        for wid in missing_wrestlers:

            wrestler_db.save_profile_for_wrestler(wid, {"Missing Profile": True})
            wrestler_db.update_wrestler_from_profile(wid)
            wrestler_db.save_matches_for_wrestler(wid, [])

    def main(self):
        logger.success("Starting scraping session...")
        self.seed_database()
        for update_function in [
            self.update_gender_diverse_wrestlers,
            self.update_wrestlers_without_profiles,
            self.update_missing_wrestlers,
            self.update_top_wrestlers,
            self.update_random_wrestlers,
        ]:
            if self.scraper.keep_going():
                update_function()
            else:
                break

        wrestler_db.close()
        logger.success("Scraping session complete.")


if __name__ == "__main__":

    scraper = ScrapingSession()

    # logger.add(sys.stderr, level="INFO")
    FORCE_SCRAPES = []

    for wid in FORCE_SCRAPES:
        scraper.refresh_wrestler(wid, 2025, force=True)

        print(wrestler_db.get_wrestler(wid))
        print(wrestler_db.get_match_info(wid))
    if FORCE_SCRAPES:
        sys.exit()

    scraper.main()
