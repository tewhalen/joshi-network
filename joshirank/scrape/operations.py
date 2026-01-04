"""Scraping operations for wrestler profiles and matches."""

import time

from loguru import logger

from joshirank.cagematch.scraper import CageMatchScraper
from joshirank.joshidb import WrestlerDb
from joshirank.scrape.workqueue import WorkItem

YEAR = time.localtime().tm_year


class OperationsManager:
    """Manages scraping operations and HTTP session."""

    def __init__(self, wrestler_db: WrestlerDb):
        """Initialize operations manager.

        Args:
            wrestler_db: Database instance to update
        """
        self.wrestler_db = wrestler_db
        self.scraper = CageMatchScraper()

    def keep_going(self) -> bool:
        """Check if we should continue scraping (rate limit check).

        Returns:
            True if we should continue, False if rate limited
        """
        return self.scraper.keep_going()

    def seed_database(self):
        """Seed the database with known missing profiles."""
        logger.info("Seeding database with known missing profiles...")
        missing_wrestlers = [9232]
        for wid in missing_wrestlers:
            self.wrestler_db.save_profile_for_wrestler(wid, {"Missing Profile": True})
            self.wrestler_db.update_wrestler_from_profile(wid)
            self.wrestler_db.save_matches_for_wrestler(wid, [])

    def refresh_profile(self, wrestler_id: int):
        """Scrape and update wrestler profile.

        Args:
            wrestler_id: ID of wrestler to scrape
        """
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
        """Scrape and update matches for a specific year.

        Args:
            wrestler_id: ID of wrestler to scrape
            year: Year to scrape matches for
        """
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

    def execute_work_item(self, item: WorkItem):
        """Execute a work item by dispatching to the appropriate operation.

        Args:
            item: WorkItem with operation, wrestler_id, and optional year

        Raises:
            ValueError: If operation type is unknown
        """
        if item.operation == "refresh_profile":
            self.refresh_profile(item.wrestler_id)
        elif item.operation == "refresh_matches":
            if item.year is None:
                logger.error(
                    "refresh_matches operation requires year for wrestler {}",
                    item.wrestler_id,
                )
                return
            self.refresh_matches_for_year(item.wrestler_id, item.year)
        else:
            raise ValueError(f"Unknown work item operation: {item.operation}")
