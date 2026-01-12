#!/usr/bin/env python
"""Delete empty records for wrestlers that are earlier than 2026.

Because we're fairly confident that we've got a recent scrape of all data,
we can delete empty match-year records, since they're unlikely to be stubs
and more likely to be wrestlers who simply had no matches that year.
"""

import json
import sys

from joshirank.joshidb import wrestler_db


def find_empty_match_records():
    """Find all empty match records earlier than 2026"""
    empty_records = {}

    sql = """SELECT wrestler_id, year, cm_matches_json FROM matches WHERE year < 2026 
    and match_count = 0 ORDER BY wrestler_id, year"""

    results = wrestler_db._select_and_fetchall(sql, ())
    for row in results:
        wrestler_id, year, cm_match_json = row
        matches = json.loads(cm_match_json)
        if len(matches) != 0:
            continue
        if wrestler_id not in empty_records:
            empty_records[wrestler_id] = []
        empty_records[wrestler_id].append(year)

    return empty_records


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
    print("Finding wrestlers with empty records prior to 2026...")
    empty_records = find_empty_match_records()
    print(f"Found {len(empty_records)} wrestlers with empty records prior to 2026")
    print(
        f"Found {sum(len(years) for years in empty_records.values())} total empty records prior to 2026"
    )

    # Show sample
    print("\nSample of wrestlers to be cleaned:")
    for wid in list(empty_records.keys())[:10]:
        name = wrestler_db.get_name(wid)
        print(f"  {wid:6d} | {name} | Empty years: {empty_records[wid]}")

    if len(empty_records) > 10:
        print(f"  ... and {len(empty_records) - 10} more")

    response = input(
        f"\nDelete empty records for these {len(empty_records)} wrestlers? [y/N]: "
    )
    if response.lower() != "y":
        print("Cancelled.")
        return

    print("\nDeleting empty 2025 records...")
    with wrestler_db.writable() as db:
        for i, wid in enumerate(empty_records.keys(), 1):
            empty_years = empty_records[wid]
            # delete the records for this wrestler where year is in that list of years
            db._execute(
                "DELETE FROM matches WHERE wrestler_id=? AND year IN ({})".format(
                    ",".join("?" * len(empty_years))
                ),
                (wid, *empty_years),
            )
            if i % 100 == 0:
                print(f"  Processed {i}/{len(empty_records)}...")

    print(f"\nDeleted empty records for {len(empty_records)} wrestlers")
    print("Done!")


if __name__ == "__main__":
    main()
