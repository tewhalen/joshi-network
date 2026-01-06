"""Script to scrape wrestler profiles and matches from CageMatch.net."""

import shutil
import sqlite3
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

import click
from loguru import logger

from joshirank.analysis.promotion import ever_worked_promotion
from joshirank.joshidb import WrestlerDb, wrestler_db
from joshirank.scrape.operations import OperationsManager
from joshirank.scrape.queue_builder import (
    FilteredQueueBuilder,
    FullQueueBuilder,
    QueueBuilder,
)
from joshirank.scrape.workqueue import WorkQueue

YEAR = time.localtime().tm_year


def rotate_backups(backup_dir: Path):
    """Rotate backups to keep only recent ones.

    Retention policy:
    - Today: Keep up to 3 most recent backups
    - Yesterday: Keep 1 most recent backup
    - 2 days ago: Keep 1 most recent backup
    - Older: Delete all

    Args:
        backup_dir: Directory containing backup files
    """
    if not backup_dir.exists():
        return

    # Get all backup files sorted by modification time (newest first)
    backup_files = sorted(
        backup_dir.glob("joshi_wrestlers_*.sqlite3"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )

    if not backup_files:
        return

    now = datetime.now()
    today = now.date()
    yesterday = today - timedelta(days=1)
    two_days_ago = today - timedelta(days=2)

    # Group backups by date
    backups_by_date = {}
    for backup_file in backup_files:
        file_time = datetime.fromtimestamp(backup_file.stat().st_mtime)
        file_date = file_time.date()
        backups_by_date.setdefault(file_date, []).append(backup_file)

    files_to_delete = []

    # Process each date
    for file_date, files in backups_by_date.items():
        if file_date == today:
            # Keep up to 3 most recent from today
            if len(files) > 3:
                files_to_delete.extend(files[3:])
        elif file_date == yesterday:
            # Keep 1 most recent from yesterday
            if len(files) > 1:
                files_to_delete.extend(files[1:])
        elif file_date == two_days_ago:
            # Keep 1 most recent from 2 days ago
            if len(files) > 1:
                files_to_delete.extend(files[1:])
        else:
            # Delete all older backups
            files_to_delete.extend(files)

    # Delete old backups
    if files_to_delete:
        logger.info("Rotating backups: removing {} old backup(s)", len(files_to_delete))
        for backup_file in files_to_delete:
            logger.debug("Deleting old backup: {}", backup_file.name)
            backup_file.unlink()


def backup_database(source_path: Path, backup_dir: Path) -> Path:
    """Safely backup the SQLite database using SQLite's backup API.

    Args:
        source_path: Path to the source database file
        backup_dir: Directory to store the backup

    Returns:
        Path to the created backup file
    """
    backup_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = backup_dir / f"joshi_wrestlers_{timestamp}.sqlite3"

    logger.info("Creating database backup: {}", backup_path.name)

    # Use SQLite's backup API for safe, atomic backup
    source_conn = sqlite3.connect(source_path)
    backup_conn = sqlite3.connect(backup_path)

    with backup_conn:
        source_conn.backup(backup_conn)

    source_conn.close()
    backup_conn.close()

    # Verify backup integrity
    verify_conn = sqlite3.connect(backup_path)
    try:
        cursor = verify_conn.cursor()
        cursor.execute("PRAGMA integrity_check")
        result = cursor.fetchone()
        if result[0] != "ok":
            logger.error("Backup integrity check failed!")
            backup_path.unlink()  # Delete corrupted backup
            raise RuntimeError("Database backup failed integrity check")
        verify_conn.close()
    except Exception as e:
        verify_conn.close()
        raise

    logger.success("Database backup created successfully")

    # Rotate old backups
    rotate_backups(backup_dir)

    return backup_path


class ScrapingSession:
    """A scraping session to update wrestler profiles and matches."""

    wrestler_db: WrestlerDb

    def __init__(
        self,
        wrestler_db: WrestlerDb,
        queue_builder: QueueBuilder,
        dry_run=False,
        slow=False,
    ):
        self.ops_manager = OperationsManager(wrestler_db, slow=slow)
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
                    if item.operation == "refresh_promotion":
                        promo_name = self.wrestler_db.get_promotion_name(item.object_id)
                        logger.info(
                            "[Priority {}] {} | {} ({})",
                            item.priority,
                            item.operation,
                            promo_name,
                            item.object_id,
                        )
                    else:
                        name = self.wrestler_db.get_name(item.object_id)
                        year_str = f" ({item.year})" if item.year else ""
                        logger.info(
                            "[Priority {}] {} | {} ({}){}",
                            item.priority,
                            item.operation,
                            name,
                            item.object_id,
                            year_str,
                        )
                else:
                    # make the db writable and execute the item
                    with self.wrestler_db.writable():
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
                logger.error("Failed processing {}: {}", item.object_id, e)

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
        objects = set()  # Could be wrestlers or promotions

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
            objects.add(item.object_id)

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

        logger.info("\nUnique objects (wrestlers/promotions): {}", len(objects))
        logger.info("=" * 50)

    def main(self):
        """Main scraping session logic using work queue."""

        logger.success("Starting scraping session with work queue...")

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
    "--promotion",
    type=int,
    help="Promotion ID to scrape (overrides other filters, scrapes all wrestlers in that promotion)",
)
@click.option("--matches-only", is_flag=True, help="Only scrape matches!")
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
@click.option(
    "--no-backup",
    is_flag=True,
    help="Skip database backup (not recommended)",
)
@click.option(
    "--slow",
    is_flag=True,
    help="Slow mode: 7s between requests, no session limit",
)
def cli(
    tjpw_only,
    wrestler_ids,
    dry_run,
    stats_only,
    force,
    no_backup,
    slow,
    promotion,
    matches_only,
):
    """Scrape wrestler profiles and matches from CageMatch.net."""
    setup_logging()

    # Create backup before opening database for writing (unless dry-run or stats-only)
    if not dry_run and not stats_only and not no_backup:
        db_path = Path("data/joshi_wrestlers.sqlite3")
        backup_dir = Path("data/backups")
        try:
            backup_database(db_path, backup_dir)
        except Exception as e:
            logger.error("Failed to create backup: {}", e)
            logger.warning(
                "Proceeding without backup (use --no-backup to skip this warning)"
            )

    # open database for writing and initialize it
    with wrestler_db.writable():
        wrestler_db.initialize_sql_db()

    if tjpw_only and wrestler_ids:
        logger.error("Cannot use both --tjpw-only and --wrestler-ids")
        return

    # Instantiate appropriate queue builder based on flags
    if force:
        logger.warning("FORCE MODE: Ignoring staleness checks, will refresh all data")

    if tjpw_only:
        from joshirank.analysis.promotion import all_tjpw_wrestlers

        wrestler_filter = all_tjpw_wrestlers()
        logger.info("TJPW-only mode: limiting to {} wrestlers", len(wrestler_filter))
        queue_builder = FilteredQueueBuilder(
            wrestler_db, wrestler_filter, force_refresh=force
        )
    elif promotion:
        promo_name = wrestler_db.get_promotion_name(int(promotion))
        logger.info(
            "Promotion mode: scraping all wrestlers from promotion {} ({})",
            promo_name,
            promotion,
        )
        wrestler_filter = ever_worked_promotion(int(promotion))
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
        queue_builder = FullQueueBuilder(wrestler_db, force_refresh=force)

    if matches_only:
        queue_builder.only_matches = True
        logger.info("Matches-only mode: only scraping matches")
    if slow:
        logger.warning("SLOW MODE: 7s between requests, no session limit")

    scraper = ScrapingSession(wrestler_db, queue_builder, dry_run=dry_run, slow=slow)

    if stats_only:
        logger.info("Stats-only mode: building work queue...")
        work_queue = scraper.build_work_queue()
        scraper.show_stats(work_queue)
    else:
        scraper.main()


if __name__ == "__main__":
    cli()
