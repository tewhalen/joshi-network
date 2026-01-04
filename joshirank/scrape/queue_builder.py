"""Queue builder for constructing work queues based on database staleness analysis."""

import time

from loguru import logger

from joshirank.joshidb import WrestlerDb
from joshirank.scrape.priority import (
    calculate_missing_wrestler_priority,
    get_gender_diverse_match_priority,
    get_match_refresh_priority,
    get_profile_refresh_priority,
)
from joshirank.scrape.scrapeinfo import WrestlerScrapeInfo
from joshirank.scrape.workqueue import WorkItem, WorkQueue

YEAR = time.localtime().tm_year


class QueueBuilder:
    """Builds work queues by analyzing database staleness and priorities.

    Priority scale (0-100, lower = higher priority):
    1: Missing wrestler profiles
    10: Stale female wrestler profiles, current year matches
    30: Stale non-female profiles, previous year matches
    50+: Historical matches (priority increases with age)

    During year transition (first 2 weeks of January), priorities shift:
    - Previous year gets HIGH priority (to finalize complete dataset)
    - Current year gets NORMAL priority (minimal data exists)
    """

    def __init__(
        self,
        wrestler_db: WrestlerDb,
        current_year: int = YEAR,
        force_refresh: bool = False,
    ):
        """Initialize queue builder.

        Args:
            wrestler_db: Database instance to query
            current_year: Current year for staleness calculations
            force_refresh: If True, ignore staleness checks and refresh everything
        """
        self.wrestler_db = wrestler_db
        self.scrape_info = WrestlerScrapeInfo(wrestler_db, current_year=current_year)
        self.current_year = current_year
        self.force_refresh = force_refresh

    def get_target_wrestlers(self) -> set[int]:
        """Get the set of wrestlers to consider for scraping.

        Default implementation returns all female wrestlers.
        Subclasses can override to implement filtering.
        """
        return set(self.wrestler_db.all_female_wrestlers())

    def should_discover_missing(self) -> bool:
        """Whether to discover missing wrestlers from the network.

        Returns True for full scraping, False when filtering to specific wrestlers.
        """
        return True

    def should_scrape_non_female_profiles(self) -> bool:
        """Whether to scrape non-female wrestler profiles.

        Returns True for full scraping, False when filtering.
        """
        return True

    def should_scrape_gender_diverse(self) -> bool:
        """Whether to scrape gender-diverse wrestlers.

        Returns True for full scraping, False when filtering.
        """
        return True

    def build(self) -> WorkQueue:
        """Build and return a work queue based on database state."""
        queue = WorkQueue()

        # 1. URGENT: Profiles of Missing wrestlers (referenced but not in DB)
        if self.should_discover_missing():
            for wid, count, opponents in self.scrape_info.find_missing_wrestlers():
                priority = calculate_missing_wrestler_priority(len(opponents))
                queue.enqueue(
                    WorkItem(
                        priority=priority,
                        wrestler_id=wid,
                        operation="refresh_profile",
                    )
                )

        # 2. HIGH: Stale female wrestler profiles
        for wid in self.get_target_wrestlers():
            if self.force_refresh or self.scrape_info.wrestler_info_is_stale(wid):
                priority = get_profile_refresh_priority(is_female=True)
                queue.enqueue(
                    WorkItem(
                        priority=priority,
                        wrestler_id=wid,
                        operation="refresh_profile",
                    )
                )

        # 3. NORMAL: Stale non-female profiles
        if self.should_scrape_non_female_profiles():
            for wid in self.wrestler_db.all_wrestler_ids():
                if self.force_refresh or self.scrape_info.wrestler_info_is_stale(wid):
                    if not self.wrestler_db.is_female(wid):
                        priority = get_profile_refresh_priority(is_female=False)
                        queue.enqueue(
                            WorkItem(
                                priority=priority,
                                wrestler_id=wid,
                                operation="refresh_profile",
                            )
                        )

        # 4. Match refreshes for female wrestlers (year-based priorities)
        for wid in self.get_target_wrestlers():
            available_years = self.wrestler_db.match_years_available(wid)
            is_active = self.scrape_info.is_recently_active(wid)
            importance = self.scrape_info.calculate_importance(wid)

            # Add missing current year only for recently active wrestlers
            if self.current_year not in available_years or self.force_refresh:
                priority = get_match_refresh_priority(
                    self.current_year, self.current_year, is_active, importance
                )
                if (
                    self.force_refresh or priority < 100
                ):  # Skip if priority is too low (inactive wrestlers)
                    queue.enqueue(
                        WorkItem(
                            priority=priority,
                            wrestler_id=wid,
                            operation="refresh_matches",
                            year=self.current_year,
                        )
                    )

        # 5. Gender-diverse wrestlers: always check current year matches
        if self.should_scrape_gender_diverse():
            for wid in self.wrestler_db.gender_diverse_wrestlers():
                available_years = self.wrestler_db.match_years_available(wid)
                importance = self.scrape_info.calculate_importance(wid)
                priority = get_gender_diverse_match_priority(
                    self.current_year, self.current_year, importance
                )

                if self.current_year not in available_years:
                    queue.enqueue(
                        WorkItem(
                            priority=priority,
                            wrestler_id=wid,
                            operation="refresh_matches",
                            year=self.current_year,
                        )
                    )
                # Check if existing current year data is stale (every 14 days)
                elif self.force_refresh or self.scrape_info.matches_need_refresh(
                    wid, self.current_year, is_gender_diverse=True
                ):
                    queue.enqueue(
                        WorkItem(
                            priority=priority,
                            wrestler_id=wid,
                            operation="refresh_matches",
                            year=self.current_year,
                        )
                    )

        # 6. Continue with rest of female wrestler match refreshes
        for wid in self.get_target_wrestlers():
            available_years = self.wrestler_db.match_years_available(wid)
            is_active = self.scrape_info.is_recently_active(wid)
            importance = self.scrape_info.calculate_importance(wid)

            # Add missing previous year for all wrestlers
            if (self.current_year - 1) not in available_years or self.force_refresh:
                priority = get_match_refresh_priority(
                    self.current_year - 1, self.current_year, is_active, importance
                )
                queue.enqueue(
                    WorkItem(
                        priority=priority,
                        wrestler_id=wid,
                        operation="refresh_matches",
                        year=self.current_year - 1,
                    )
                )

            # Check stale years (for years already in database)
            if self.force_refresh:
                # Force refresh all available years
                for year in available_years:
                    if year not in (
                        self.current_year,
                        self.current_year - 1,
                    ):  # Already handled above
                        priority = get_match_refresh_priority(
                            year, self.current_year, is_active, importance
                        )
                        queue.enqueue(
                            WorkItem(
                                priority=priority,
                                wrestler_id=wid,
                                operation="refresh_matches",
                                year=year,
                            )
                        )
            else:
                # Only refresh stale years
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


