"""Script to scrape wrestler profiles and matches from CageMatch.net."""

import random
import sys
import time

from loguru import logger

from joshirank.cagematch.scraper import CageMatchScraper
from joshirank.joshidb import WrestlerDb, reopen_rw
from joshirank.scrape.scrapeinfo import WrestlerScrapeInfo
from joshirank.scrape.workqueue import WorkItem, WorkQueue

YEAR = time.localtime().tm_year

# Priority constants (0-100 scale, lower = higher priority)
PRIORITY_URGENT = 1  # Missing wrestler profiles
PRIORITY_HIGH = 10  # Current year matches, stale female profiles
PRIORITY_NORMAL = 30  # Previous year matches, stale non-female profiles
PRIORITY_LOW = 50  # Historical matches (base)


class ScrapingSession:
    """A scraping session to update wrestler profiles and matches."""

    wrestler_db: WrestlerDb

    def __init__(self, wrestler_db: WrestlerDb):
        self.scraper = CageMatchScraper()
        self.scrape_info = WrestlerScrapeInfo(wrestler_db, current_year=YEAR)
        self.wrestler_db = wrestler_db

    def adjust_priority_by_importance(
        self, base_priority: int, wrestler_id: int
    ) -> int:
        """Adjust priority based on wrestler importance.

        More important wrestlers get better (lower) priority.
        Adjustment range: -5 to 0 (subtract up to 5 from base priority).
        """
        importance = self.scrape_info.calculate_importance(wrestler_id)
        adjustment = int(importance * 5)  # 0-5 point boost
        return max(1, base_priority - adjustment)  # Ensure priority stays >= 1

    def is_year_transition_period(self) -> bool:
        """Check if we're in early January (first 2 weeks).

        During this period, previous year data is prioritized over current year
        since current year has minimal data but previous year can be finalized.
        """
        current = time.localtime()
        return current.tm_mon == 1 and current.tm_mday <= 14

    def build_work_queue(self) -> WorkQueue:
        """Build work queue by analyzing database state.

        Priority scale (0-100, lower = higher priority):
        1: Missing wrestler profiles
        10: Stale female wrestler profiles, current year matches
        30: Stale non-female profiles, previous year matches
        50+: Historical matches (priority increases with age)

        During year transition (first 2 weeks of January), priorities shift:
        - Previous year gets HIGH priority (to finalize complete dataset)
        - Current year gets NORMAL priority (minimal data exists)
        """
        queue = WorkQueue()
        in_transition = self.is_year_transition_period()

        if in_transition:
            logger.info(
                "In year transition period - prioritizing {} data completion", YEAR - 1
            )

        # 1. URGENT: Profiles of Missing wrestlers (referenced but not in DB)
        # Priority based on appearance count and number of unique opponents
        for wid, count, opponents in self.scrape_info.find_missing_wrestlers():
            # Calculate priority based on appearances and connections
            # More appearances = higher priority (lower number)
            # Base: 1-30 range depending on appearances
            n_opponents = len(opponents)
            if n_opponents >= 20:
                # Very connected wrestler
                priority = PRIORITY_URGENT
            elif n_opponents >= 10:
                priority = PRIORITY_HIGH
            else:
                priority = PRIORITY_NORMAL + 10 - n_opponents

            queue.enqueue(
                WorkItem(
                    priority=priority,
                    wrestler_id=wid,
                    operation="refresh_profile",
                )
            )

        # 2. HIGH: Stale female wrestler profiles
        for wid in self.wrestler_db.all_female_wrestlers():
            if self.scrape_info.wrestler_info_is_stale(wid):
                queue.enqueue(
                    WorkItem(
                        priority=PRIORITY_HIGH,
                        wrestler_id=wid,
                        operation="refresh_profile",
                    )
                )

        # 3. NORMAL: Stale non-female profiles
        for wid in self.wrestler_db.all_wrestler_ids():
            if self.scrape_info.wrestler_info_is_stale(wid):
                if not self.wrestler_db.is_female(wid):
                    queue.enqueue(
                        WorkItem(
                            priority=PRIORITY_NORMAL,
                            wrestler_id=wid,
                            operation="refresh_profile",
                        )
                    )

        # 4. Match refreshes for female wrestlers (year-based priorities)
        for wid in self.wrestler_db.all_female_wrestlers():
            available_years = self.wrestler_db.match_years_available(wid)
            is_active = self.scrape_info.is_recently_active(wid)

            # Add missing current year only for recently active wrestlers
            # Skip retired/inactive wrestlers to avoid wasting scraping quota
            # During transition period, lower priority since there's minimal new data
            if YEAR not in available_years and is_active:
                base = PRIORITY_LOW if in_transition else PRIORITY_HIGH
                priority = self.adjust_priority_by_importance(base, wid)
                queue.enqueue(
                    WorkItem(
                        priority=priority,
                        wrestler_id=wid,
                        operation="refresh_matches",
                        year=YEAR,
                    )
                )

        # 5. Gender-diverse wrestlers: always check current year matches
        # Their imputed gender depends on current year opponent data, so we need
        # to refresh regardless of activity to detect gender reclassification
        # During transition period, lower priority since there's minimal new data
        for wid in self.wrestler_db.gender_diverse_wrestlers():
            available_years = self.wrestler_db.match_years_available(wid)
            base = PRIORITY_LOW if in_transition else PRIORITY_HIGH
            priority = self.adjust_priority_by_importance(base, wid)
            if YEAR not in available_years:
                queue.enqueue(
                    WorkItem(
                        priority=priority,
                        wrestler_id=wid,
                        operation="refresh_matches",
                        year=YEAR,
                    )
                )
            # Check if existing current year data is stale (every 14 days)
            elif self.scrape_info.matches_need_refresh(
                wid, YEAR, is_gender_diverse=True
            ):
                queue.enqueue(
                    WorkItem(
                        priority=priority,
                        wrestler_id=wid,
                        operation="refresh_matches",
                        year=YEAR,
                    )
                )

        # Continue with rest of female wrestler match refreshes
        for wid in self.wrestler_db.all_female_wrestlers():
            available_years = self.wrestler_db.match_years_available(wid)

            # Add missing previous year for all wrestlers
            # During transition period, boost priority to finalize previous year data
            if (YEAR - 1) not in available_years:
                if in_transition:
                    priority = self.adjust_priority_by_importance(PRIORITY_HIGH, wid)
                else:
                    priority = PRIORITY_NORMAL
                queue.enqueue(
                    WorkItem(
                        priority=priority,
                        wrestler_id=wid,
                        operation="refresh_matches",
                        year=YEAR - 1,
                    )
                )

            # Check stale years (for years already in database)
            stale_years = self.scrape_info.get_stale_match_years(wid)
            for year, priority in stale_years:
                queue.enqueue(
                    WorkItem(
                        priority=priority,
                        wrestler_id=wid,
                        operation="refresh_matches",
                        year=year,
                    )
                )

        logger.info("Built work queue with {} items", len(queue))
        return queue

    def process_queue(self, queue: WorkQueue):
        """Process work queue until done or rate limited."""
        total = len(queue)
        processed = 0

        while self.scraper.keep_going():
            item = queue.dequeue()
            if not item:
                break

            try:
                if item.priority < 30:
                    logger.debug(
                        "Priority {} | w{} | {}",
                        item.priority,
                        item.wrestler_id,
                        item.operation,
                    )
                if item.operation == "refresh_profile":
                    self.refresh_profile(item.wrestler_id)
                elif item.operation == "refresh_matches":
                    if item.year is None:
                        logger.error(
                            "refresh_matches operation requires year for wrestler {}",
                            item.wrestler_id,
                        )
                        continue
                    self.refresh_matches_for_year(item.wrestler_id, item.year)
                else:
                    raise ValueError(f"Unknown work item operation: {item.operation}")
                processed += 1
                if processed % 10 == 0:
                    logger.info(
                        "Progress: {}/{} ({:.1f}%)",
                        processed,
                        total,
                        100 * processed / total,
                    )

            except Exception as e:
                logger.error("Failed wrestler {}: {}", item.wrestler_id, e)

        logger.success("Processed {}/{} items", processed, total)

    def refresh_profile(self, wrestler_id: int):
        """Scrape and update wrestler profile."""
        if wrestler_id == -1:
            logger.warning("Skipping refresh for sentinel wrestler_id -1")
            return

        name = self.wrestler_db.get_name(wrestler_id)

        logger.info("Scraping profile for {} ({})", name, wrestler_id)
        scraped_profile = self.scraper.scrape_profile(wrestler_id)
        self.wrestler_db.save_profile_for_wrestler(
            wrestler_id, scraped_profile.profile_data
        )
        self.wrestler_db.update_wrestler_from_profile(wrestler_id)
        if name == "Unknown":
            # Update name if it was previously unknown
            updated_name = self.wrestler_db.get_name(wrestler_id)
            logger.info("Learned '{}' for ID {}", updated_name, wrestler_id)

            # For newly discovered female wrestlers, create a stub match entry
            # to ensure their matches get queued in the next session
            if self.wrestler_db.is_female(wrestler_id):
                logger.info(
                    "Creating stub match entry for new female wrestler", wrestler_id
                )
                self.wrestler_db.create_stale_match_stubs(wrestler_id, {YEAR - 1})

    def refresh_matches_for_year(self, wrestler_id: int, year: int):
        """Scrape and update matches for a specific year."""
        if wrestler_id == -1:
            logger.warning("Skipping match refresh for sentinel wrestler_id -1")
            return

        name = self.wrestler_db.get_name(wrestler_id)
        logger.info("Scraping {} | {} ({})", year, name, wrestler_id)
        matches, available_years = self.scraper.scrape_matches(wrestler_id, year)

        self.wrestler_db.save_matches_for_wrestler(wrestler_id, matches, year)

        # Create stale stubs for any newly discovered years
        if available_years:
            logger.debug(
                "Discovered {} available years for {}: {}",
                len(available_years),
                name,
                sorted(available_years),
            )
            self.wrestler_db.create_stale_match_stubs(wrestler_id, available_years)

        self.wrestler_db.update_matches_from_matches(wrestler_id)
        self.wrestler_db.update_wrestler_from_matches(wrestler_id)

    def seed_database(self):
        """Seed the database known missing profiles..."""
        logger.info("Seeding database with known missing profiles...")
        missing_wrestlers = [9232]
        for wid in missing_wrestlers:
            self.wrestler_db.save_profile_for_wrestler(wid, {"Missing Profile": True})
            self.wrestler_db.update_wrestler_from_profile(wid)
            self.wrestler_db.save_matches_for_wrestler(wid, [])

    def main(self):
        """Main scraping session logic using work queue."""

        logger.success("Starting scraping session with work queue...")
        self.seed_database()
        work_queue = self.build_work_queue()
        self.process_queue(work_queue)

        self.wrestler_db.close()
        logger.success("Scraping session complete.")


def setup_logging():
    """Set up logging format and level."""
    logger.remove()
    logger.add(
        sys.stderr,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>",
        level="INFO",
    )


if __name__ == "__main__":
    # set up the logging format
    # to be slightly more compact
    setup_logging()
    with reopen_rw() as wrestler_db:
        scraper = ScrapingSession(wrestler_db)

        scraper.main()
