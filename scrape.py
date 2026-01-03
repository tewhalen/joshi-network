"""Script to scrape wrestler profiles and matches from CageMatch.net."""

import random
import sys
import time
from collections import Counter, defaultdict

from loguru import logger

import joshirank.cagematch.data as cm_data
from joshirank.cagematch.scraper import CageMatchScraper
from joshirank.joshidb import WrestlerDb, reopen_rw

WEEK = 60 * 60 * 24 * 7


YEAR = 2025


class WrestlerScrapeInfo:
    """Interface to check wrestler profile freshness and existence."""

    wrestler_db: WrestlerDb

    def __init__(self, wrestler_db: WrestlerDb):
        self.wrestler_db = wrestler_db

    def wrestler_info_is_stale(self, wrestler_id: int) -> bool:
        """Return True if the wrestler should be refreshed."""
        wrestler_info = self.wrestler_db.get_wrestler(wrestler_id)

        if "timestamp" not in wrestler_info or (
            time.time() - wrestler_info["timestamp"] > WEEK
        ):
            # info is stale, refresh
            return True
        else:
            return False

    def wrestler_profile_missing(self, wrestler_id: int) -> bool:
        """Return True if the wrestler profile is missing."""
        if wrestler_id in cm_data.missing_profiles:
            return False  # we know this profile is missing, don't try to reload it
        try:
            wrestler_info = self.wrestler_db.get_wrestler(wrestler_id)
        except KeyError:
            # wrestler not in DB, definitely refresh
            return True

        if not wrestler_info:
            # wrestler in DB but no info, definitely refresh
            return True
        return False

    def profile_age(self, wrestler_id: int) -> str:
        """Return the age of the wrestler profile in a nice human-readable string."""
        wrestler_info = self.wrestler_db.get_wrestler(wrestler_id)
        if not wrestler_info or "last_updated" not in wrestler_info:
            return "never"
        age_seconds = max(0, time.time() - wrestler_info["timestamp"])
        if age_seconds < 60:
            return f"{int(age_seconds)} seconds"
        elif age_seconds < 3600:
            return f"{int(age_seconds / 60)} minutes"
        elif age_seconds < 86400:
            return f"{int(age_seconds / 3600)} hours"
        else:
            return f"{int(age_seconds / 86400)} days"

    def find_missing_wrestlers(self):
        """Yield all wrestlers present in matches but missing from the database."""
        appearance_counter = Counter()
        opponent_tracker = defaultdict(set)
        for wrestler_id in self.wrestler_db.all_wrestler_ids():
            colleagues = self.wrestler_db.get_all_colleagues(int(wrestler_id))
            for wid in colleagues:
                if not self.wrestler_db.wrestler_exists(wid):
                    appearance_counter[wid] += 1
                    opponent_tracker[wid].add(wrestler_id)
        for wid, count in appearance_counter.most_common():
            yield wid, count, opponent_tracker[wid]

    def random_wrestlers(self, count: int, year: int):
        all_wrestler_ids = self.wrestler_db.all_wrestler_ids()
        random_ids = random.sample(all_wrestler_ids, count)
        return random_ids

    def wrestlers_without_profiles(self):
        """Yield all wrestler ids that have matches but no profile."""

        for wrestler_id in self.wrestler_db.all_wrestler_ids():
            wrestler_info = self.wrestler_db.get_cm_profile_for_wrestler(wrestler_id)

            if not wrestler_info:
                yield wrestler_id


