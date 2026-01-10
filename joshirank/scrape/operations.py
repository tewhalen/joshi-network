"""Scraping operations for wrestler profiles and matches."""

import time

from loguru import logger

from joshirank.cagematch.scraper import CageMatchScraper
from joshirank.joshidb import WrestlerDb
from joshirank.scrape.workqueue import WorkItem

THIS_YEAR = time.localtime().tm_year


class OperationsManager:
    """Manages scraping operations and HTTP session."""

    def __init__(self, wrestler_db: WrestlerDb, slow: int | None = None):
        """Initialize operations manager.

        Args:
            wrestler_db: Database instance to update
            slow: If set, use this many seconds delay and remove session limit
        """
        self.wrestler_db = wrestler_db
        self.scraper = CageMatchScraper()

        if slow is not None:
            self.scraper.sleep_delay = float(slow)
            self.scraper.max_requests_per_session = float("inf")  # No limit

    def keep_going(self) -> bool:
        """Check if we should continue scraping (rate limit check).

        Returns:
            True if we should continue, False if rate limited
        """
        return self.scraper.keep_going()

    def refresh_profile(self, wrestler_id: int):
        """Scrape and update wrestler profile.

        Args:
            wrestler_id: ID of wrestler to scrape
        """
        if wrestler_id == -1:
            logger.warning("Skipping refresh for sentinel wrestler_id -1")
            return

        name = self.wrestler_db.get_name(wrestler_id)

        logger.info("{} | Scraping profile for {} ", wrestler_id, name)
        scraped_profile = self.scraper.scrape_profile(wrestler_id)
        # Atomically save JSON and update derived fields using in-memory data
        wrestler_profile = self.wrestler_db.save_profile_for_wrestler(
            wrestler_id, scraped_profile.profile_data
        )

        if name == "Unknown":
            # Update name if it was previously unknown
            updated_name = wrestler_profile.name()
            logger.info("{} | Learned '{}' ", wrestler_id, updated_name)

            # For newly discovered female wrestlers, create a stub match entry
            # to ensure their matches get queued in the next session
            if wrestler_profile.is_female():
                start_year, end_year = self._guess_likely_match_year_range(
                    scraped_profile
                )
                logger.success(
                    "{} | Creating stubs for years {}-{}",
                    wrestler_id,
                    start_year,
                    end_year,
                )
                # create the range between start_year and end_year inclusive
                years_range = set(range(start_year, end_year + 1))
                self.wrestler_db.create_stale_match_stubs(wrestler_id, years_range)

    def refresh_matches_for_year(self, wrestler_id: int, year: int):
        """Scrape and update matches for a specific year.

        Args:
            wrestler_id: ID of wrestler to scrape
            year: Year to scrape matches for
        """
        if wrestler_id == -1:
            logger.warning("Skipping match refresh for sentinel wrestler_id -1")
            return

        name = self.wrestler_db.get_name(wrestler_id)
        logger.info("{} | Scraping {} for {}", wrestler_id, year, name)
        matches, available_years = self.scraper.scrape_matches(wrestler_id, year)

        self.wrestler_db.save_matches_for_wrestler(wrestler_id, matches, year)

        # Create stale stubs for any newly discovered years
        if available_years:
            logger.debug(
                "{} | Discovered {} available years: {}",
                wrestler_id,
                len(available_years),
                sorted(available_years),
            )
            self.wrestler_db.create_stale_match_stubs(wrestler_id, available_years)

    def refresh_all_matches(self, wrestler_id: int):
        """Scrape and update all matches for a wrestler.

        Args:
            wrestler_id: ID of wrestler to scrape
        """
        if wrestler_id == -1:
            logger.warning("Skipping full match refresh for sentinel wrestler_id -1")
            return

        name = self.wrestler_db.get_name(wrestler_id)
        logger.info("{} | Scraping all matches for {}", wrestler_id, name)
        matches = self.scraper.scrape_all_matches(wrestler_id)

        # matches is a list of match dicts which need to be grouped by year
        matches_by_year = {}
        for match in matches:
            year = match.get("date", "Unknown")[:4]
            if year.isdigit():
                year = int(year)
            else:
                logger.warning(
                    "Skipping match with unknown year for wrestler {}: {}",
                    wrestler_id,
                    match,
                )
                continue  # Skip matches with unknown year
            matches_by_year.setdefault(year, []).append(match)

        # Save all years with matches
        for year, matches in matches_by_year.items():
            self.wrestler_db.save_matches_for_wrestler(wrestler_id, matches, year=year)

        # Update timestamps for existing stub years that had no matches
        # This confirms they've been checked and prevents them showing as stale
        existing_years = self.wrestler_db.match_years_available(wrestler_id)
        for year in existing_years:
            if year not in matches_by_year:
                # This year exists in DB but had no matches - update timestamp to mark as checked
                self.wrestler_db.save_matches_for_wrestler(wrestler_id, [], year=year)

    def refresh_promotion(self, promotion_id: int):
        """Scrape and update promotion data.

        Args:
            promotion_id: ID of promotion to scrape
        """
        logger.info("{} | Scraping promotion", promotion_id)
        try:
            scraped_promotion = self.scraper.scrape_promotion(promotion_id)
            self.wrestler_db.save_promotion(promotion_id, scraped_promotion.to_dict())
            logger.success(
                "{} | Saved promotion: {}", promotion_id, scraped_promotion.name()
            )
        except Exception as e:
            logger.error("{} | Failed to scrape promotion: {}", promotion_id, e)

    def _guess_likely_match_year_range(self, profile) -> tuple[int, int]:
        """Guess a range of years most likely to have matches for a newly discovered wrestler.

        Uses career start date to start scraping from the beginning:
        - If career start year is available: use that year (to find earliest matches)
        - If no career start data: use 1970 (safest bet for active wrestlers)

        Args:
            profile: CMProfile object with career_start() method

        Returns:
            Year (int) most likely to have match data
        """
        career_start = profile.career_start()
        career_end = profile.career_end()

        if career_end:
            try:
                if len(career_end) == 4:  # Just year "YYYY"
                    end_year = int(career_end)
                else:  # Full date "YYYY-MM-DD"
                    end_year = int(career_end.split("-")[0])
            except (ValueError, AttributeError) as e:
                logger.debug("Could not parse career end '{}': {}", career_end, e)
                end_year = THIS_YEAR - 1
        else:
            end_year = THIS_YEAR - 1

        if career_start:
            # Extract year from career_start (could be YYYY-MM-DD or just YYYY)
            try:
                if len(career_start) == 4:  # Just year "YYYY"
                    start_year = int(career_start)
                else:  # Full date "YYYY-MM-DD"
                    start_year = int(career_start.split("-")[0])

                logger.debug("Career started in {}, using that year", start_year)

            except (ValueError, AttributeError) as e:
                logger.debug("Could not parse career start '{}': {}", career_start, e)
                start_year = end_year
        else:
            # Fallback: previous year is safest bet for active wrestlers
            logger.debug("No career start data, defaulting to end year")
            start_year = end_year
        # Fallback: previous year is safest bet for active wrestlers
        logger.debug("No career start data, defaulting to previous year")
        return (start_year, end_year)

    def execute_work_item(self, item: WorkItem):
        """Execute a work item by dispatching to the appropriate operation.

        Args:
            item: WorkItem with operation, object_id, and optional year

        Raises:
            ValueError: If operation type is unknown
        """
        if item.operation == "refresh_profile":
            self.refresh_profile(item.object_id)
        elif item.operation == "refresh_matches":
            if item.year is None:
                logger.error(
                    "refresh_matches operation requires year for wrestler {}",
                    item.object_id,
                )
                return
            self.refresh_matches_for_year(item.object_id, item.year)
        elif item.operation == "refresh_all_matches":
            self.refresh_all_matches(item.object_id)
        elif item.operation == "refresh_promotion":
            self.refresh_promotion(item.object_id)
        else:
            raise ValueError(f"Unknown work item operation: {item.operation}")
        if item.note:
            logger.info(
                "{} | {}",
                item.object_id,
                item.note,
            )
