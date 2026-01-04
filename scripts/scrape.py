"""Script to scrape wrestler profiles and matches from CageMatch.net."""

import random
import sys
import time

import click
from loguru import logger

from joshirank.joshidb import WrestlerDb, reopen_rw
from joshirank.scrape.operations import OperationsManager
from joshirank.scrape.priority import (
    calculate_missing_wrestler_priority,
    get_gender_diverse_match_priority,
    get_match_refresh_priority,
    get_profile_refresh_priority,
)
from joshirank.scrape.scrapeinfo import WrestlerScrapeInfo
from joshirank.scrape.workqueue import WorkItem, WorkQueue

YEAR = time.localtime().tm_year


class ScrapingSession:
    """A scraping session to update wrestler profiles and matches."""

    wrestler_db: WrestlerDb

    def __init__(self, wrestler_db: WrestlerDb, wrestler_filter=None, dry_run=False):
        self.ops_manager = OperationsManager(wrestler_db)
        self.scrape_info = WrestlerScrapeInfo(wrestler_db, current_year=YEAR)
        self.wrestler_db = wrestler_db
        self.wrestler_filter = (
            wrestler_filter  # Optional set of wrestler IDs to limit scraping
        )
        self.dry_run = dry_run  # If True, don't make actual HTTP requests

    def get_target_wrestlers(self) -> set[int]:
        """Get the set of female wrestlers to scrape.

        If wrestler_filter is set, returns the intersection of female wrestlers
        and the filter set. Otherwise returns all female wrestlers.
        """
        all_female = set(self.wrestler_db.all_female_wrestlers())
        if self.wrestler_filter is not None:
            return all_female.intersection(self.wrestler_filter)
        return all_female

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

        # 1. URGENT: Profiles of Missing wrestlers (referenced but not in DB)
        # Skip this entirely when using a filter - only work on explicitly filtered wrestlers
        if not self.wrestler_filter:
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
            if self.scrape_info.wrestler_info_is_stale(wid):
                priority = get_profile_refresh_priority(is_female=True)
                queue.enqueue(
                    WorkItem(
                        priority=priority,
                        wrestler_id=wid,
                        operation="refresh_profile",
                    )
                )

        # 3. NORMAL: Stale non-female profiles
        # Skip this when using wrestler_filter to avoid scraping opponents
        if not self.wrestler_filter:
            for wid in self.wrestler_db.all_wrestler_ids():
                if self.scrape_info.wrestler_info_is_stale(wid):
                    if not self.wrestler_db.is_female(wid):
                        priority = get_profile_refresh_priority(is_female=False)
                        queue.enqueue(
                            WorkItem(
                                priority=PRIORITY_NORMAL,
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
            # Skip retired/inactive wrestlers to avoid wasting scraping quota
            if YEAR not in available_years:
                priority = get_match_refresh_priority(YEAR, YEAR, is_active, importance)
                if priority < 100:  # Skip if priority is too low (inactive wrestlers)
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
        if not self.wrestler_filter:
            for wid in self.wrestler_db.gender_diverse_wrestlers():
                available_years = self.wrestler_db.match_years_available(wid)
                importance = self.scrape_info.calculate_importance(wid)
                priority = get_gender_diverse_match_priority(YEAR, YEAR, importance)

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
        for wid in self.get_target_wrestlers():
            available_years = self.wrestler_db.match_years_available(wid)
            is_active = self.scrape_info.is_recently_active(wid)
            importance = self.scrape_info.calculate_importance(wid)

            # Add missing previous year for all wrestlers
            if (YEAR - 1) not in available_years:
                priority = get_match_refresh_priority(
                    YEAR - 1, YEAR, is_active, importance
                )
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

        if self.dry_run:
            logger.info("DRY RUN MODE: Showing what would be scraped...")
            while True:
                item = queue.dequeue()
                if not item:
                    break
                name = self.wrestler_db.get_name(item.wrestler_id)
                year_str = f" ({item.year})" if item.year else ""
                logger.info(
                    "[Priority {}] {} | {} ({}){}",
                    item.priority,
                    item.operation,
                    name,
                    item.wrestler_id,
                    year_str,
                )
                processed += 1
            logger.success("DRY RUN: Would process {} items", processed)
            return

        while self.ops_manager.keep_going():
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
                self.ops_manager.execute_work_item(item)
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

    def show_stats(self, queue: WorkQueue):
        """Display statistics about the work queue without processing it."""
        from collections import Counter

        total = len(queue)
        logger.info("Work Queue Statistics:")
        logger.info("=" * 50)
        logger.info("Total items: {}", total)

        # Count by operation type
        operations = Counter()
        priorities = Counter()
        years = Counter()
        wrestlers = set()

        # Peek at all items without dequeueing
        temp_items = []
        while True:
            item = queue.dequeue()
            if not item:
                break
            temp_items.append(item)
            operations[item.operation] += 1
            priority_bucket = (item.priority // 10) * 10  # Group by tens
            priorities[priority_bucket] += 1
            if item.year:
                years[item.year] += 1
            wrestlers.add(item.wrestler_id)

        # Re-queue items
        for item in temp_items:
            queue.enqueue(item)

        logger.info("\nOperations:")
        for op, count in sorted(operations.items()):
            logger.info("  {}: {}", op, count)

        logger.info("\nPriority distribution:")
        for priority, count in sorted(priorities.items()):
            logger.info("  {}-{}: {} items", priority, priority + 9, count)

        logger.info("\nYear distribution:")
        for year, count in sorted(years.items(), reverse=True):
            logger.info("  {}: {} items", year, count)

        logger.info("\nUnique wrestlers: {}", len(wrestlers))
        logger.info("=" * 50)

    def main(self):
        """Main scraping session logic using work queue."""

        logger.success("Starting scraping session with work queue...")
        self.ops_manager.seed_database()
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


@click.command()
@click.option(
    "--tjpw-only",
    is_flag=True,
    help="Only scrape TJPW wrestlers instead of all female wrestlers",
)
@click.option(
    "--wrestler-ids",
    help="Comma-separated list of wrestler IDs to scrape (e.g., 16547,9462,4629)",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Show what would be scraped without making HTTP requests",
)
@click.option(
    "--stats-only",
    is_flag=True,
    help="Show work queue statistics without scraping",
)
def cli(tjpw_only, wrestler_ids, dry_run, stats_only):
    """Scrape wrestler profiles and matches from CageMatch.net."""
    setup_logging()

    with reopen_rw() as wrestler_db:
        wrestler_filter = None

        if tjpw_only and wrestler_ids:
            logger.error("Cannot use both --tjpw-only and --wrestler-ids")
            return

        if tjpw_only:
            from joshirank.queries import all_tjpw_wrestlers

            wrestler_filter = all_tjpw_wrestlers(wrestler_db)
            logger.info(
                "TJPW-only mode: limiting to {} wrestlers", len(wrestler_filter)
            )
        elif wrestler_ids:
            wrestler_filter = set(int(wid.strip()) for wid in wrestler_ids.split(","))
            logger.info("Filtering to {} specific wrestler IDs", len(wrestler_filter))

        scraper = ScrapingSession(
            wrestler_db, wrestler_filter=wrestler_filter, dry_run=dry_run
        )

        if stats_only:
            logger.info("Stats-only mode: building work queue...")
            work_queue = scraper.build_work_queue()
            scraper.show_stats(work_queue)
        else:
            scraper.main()


if __name__ == "__main__":
    cli()
