"""Queue builder for constructing work queues based on database staleness analysis."""

import time
from abc import abstractmethod

from loguru import logger

from joshirank.analysis.gender import gender_diverse_wrestlers
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

    @abstractmethod
    def build(self) -> WorkQueue:
        """Build and return a work queue based on database state."""
        pass

    def stale_profile_tasks(self, wid):
        if self.force_refresh or self.scrape_info.wrestler_info_is_stale(wid):
            priority = get_profile_refresh_priority(is_female=True)

            yield WorkItem(
                priority=priority,
                object_id=wid,
                operation="refresh_profile",
            )

    def stale_match_tasks(self, wid):
        """For a given wrestler, generate match-scraping tasks
        for missing or stale match-years.

        In general, any sucessful match-year scrape will separately
        create any midding stub stale match-years in the database for
        valid match-years.

        So, we only need to ensure that active wrestlers have a task created
        for the current year, since otherwise it won't be created until the previous
        year refreshes (and that's on a slower refresh cycle.)

        Other than that, we should rely upon created stale stubs to trigger
        match-year refreshes on a normal schedule.

        Efficiency heuristic: Use refresh_all_matches when many years are stale.
        Threshold: 3+ stale years -> use refresh_all_matches (1 request)
        Otherwise: use year-by-year refresh (1 request per year)
        """

        available_years = self.wrestler_db.match_years_available(wid)
        is_active = self.scrape_info.is_recently_active(wid)
        importance = self.scrape_info.calculate_importance(wid)

        # Collect all years that need refreshing
        years_to_refresh = []

        if not self.force_refresh:
            # Normal mode: add missing current year for active wrestlers
            if is_active and self.current_year not in available_years:
                priority = get_match_refresh_priority(
                    self.current_year, self.current_year, is_active, importance
                )
                if priority < 100:
                    years_to_refresh.append((self.current_year, priority))

            # Check stale years (for years already in database)
            stale_years = self.scrape_info.get_stale_match_years(wid)
            years_to_refresh.extend(stale_years)
        else:
            # Force mode: refresh all available years
            for year in available_years:
                priority = get_match_refresh_priority(
                    year, self.current_year, is_active, importance
                )
                years_to_refresh.append((year, priority))

            # Add current year if not already in available_years (for active wrestlers)
            if is_active and self.current_year not in available_years:
                priority = get_match_refresh_priority(
                    self.current_year, self.current_year, is_active, importance
                )
                years_to_refresh.append((self.current_year, priority))

        # Decide: refresh_all_matches vs year-by-year
        # Use refresh_all_matches if 3+ years need refreshing (more efficient)
        if len(years_to_refresh) >= 3:
            # Use the highest priority (lowest number) from the years
            best_priority = min((p for y, p in years_to_refresh), default=50)
            yield WorkItem(
                priority=best_priority,
                object_id=wid,
                operation="refresh_all_matches",
            )
        else:
            # Refresh year-by-year (more targeted)
            for year, priority in years_to_refresh:
                yield WorkItem(
                    priority=priority,
                    object_id=wid,
                    operation="refresh_matches",
                    year=year,
                )

    def _collect_promotion_ids(self) -> dict:
        """Collect all promotion IDs from match data with frequency counts."""
        from collections import Counter

        promotion_counter = Counter()

        # Only look at female wrestlers' matches for promotion discovery
        for wrestler_id in self.get_target_wrestlers():
            for year in self.wrestler_db.match_years_available(wrestler_id):
                match_info = self.wrestler_db.get_match_info(wrestler_id, year)
                promotions_worked = match_info.get("promotions_worked", {})

                for promotion_id, count in promotions_worked.items():
                    try:
                        promotion_counter[int(promotion_id)] += count
                    except (ValueError, TypeError):
                        continue

        return promotion_counter

    def _promotion_is_stale(self, promotion_id: int) -> bool:
        """Check if a promotion needs updating."""
        if not self.wrestler_db.promotion_exists(promotion_id):
            return True

        timestamp = self.wrestler_db.get_promotion_timestamp(promotion_id)
        return self.scrape_info.staleness_policy.promotion_is_stale(timestamp)


