#!/usr/bin/env python
"""List all years available in the database for ranking/network generation.

This script queries the joshi_wrestlers database to find all years that have
match data for female wrestlers, sorted in ascending order.

Usage:
    python scripts/list_available_years.py          # Print space-separated years
    python scripts/list_available_years.py --json   # Print as JSON array
"""

import json
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from joshirank.joshidb import wrestler_db


def get_available_years():
    """Query database for all years with match data for female wrestlers.

    Returns:
        list[int]: Sorted list of years that have match data
    """
    years = set()

    # get all unique match years in the match table which a wrestlers has match_count > 8

    sql = """SELECT DISTINCT year
             FROM matches
             WHERE match_count > 8
             ORDER BY year ASC;"""

    results = wrestler_db._select_and_fetchall(sql, ())
    years = {int(row[0]) for row in results if row[0] is not None}

    return list(years)


def main():
    """Print available years in requested format."""
    years = get_available_years()

    if not years:
        print("No years found in database", file=sys.stderr)
        sys.exit(1)

    # Check for --json flag
    if len(sys.argv) > 1 and sys.argv[1] == "--json":
        print(json.dumps(years))
    else:
        # Print as space-separated string (suitable for Makefile)
        print(" ".join(str(year) for year in years))


if __name__ == "__main__":
    main()