class FilteredQueueBuilder(QueueBuilder):
    """Queue builder that limits scraping to a specific set of wrestlers.

    This builder:
    - Only scrapes profiles/matches for wrestlers in the filter set
    - Skips missing wrestler discovery (avoids expanding to entire network)
    - Skips non-female and gender-diverse wrestlers outside the filter
    """

    def __init__(
        self,
        wrestler_db: WrestlerDb,
        wrestler_filter: set[int],
        current_year: int = YEAR,
        force_refresh: bool = False,
    ):
        """Initialize filtered queue builder.

        Args:
            wrestler_db: Database instance to query
            wrestler_filter: Set of wrestler IDs to limit scraping to
            current_year: Current year for staleness calculations
            force_refresh: If True, ignore staleness checks and refresh everything
        """
        super().__init__(wrestler_db, current_year, force_refresh)
        self.wrestler_filter = wrestler_filter

    def get_target_wrestlers(self) -> set[int]:
        """Return only female wrestlers in the filter set."""
        all_female = set(self.wrestler_db.all_female_wrestlers())
        return all_female.intersection(self.wrestler_filter)

    def should_discover_missing(self) -> bool:
        """Don't discover missing wrestlers when filtering."""
        return False

    def should_scrape_non_female_profiles(self) -> bool:
        """Don't scrape non-female profiles when filtering."""
        return False

    def should_scrape_gender_diverse(self) -> bool:
        """Don't scrape gender-diverse wrestlers when filtering."""
        return False
