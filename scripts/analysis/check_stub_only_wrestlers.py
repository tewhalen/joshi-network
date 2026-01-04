"""Check for wrestlers with only stub records (no actual matches)."""

from joshirank.joshidb import wrestler_db


def find_stub_only_wrestlers():
    """Find non-female wrestlers who have no matches but only stub records from 2025/2026."""

    stub_only_wrestlers = []

    for wrestler_id in wrestler_db.all_wrestler_ids():
        # Skip female wrestlers - we only want to see non-female wrestlers
        if not wrestler_db.is_female(wrestler_id):
            continue

        # Get all years available
        years = wrestler_db.match_years_available(wrestler_id)

        if not years:
            continue

        # Check if any year has actual matches
        has_any_matches = False
        for year in years:
            matches = wrestler_db.get_matches(wrestler_id, year)
            if matches:  # Has actual matches
                has_any_matches = True
                break

        # If no matches at all, and only has 2025/2026 stub records
        if not has_any_matches:
            if years.issubset({2025, 2026}):
                name = wrestler_db.get_name(wrestler_id)
                stub_only_wrestlers.append((wrestler_id, name, sorted(years)))

    return stub_only_wrestlers


if __name__ == "__main__":
    wrestlers = find_stub_only_wrestlers()

    print(
        f"Found {len(wrestlers)} non-female wrestlers with only stub records from 2025/2026:"
    )
    print()

    for wid, name, years in sorted(wrestlers, key=lambda x: x[0]):
        print(f"  {wid:5d} - {name:30s} (stub years: {years})")

    print()
    print(f"Total: {len(wrestlers)} female wrestlers")
