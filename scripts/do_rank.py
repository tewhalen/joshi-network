import datetime
import pathlib
from collections import Counter, defaultdict

import click
import jinja2
from loguru import logger
from tabulate import tabulate

from joshirank.all_matches import all_matches
from joshirank.analysis.promotion import (
    get_primary_promotion_for_year,
    get_short_primary_promotion_for_year,
)
from joshirank.joshidb import (
    get_name,
)
from joshirank.ranking.glicko2 import Player
from joshirank.ranking.record import Record

URL_TEMPLATE = "https://www.cagematch.net/?id=2&nr={w_id}&view=&page=4&gimmick=&year={year}&promotion=&region=&location=&arena=&showtype=&constellationType=Singles&worker="


class Wrestler(Player):
    record: Record
    last_month: datetime.date | None = None
    year_records: dict[int, Record]

    def __init__(self, *args, **kwargs):
        self.record = Record()
        self.year_records = defaultdict(Record)
        self.last_month = None
        super().__init__(*args, **kwargs)

    def y_record(self, month) -> Record:
        return self.year_records[month.year]

    def add_wld(self, wins, losses, draws):
        self.record += (wins, losses, draws)


class Ranker:
    """
    A class to manage the ranking process for a given year.


    """

    wrestler_objects: dict[str, Wrestler]
    start_rating: int = 1500
    start_rd: int = 400

    def __init__(self, year: int, by_week: bool = False):
        self.year = year
        self.by_week = by_week
        self.wrestler_objects = {}
        self.rank_history = {}
        self.record_history = {}

    def get_wrestler(self, wrestler_id: str) -> Wrestler:
        if wrestler_id in self.wrestler_objects:
            return self.wrestler_objects[wrestler_id]
        else:
            start_rating = self.start_rating
            start_rd = self.start_rd
            new_object = Wrestler(rating=start_rating, rd=start_rd)
            self.wrestler_objects[wrestler_id] = new_object
            return new_object

    def matches_by_month(self) -> dict[tuple[int, int], list[dict]]:
        """Returns a dict of (year, month) -> list of matches"""
        matches_by_month = defaultdict(list)
        for match in all_matches(self.year):
            match_dict = dict(match)
            match_date = match_dict["date"]
            if match_date == "Unknown":
                continue
            date_obj = datetime.date.fromisoformat(match_date)
            year = date_obj.year
            month = date_obj.month
            matches_by_month[(year, month)].append(match_dict)
        return matches_by_month

    def matches_by_week(self) -> dict[tuple[int, int], list[dict]]:
        """Returns a dict of (year, week) -> list of matches"""
        matches_by_week = defaultdict(list)
        for match in all_matches(self.year):
            match_dict = dict(match)
            match_date = match_dict["date"]
            if match_date == "Unknown":
                continue
            date_obj = datetime.date.fromisoformat(match_date)
            year, week, _ = date_obj.isocalendar()
            matches_by_week[(year, week)].append(match_dict)
        return matches_by_week

    def matches_to_result_vectors(self, matches: list[dict]):
        """Given a list of matches, return structured result vectors needed for Glicko2 update.
        This will be a list of tuples wrestler_id, (opponent_rating, opponent_rd, outcomes)
        """
        result_vectors = defaultdict(
            lambda: ([], [], [])
        )  # wrestler_id -> (opp_rating, opp_rd, outcomes)
        for match in matches:
            for wid_a in match["side_a"]:
                w_a = self.get_wrestler(wid_a)
                for wid_b in match["side_b"]:
                    w_b = self.get_wrestler(wid_b)
                    result_vectors[wid_a][0].append(w_b.rating)
                    result_vectors[wid_a][1].append(w_b.rd)
                    result_vectors[wid_b][0].append(w_a.rating)
                    result_vectors[wid_b][1].append(w_a.rd)
                if match["is_victory"]:
                    result_vectors[wid_a][2].append(1)  # win
                    result_vectors[wid_b][2].append(0)  # loss
                else:  # draw
                    result_vectors[wid_a][2].append(0.5)  # draw
                    result_vectors[wid_b][2].append(0.5)  # draw

        return result_vectors

    def main(self):
        # iterate over all the intervals in order
        if self.by_week:
            matches_by_interval = self.matches_by_week()
        else:
            matches_by_interval = self.matches_by_month()

        all_intervals = list(matches_by_interval.keys())
        all_intervals.sort()

        for interval in all_intervals:
            results = self.matches_to_result_vectors(matches_by_interval[interval])
            seen_this_interval = set()
            # now update each wrestler
            for wrestler_id, (opp_ratings, opp_rds, outcomes) in results.items():
                seen_this_interval.add(wrestler_id)
                wrestler = self.get_wrestler(wrestler_id)
                wrestler.add_wld(
                    sum(1 for o in outcomes if o == 1),
                    sum(1 for o in outcomes if o == 0),
                    sum(1 for o in outcomes if o == 0.5),
                )
                wrestler.update_player(
                    opp_ratings,
                    opp_rds,
                    outcomes,
                )
            for wrestler_id in self.wrestler_objects:
                if wrestler_id not in seen_this_interval:
                    wrestler = self.get_wrestler(wrestler_id)
                    wrestler.did_not_compete()

    def current_rankings_table(self):
        rankings = self.current_rankings()

        output = []
        for i, d in enumerate(rankings, start=1):
            p = self.wrestler_objects[d["id"]]
            # name = db.get_name(name)
            # output.append(
            #    f"{i:3} {name:20} {rating:.0f} ({rd:.0f}) {p.record} {p.y_record(month)}"
            # )
            html_link = (
                '<a href="'
                + URL_TEMPLATE.format(w_id=d["id"], year=self.year)
                + '">{}</a>'.format(get_name(d["id"]))
            )

            output.append(
                [
                    i,
                    html_link,
                    get_short_primary_promotion_for_year(d["id"], self.year),
                    f"{d['rating']:.0f}",
                    f"{d['rd']:.0f}",
                    d["record"],
                ]
            )

        return tabulate(
            output,
            tablefmt="unsafehtml",
            headers=[
                "Rank",
                "Name",
                "Promotion",
                "Rating",
                "RD",
                "Record",
            ],
        )

    def current_rankings(self):
        rankings = [
            {
                "id": wrestler_id,
                "rating": p.rating,
                "rd": p.rd,
                "record": p.record,
            }
            for wrestler_id, p in self.wrestler_objects.items()
            if p.record.total_matches() >= 5
        ]
        rankings.sort(key=lambda x: x["rating"], reverse=True)
        return rankings

    def display_upsets_and_squashes(
        self,
    ):
        all_opponents, all_outcomes = self.db.singles_outcomes_by_month(month)

        for wrestler in all_opponents:
            p = self.wrestler_objects[wrestler]

            opponents = all_opponents[wrestler]
            results = all_outcomes[wrestler]
            upset_wins = [
                opp
                for opp, outcome in zip(opponents, results)
                if self.result_is_upset(wrestler, opp, outcome)
            ]
            for opp in upset_wins:
                print(
                    "Upset: {} ({:.0f} / {}) def. {} ({:.0f} / {})".format(
                        wrestler,
                        p.rating,
                        p.record,
                        opp,
                        self.wrestler_objects[opp].rating,
                        self.wrestler_objects[opp].record,
                    )
                )
            squashes = [
                opp
                for opp, outcome in zip(opponents, results)
                if self.result_is_squash(wrestler, opp, outcome)
            ]
            for opp in squashes:
                break
                print(
                    "Squash: {} ({:.0f} / {}) def. {} ({:.0f} / {})".format(
                        wrestler,
                        p.rating,
                        p.record,
                        opp,
                        self.wrestler_objects[opp].rating,
                        self.wrestler_objects[opp].record,
                    )
                )

    def result_is_upset(self, wrestler_a, wrestler_b, outcome) -> bool:
        if outcome == 1:
            wo_a = self.get_wrestler(wrestler_a)
            wo_b = self.get_wrestler(wrestler_b)
            if wo_a is None or wo_b is None:
                return False
            return wo_b.rating > wo_a.rating  # + wo_a.rd / 2
        else:
            return False

    def result_is_squash(self, wrestler_a, wrestler_b, outcome) -> bool:
        if outcome == 1:
            wo_a = self.get_wrestler(wrestler_a)
            wo_b = self.get_wrestler(wrestler_b)
            if wo_a is None or wo_b is None:
                return False
            return wo_b.rating < wo_a.rating - wo_a.rd * 2
        else:
            return False

    def save_rankings_to_html(self):
        # load the ranking template and render out the results to a file
        template_loader = jinja2.FileSystemLoader(searchpath="templates")
        template_env = jinja2.Environment(loader=template_loader)
        template = template_env.get_template("ranking.html")
        rendered_table = self.current_rankings_table()
        rendered_table = rendered_table.replace(
            "<table>", '<table id="ranking-table" class="display">'
        )

        # Get available years for navigation
        from scripts.list_available_years import get_available_years

        all_years = sorted(get_available_years())
        try:
            year_idx = all_years.index(self.year)
            prev_year = all_years[year_idx - 1] if year_idx > 0 else None
            next_year = (
                all_years[year_idx + 1] if year_idx < len(all_years) - 1 else None
            )
        except ValueError:
            prev_year = next_year = None

        rendered_html = template.render(
            the_table=rendered_table,
            year=self.year,
            sort_column=0,
            sort_order="asc",
            prev_year=prev_year,
            next_year=next_year,
        )

        # Create year subdirectory
        output_dir = pathlib.Path(f"output/{self.year}")
        output_dir.mkdir(parents=True, exist_ok=True)

        # Write to year subdirectory
        with open(output_dir / "ranking.html", "w") as f:
            f.write(rendered_html)


