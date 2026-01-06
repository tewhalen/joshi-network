#!/usr/bin/env python
"""Migration: add and populate 'career_end' column in wrestlers table.

- Adds the TEXT column 'career_end' if missing
- Parses 'End of in-ring career' from stored JSON (cm_profile_json)
  using flexible date parsing and populates the column in ISO format

This script performs a write operation on the default database via WrestlerDb.
"""

import json

from loguru import logger

from joshirank.cagematch.profile import CMProfile
from joshirank.cagematch.util import parse_cm_date_flexible
from joshirank.joshidb import wrestler_db


def column_exists(table: str, column: str) -> bool:
    rows = wrestler_db._select_and_fetchall(
        f"PRAGMA table_info({table})",
        (),
    )
    for row in rows:
        # PRAGMA table_info returns: cid, name, type, notnull, dflt_value, pk
        if len(row) >= 2 and row[1] == column:
            return True
    return False


def add_column_if_missing():
    if column_exists("wrestlers", "career_end"):
        logger.info("Column 'career_end' already exists; skipping ALTER TABLE.")
        return False

    logger.info("Adding column 'career_end' (TEXT) to wrestlers table...")
    with wrestler_db.writable():
        wrestler_db._execute_and_commit(
            "ALTER TABLE wrestlers ADD COLUMN career_end TEXT",
            (),
        )
    logger.success("Added column 'career_end'.")
    return True


def populate_career_end():
    rows = wrestler_db._select_and_fetchall(
        """
        SELECT wrestler_id, cm_profile_json
        FROM wrestlers
        WHERE cm_profile_json IS NOT NULL AND cm_profile_json != '{}'
        """,
        (),
    )

    total = len(rows)
    fixed = 0
    errors = 0

    logger.info("Populating career_end for {} wrestlers...", total)

    with wrestler_db.writable():
        for wrestler_id, json_str in rows:
            try:
                data = json.loads(json_str)
                profile = CMProfile.from_dict(wrestler_id, data)
                career_end_raw = profile.career_end()

                career_end_val = str(career_end_raw).strip()

                wrestler_db._execute_and_commit(
                    "UPDATE wrestlers SET career_end = ? WHERE wrestler_id = ?",
                    (career_end_val, wrestler_id),
                )
                fixed += 1
            except Exception as e:
                logger.error("Error updating {}: {}", wrestler_id, e)
                errors += 1

    logger.success("Populated career_end: {} updated, {} errors", fixed, errors)


def main():
    added = add_column_if_missing()
    populate_career_end()
    if added:
        logger.info("Migration completed: column added and values populated.")
    else:
        logger.info("Migration completed: values populated for existing column.")


if __name__ == "__main__":
    main()
