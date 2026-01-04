"""Script to scrape wrestler profiles and matches from CageMatch.net."""

import sys
import time

import click
from loguru import logger

from joshirank.joshidb import WrestlerDb, reopen_rw
from joshirank.scrape.operations import OperationsManager
from joshirank.scrape.queue_builder import FilteredQueueBuilder, QueueBuilder
from joshirank.scrape.workqueue import WorkQueue

YEAR = time.localtime().tm_year


class ScrapingSession:
    """A scraping session to update wrestler profiles and matches."""

    wrestler_db: WrestlerDb

    def __init__(
        self, wrestler_db: WrestlerDb, queue_builder: QueueBuilder, dry_run=False
    ):
        self.ops_manager = OperationsManager(wrestler_db)
        self.wrestler_db = wrestler_db
        self.queue_builder = queue_builder
        self.dry_run = dry_run  # If True, don't make actual HTTP requests

    def build_work_queue(self) -> WorkQueue:
        """Build work queue using the configured queue builder."""
        return self.queue_builder.build()

    def process_queue(self, queue: WorkQueue):
        """Process work queue until done or rate limited."""
        total = len(queue)
        processed = 0

        if self.dry_run:
            logger.info("DRY RUN MODE: Showing what would be scraped...")

        while self.dry_run or self.ops_manager.keep_going():
            item = queue.dequeue()
            if not item:
                break

            try:
                if self.dry_run:
                    # Log what would be done
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
                else:
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

        if self.dry_run:
            logger.success("DRY RUN: Would process {} items", processed)
        else:
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
@click.option(
    "--force",
    is_flag=True,
    help="Force refresh all data, ignoring staleness checks",
)
def cli(tjpw_only, wrestler_ids, dry_run, stats_only, force):
    """Scrape wrestler profiles and matches from CageMatch.net."""
    setup_logging()

    with reopen_rw() as wrestler_db:
        if tjpw_only and wrestler_ids:
            logger.error("Cannot use both --tjpw-only and --wrestler-ids")
            return

        # Instantiate appropriate queue builder based on flags
        if force:
            logger.warning(
                "FORCE MODE: Ignoring staleness checks, will refresh all data"
            )

        if tjpw_only:
            from joshirank.queries import all_tjpw_wrestlers

            wrestler_filter = all_tjpw_wrestlers(wrestler_db)
            logger.info(
                "TJPW-only mode: limiting to {} wrestlers", len(wrestler_filter)
            )
            queue_builder = FilteredQueueBuilder(
                wrestler_db, wrestler_filter, force_refresh=force
            )
        elif wrestler_ids:
            wrestler_filter = set(int(wid.strip()) for wid in wrestler_ids.split(","))
            logger.info("Filtering to {} specific wrestler IDs", len(wrestler_filter))
            queue_builder = FilteredQueueBuilder(
                wrestler_db, wrestler_filter, force_refresh=force
            )
        else:
            queue_builder = QueueBuilder(wrestler_db, force_refresh=force)

        scraper = ScrapingSession(wrestler_db, queue_builder, dry_run=dry_run)

        if stats_only:
            logger.info("Stats-only mode: building work queue...")
            work_queue = scraper.build_work_queue()
            scraper.show_stats(work_queue)
        else:
            scraper.main()


if __name__ == "__main__":
    cli()
