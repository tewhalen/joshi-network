import datetime

import click
from loguru import logger

import joshirank.analysis.promotion
from joshirank.joshidb import wrestler_db


def anniversary_within_days(debut_date: datetime.date, days: int) -> bool:
    """Returns true if the anniversary of debut_date is within `days` of today."""
    today = datetime.date.today()
    # this will fail on Feb 29 debut dates!
    if debut_date.month == 2 and debut_date.day == 29:
        debut_date = debut_date.replace(day=28)
    this_year_anniversary = debut_date.replace(year=today.year)
    delta = abs((today - this_year_anniversary).days)
    return delta <= days


@click.command()
def main():
    for years, name, debut, promo in sorted(joshi_anniversaries()):
        print(f"{years:<3} {name}: Debut Date: {debut}  - Current Promotion: {promo}")


def joshi_anniversaries():
    """Analyze Joshi anniversaries."""
    # look through all joshi wresltlers and find their debut anniversaries
    # if anniversary is +/- 30 days from today, print out the wrestler name and debut date
    # and how many years since debut and what promotion they're currently in

    for wrestler_id in wrestler_db.all_female_wrestlers():
        if joshirank.analysis.promotion.is_japanese(wrestler_id):
            if joshirank.analysis.promotion.wrestler_is_retired(wrestler_id):
                continue
            wrestler_info = wrestler_db.get_wrestler(wrestler_id)
            debut_date_str = wrestler_info.get("career_start", "")
            if not debut_date_str:
                continue
            try:
                debut_date = datetime.datetime.strptime(
                    debut_date_str, "%Y-%m-%d"
                ).date()
            except ValueError:
                continue
            today = datetime.date.today()
            career_length = today - debut_date

            # if debut anniversary is within 30 days of today

            if anniversary_within_days(debut_date, 60):
                years_since_debut = today.year - debut_date.year
                current_promotion = (
                    joshirank.analysis.promotion.get_primary_promotion_for_year(
                        wrestler_id, today.year - 1
                    )
                    or "Unknown"
                )
                wrestler_name = wrestler_db.get_name(wrestler_id)
                yield years_since_debut, wrestler_name, debut_date, current_promotion


if __name__ == "__main__":
    main()
