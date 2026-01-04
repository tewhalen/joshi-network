#!/usr/bin/env python
"""Delete empty 2025 records for wrestlers who also have earlier stub records.

These wrestlers have empty 2025 match records but also have stub records from earlier
years, indicating they were inactive and shouldn't have 2025 data at all.
"""

from joshirank.joshidb import reopen_rw, wrestler_db


def find_wrestlers_to_clean():
    """Find wrestlers with empty 2025 and earlier stub records."""
    wrestlers_to_clean = []

    for wid in wrestler_db.all_wrestler_ids():
        available_years = wrestler_db.match_years_available(wid)

        if 2025 not in available_years:
            continue

        # Check if 2025 is empty
        matches_2025 = wrestler_db.get_matches(wid, 2025)
        if len(matches_2025) > 0:
            continue

        # Check for earlier stub records (before 2025)
        has_earlier_stubs = False
        for year in available_years:
            if year >= 2025:
                continue
            matches = wrestler_db.get_matches(wid, year)
            if len(matches) == 0:
                has_earlier_stubs = True
                break

        if has_earlier_stubs:
            wrestlers_to_clean.append(wid)

    return wrestlers_to_clean


def main():
    print("Finding wrestlers with empty 2025 records and earlier stubs...")
    wrestlers_to_clean = find_wrestlers_to_clean()

    print(f"Found {len(wrestlers_to_clean)} wrestlers to clean")

    if len(wrestlers_to_clean) == 0:
        print("Nothing to do!")
        return

    # Show sample
    print("\nSample of wrestlers to be cleaned:")
    for wid in wrestlers_to_clean[:10]:
        name = wrestler_db.get_name(wid)
        print(f"  {wid:6d} | {name}")

    if len(wrestlers_to_clean) > 10:
        print(f"  ... and {len(wrestlers_to_clean) - 10} more")

    response = input(
        f"\nDelete 2025 records for these {len(wrestlers_to_clean)} wrestlers? [y/N]: "
    )
    if response.lower() != "y":
        print("Cancelled.")
        return

    print("\nDeleting empty 2025 records...")
    with reopen_rw() as db:
        cursor = db.sqldb.cursor()
        for i, wid in enumerate(wrestlers_to_clean, 1):
            cursor.execute(
                "DELETE FROM matches WHERE wrestler_id=? AND year=?", (wid, 2025)
            )
            if i % 100 == 0:
                print(f"  Processed {i}/{len(wrestlers_to_clean)}...")

        db.sqldb.commit()

    print(f"\nDeleted 2025 records for {len(wrestlers_to_clean)} wrestlers")
    print("Done!")


if __name__ == "__main__":
    main()