class FullQueueBuilder(QueueBuilder):
    """Full queue builder that scrapes all available data.

    This builder:
    - Discovers missing wrestlers by analyzing the network
    - Scrapes non-female and gender-diverse wrestler profiles
    - Collects promotion metadata for frequently referenced promotions
    - Implements comprehensive database maintenance
    """

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

    def should_scrape_promotions(self) -> bool:
        """Whether to scrape promotion metadata.

        Returns True for full scraping, False when filtering.
        """
        return True

    def build(self) -> WorkQueue:
        """Build and return a work queue based on database state."""
        queue = WorkQueue()

        # 1. URGENT: Profiles of Missing wrestlers (referenced but not in DB)
        if self.should_discover_missing():
            for wid, count, opponents in self.scrape_info.find_missing_wrestlers():
                priority = calculate_missing_wrestler_priority(
                    len(opponents),
                    wrestler_id=wid,
                    wrestler_db=self.wrestler_db,
                    opponent_ids=opponents,
                )
                queue.enqueue(
                    WorkItem(
                        priority=priority,
                        object_id=wid,
                        operation="refresh_profile",
                    )
                )

        # 2. Stale target wrestler profiles
        for wid in self.get_target_wrestlers():
            for item in self.stale_profile_tasks(wid):
                queue.enqueue(item)

        # 3. All stale non-female profiles
        if self.should_scrape_non_female_profiles():
            for wid in self.wrestler_db.all_wrestler_ids():
                if not self.wrestler_db.is_female(wid):
                    for task in self.stale_profile_tasks(wid):
                        queue.enqueue(task)

        # 4. Match refreshes for female wrestlers (year-based priorities)
        for wid in self.get_target_wrestlers():
            for match_item in self.stale_match_tasks(wid):
                queue.enqueue(match_item)

        # 5. LOW: Promotion data for frequently referenced promotions
        if self.should_scrape_promotions():
            promotion_counter = self._collect_promotion_ids()
            for promotion_id, frequency in promotion_counter.most_common():
                if self.force_refresh or self._promotion_is_stale(promotion_id):
                    # Priority based on frequency of promotion in match data
                    # Most common promotions get higher priority (lower number)
                    # Scale: 0 (most common) to 95 (rare)
                    priority = max(0, min(95, 95 - (frequency // 100)))
                    queue.enqueue(
                        WorkItem(
                            priority=priority,
                            object_id=promotion_id,
                            operation="refresh_promotion",
                        )
                    )

        # 6. Gender-diverse wrestlers: always check current year matches
        if self.should_scrape_gender_diverse():
            for wid in gender_diverse_wrestlers():
                available_years = self.wrestler_db.match_years_available(wid)
                importance = self.scrape_info.calculate_importance(wid)
                priority = get_gender_diverse_match_priority(
                    self.current_year, self.current_year, importance
                )

                if self.current_year not in available_years:
                    queue.enqueue(
                        WorkItem(
                            priority=priority,
                            object_id=wid,
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
                            object_id=wid,
                            operation="refresh_matches",
                            year=self.current_year,
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
        # all_female = set(self.wrestler_db.all_female_wrestlers())
        # return all_female.intersection(self.wrestler_filter)
        return self.wrestler_filter

    def build(self) -> WorkQueue:
        """Build and return a work queue based on database state."""
        queue = WorkQueue()

        # 1. Stale target profiles
        for wid in self.get_target_wrestlers():
            for item in self.stale_profile_tasks(wid):
                queue.enqueue(item)

        # 2. Stale match-years for target wrestlers (year-based priorities)
        for wid in self.get_target_wrestlers():
            for item in self.stale_match_tasks(wid):
                queue.enqueue(item)

        # 3. Opponents of target wrestlers who are missing profiles
        for wid in self.get_target_wrestlers():
            for missing_wid in self.scrape_info.find_missing_wrestlers_for_wrestler(
                wid
            ):
                if missing_wid in self.wrestler_filter:
                    priority = calculate_missing_wrestler_priority(10)
                    queue.enqueue(
                        WorkItem(
                            priority=priority,
                            object_id=missing_wid,
                            operation="refresh_profile",
                        )
                    )

        # 4. LOW: Promotion data for frequently referenced promotions

        promotion_counter = self._collect_promotion_ids()
        for promotion_id, frequency in promotion_counter.most_common():
            if self.force_refresh or self._promotion_is_stale(promotion_id):
                # Priority based on frequency of promotion in match data
                # Most common promotions get higher priority (lower number)
                # Scale: 0 (most common) to 95 (rare)
                priority = max(0, min(95, 95 - (frequency // 100)))
                queue.enqueue(
                    WorkItem(
                        priority=priority,
                        object_id=promotion_id,
                        operation="refresh_promotion",
                    )
                )

        logger.info("Built work queue with {} items", len(queue))
        return queue