class ScrapingSession:
    """A scraping session to update wrestler profiles and matches."""

    wrestler_db: WrestlerDb

    def __init__(self, wrestler_db: WrestlerDb):
        self.scraper = CageMatchScraper()
        self.scrape_info = WrestlerScrapeInfo(wrestler_db)
        self.wrestler_db = wrestler_db

    def wrestler_should_be_refreshed(
        self, wrestler_id: int, skip_gender_check=False
    ) -> bool:
        """Return True if the wrestler should be refreshed.

        Wrestlers with missing profiles, or female wrestlers with stale info, are refreshed."""
        if self.scrape_info.wrestler_profile_missing(wrestler_id):
            return True
        elif self.scrape_info.wrestler_info_is_stale(wrestler_id):
            if skip_gender_check:
                return True
            elif self.wrestler_db.is_female(wrestler_id):
                return True
        return False

    def refresh_wrestler(
        self,
        wrestler_id: int,
        year: int,
        force=False,
        force_matches=False,
        skip_gender_check=False,
    ) -> dict:
        """Reload wrestler profile and matches from CageMatch.net if refresh criteria are met.

        Loads the wrestler profile and updates the wrestler info in the database.
        If the wrestler is female, also loads matches for the given year and updates match info.

        """
        new_wrestler = False
        if not force and not self.wrestler_should_be_refreshed(
            wrestler_id, skip_gender_check=skip_gender_check
        ):
            return self.wrestler_db.get_wrestler(wrestler_id)

        try:
            logger.info(
                "Refresh: {} ({}) after {}",
                self.wrestler_db.get_name(wrestler_id),
                wrestler_id,
                self.scrape_info.profile_age(wrestler_id),
            )
        except KeyError:
            new_wrestler = True
        scraped_profile = self.scraper.scrape_profile(wrestler_id)
        self.wrestler_db.save_profile_for_wrestler(
            wrestler_id, scraped_profile.profile_data
        )
        self.wrestler_db.update_wrestler_from_profile(wrestler_id)
        if new_wrestler:
            logger.info(
                "Added new wrestler: {} ({})",
                self.wrestler_db.get_name(wrestler_id),
                wrestler_id,
            )
        # only load matches if the wrestler is female or if forced
        if self.wrestler_db.is_female(wrestler_id) or force_matches:
            self.scrape_matches(wrestler_id, year)
            self.wrestler_db.update_matches_from_matches(wrestler_id)
            self.wrestler_db.update_wrestler_from_matches(wrestler_id)

        # only load history for female wrestlers
        if self.wrestler_db.is_female(wrestler_id):
            self.scrape_missing_years(wrestler_id)
            self.wrestler_db.update_matches_from_matches(wrestler_id)
            self.wrestler_db.update_wrestler_from_matches(wrestler_id)

        return self.wrestler_db.get_wrestler(wrestler_id)

    def scrape_matches(self, wrestler_id: int, year: int):
        """Scrape matches for a wrestler for a given year."""

        matches = self.scraper.scrape_matches(wrestler_id, year)

        self.wrestler_db.save_matches_for_wrestler(wrestler_id, matches, year)

    def scrape_missing_years(self, wrestler_id: int):
        """Looks for missing years of matches and scrapes them."""
        missing_years = self.missing_match_years_for_wrestler(wrestler_id)
        logger.info(
            "Scraping {} missing years for {} ({})",
            len(missing_years),
            self.wrestler_db.get_name(wrestler_id),
            wrestler_id,
        )
        for year in missing_years:
            self.scrape_matches(wrestler_id, year)

    def follow_wrestlers(self, wrestler_id: int, year, deep=False):
        self.refresh_wrestler(wrestler_id, year)

        colleagues = self.wrestler_db.get_all_colleagues(int(wrestler_id))
        if colleagues:
            logger.info(
                "Follow: {} ({}) has {} colleagues.",
                self.wrestler_db.get_name(wrestler_id),
                wrestler_id,
                len(colleagues),
            )

        for wid in colleagues:
            if deep:
                self.follow_wrestlers(wid, year)
            else:
                self.refresh_wrestler(wid, year)

    def follow_random_wrestlers(self, count: int, year: int):
        random_ids = self.scrape_info.random_wrestlers(count, year)
        for wid in random_ids:
            self.follow_wrestlers(int(wid), year)

    def follow_random_wrestler(self, year: int):
        all_wrestler_ids = self.wrestler_db.all_wrestler_ids()
        wid = random.choice(all_wrestler_ids)
        self.follow_wrestlers(wid, year)

    def update_gender_diverse_wrestlers(self):
        """Update all wrestlers whose gender is not male or female."""
        logger.info("Updating gender-diverse wrestlers...")
        for wrestler_id in self.wrestler_db.gender_diverse_wrestlers():
            if not self.scraper.keep_going():
                break
            self.refresh_wrestler(
                wrestler_id, YEAR, force_matches=True, skip_gender_check=True
            )

    def update_missing_wrestlers(self):
        """Update all wrestlers who are missing from the database but appear in matches."""
        logger.info("Updating missing wrestlers...")
        for i, (wid, count, opponents) in enumerate(
            self.scrape_info.find_missing_wrestlers(), start=1
        ):
            if not self.scraper.keep_going():
                break
            logger.info(
                "Missing wrestler {} appears in {} matches against {}.",
                wid,
                count,
                list(
                    map(
                        lambda x: "{} ({})".format(self.wrestler_db.get_name(x), x),
                        opponents,
                    )
                ),
            )
            self.refresh_wrestler(wid, YEAR)

    def update_wrestlers_without_profiles(self):
        """Yield all wrestler ids that have matches but no profile."""
        logger.info("Updating wrestlers without profiles...")
        for wrestler_id in self.scrape_info.wrestlers_without_profiles():
            if not self.scraper.keep_going():
                break
            self.refresh_wrestler(wrestler_id, YEAR, force=True)

    def update_top_wrestlers(self):
        """Work through the top wrestlers by match count."""
        logger.info("Following wrestlers in descending match count order...")

        mc_wrestlers = self.wrestler_db.wrestlers_sorted_by_match_count()

        for i, (wrestler_id, match_count) in enumerate(mc_wrestlers, start=1):
            if not self.scraper.keep_going():
                break
            if self.scrape_info.wrestler_profile_missing(
                wrestler_id
            ) or self.scrape_info.wrestler_info_is_stale(wrestler_id):
                self.follow_wrestlers(wrestler_id, YEAR)

    def update_random_wrestlers(self):
        """Update a number of random wrestlers."""
        logger.info("Updating wrestlers at random...")
        all_wrestler_ids = self.wrestler_db.all_female_wrestlers()
        random_ids = random.sample(all_wrestler_ids, 10)
        for wid in random_ids:
            if not self.scraper.keep_going():
                break
            self.refresh_wrestler(wid, YEAR, force=True)

    def missing_match_years_for_wrestler(self, wrestler_id: int) -> set[int]:
        """Return all years that matches are missing for a wrestler."""
        existing_years = self.wrestler_db.match_years_available(wrestler_id)
        all_years = self.scraper.match_years(wrestler_id)
        missing_years = all_years - existing_years
        return missing_years

    def seed_database(self):
        """Seed the database known missing profiles..."""
        logger.info("Seeding database with known missing profiles...")
        missing_wrestlers = [9232]
        for wid in missing_wrestlers:
            self.wrestler_db.save_profile_for_wrestler(wid, {"Missing Profile": True})
            self.wrestler_db.update_wrestler_from_profile(wid)
            self.wrestler_db.save_matches_for_wrestler(wid, [])

    def main(self):
        """Main scraping session logic."""
        # set up the logging format
        # to be slightly more compact
        logger.remove()
        logger.add(
            sys.stderr,
            format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>",
            level="INFO",
        )

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

        self.wrestler_db.close()
        logger.success("Scraping session complete.")


if __name__ == "__main__":
    wrestler_db = reopen_rw()
    scraper = ScrapingSession(wrestler_db)

    # logger.add(sys.stderr, level="INFO")
    FORCE_SCRAPES = []

    for wid in FORCE_SCRAPES:
        scraper.refresh_wrestler(wid, YEAR, force=True)

        print(wrestler_db.get_wrestler(wid))
        print(wrestler_db.get_match_info(wid))
    if FORCE_SCRAPES:
        sys.exit()

    scraper.main()