@click.command()
@click.argument(
    "year",
    type=int,
    default=datetime.datetime.now().year - 1,
)
@click.option(
    "--seed",
    is_flag=True,
    help="Use the previous year's rankings as the starting point",
)
@click.option(
    "--by-week", is_flag=True, help="Process matches by week instead of by month"
)
def main(year: int, seed: bool, by_week: bool):
    """Generate Glicko2 rankings from match data.

    YEAR: Year to generate rankings for (default: previous year)
    SEED: If set, seed the rankings from the previous year's results.

    Seeding calculates and then copies over rating and rating deviation (RD) from the previous year.

    """
    logger.info("Starting ranking process for {}...", year)
    logger.info("Using by-week mode: {}", by_week)

    if seed:
        logger.info("Seeding rankings for year {} from {}...", year, year - 1)
        r = Ranker(year - 1, by_week=by_week)
        r.main()
        previous_rankings = r.current_rankings()
        r = Ranker(year, by_week=by_week)
        for d in previous_rankings:
            # generate wrestler objects in the new year
            # copy over rating and rd
            wrestler = r.get_wrestler(d["id"])
            wrestler.rating = d["rating"]
            wrestler.rd = d["rd"]
    else:
        r = Ranker(year, by_week=by_week)
    logger.info("Generating rankings for year {}...", year)
    r.main()
    r.save_rankings_to_html()
    logger.success("Rankings saved to output/{}_ranking.html", year)


if __name__ == "__main__":
    main()
