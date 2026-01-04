"""Migrate existing match data to populate promotions_worked field."""

from loguru import logger

from joshirank.joshidb import reopen_rw


def migrate_promotions_worked():
    """Populate promotions_worked field for all existing match records."""
    with reopen_rw() as db:
        # First, add the column if it doesn't exist
        cursor = db.sqldb.cursor()
        try:
            cursor.execute("ALTER TABLE matches ADD COLUMN promotions_worked TEXT")
            db.sqldb.commit()
            logger.info("Added promotions_worked column to matches table")
        except Exception as e:
            logger.info("Column promotions_worked already exists or error: {}", e)
        finally:
            cursor.close()

        # Get all wrestler IDs that have match data
        cursor = db.sqldb.cursor()
        cursor.execute("SELECT DISTINCT wrestler_id FROM matches")
        wrestler_ids = [row[0] for row in cursor.fetchall()]
        cursor.close()

        logger.info("Found {} wrestlers with match data", len(wrestler_ids))

        # For each wrestler, re-process all their match years
        count = 0
        for wid in wrestler_ids:
            years = db.match_years_available(wid)
            for year in years:
                # This will recompute and save promotions_worked
                db.update_matches_from_matches(wid)
            count += 1
            if count % 100 == 0:
                logger.info("Processed {}/{} wrestlers", count, len(wrestler_ids))

        logger.success("Migration complete! Processed {} wrestlers", count)


if __name__ == "__main__":
    migrate_promotions_worked()
