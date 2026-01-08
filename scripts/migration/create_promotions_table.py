#!/usr/bin/env python3
"""Create the promotions table in the database.

This is a one-time migration script to add the promotions table
to existing databases.
"""

from loguru import logger

from joshirank.joshidb import reopen_rw


def main():
    logger.info("Creating promotions table...")

    with reopen_rw() as db:
        # The _create_promotions_table method will be called if it doesn't exist
        # when the database is opened in read-write mode
        db._create_promotions_table()

        logger.success("Promotions table created successfully")

        # Verify it worked
        all_promos = db.all_promotion_ids()
        logger.info("Current promotions in database: {}", len(all_promos))


if __name__ == "__main__":
    main()
