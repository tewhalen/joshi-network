import csv
import datetime
from collections import defaultdict

import jinja2
from tabulate import tabulate

from joshirank.all_matches import all_matches
from joshirank.glicko2 import Player
from joshirank.joshidb import get_name, get_promotion, get_promotion_with_location
from joshirank.record import Record

URL_TEMPLATE = "https://www.cagematch.net/?id=2&nr={}&view=&page=4&gimmick=&year=2025&promotion=&region=&location=&arena=&showtype=&constellationType=Singles&worker="


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
    wrestler_objects: dict[str, Wrestler]

    def __init__(self):

        self.wrestler_objects = {}
        self.rank_history = {}
        self.record_history = {}

    def get_wrestler(self, wrestler_id: str) -> Wrestler:
        if wrestler_id in self.wrestler_objects:
            return self.wrestler_objects[wrestler_id]
        else:
            start_rating = 1500
            start_rd = 400
            new_object = Wrestler(rating=start_rating, rd=start_rd)
            self.wrestler_objects[wrestler_id] = new_object
            return new_object

    def matches_by_week(self) -> dict[tuple[int, int], list[dict]]:
        """Returns a dict of (year, week) -> list of matches"""
        matches_by_week = defaultdict(list)
        for match in all_matches():
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
        # iterate over all the weeks in order
        matches_by_week = self.matches_by_week()
        all_weeks = list(matches_by_week.keys())
        all_weeks.sort()
        for year_week in all_weeks:
            year, week = year_week

            results = self.matches_to_result_vectors(matches_by_week[year_week])
            seen_this_week = set()
            # now update each wrestler
            for wrestler_id, (opp_ratings, opp_rds, outcomes) in results.items():
                seen_this_week.add(wrestler_id)
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
                if wrestler_id not in seen_this_week:
                    wrestler = self.get_wrestler(wrestler_id)
                    wrestler.did_not_compete()

    def old_main(self):
        all_the_matches = list(dict(match) for match in all_matches())
        all_the_matches.sort(key=lambda x: x["date"])
        for match in all_the_matches:  # should sort by date
            # turn it back into a dict
            match_dict = dict(match)

            winner = self.get_wrestler(match_dict["side_a"][0])
            loser = self.get_wrestler(match_dict["side_b"][0])
            # print(winner, loser)
            if match_dict["is_victory"]:
                winner.add_wld(1, 0, 0)
                loser.add_wld(0, 1, 0)

                winner.update_player([loser.rating], [loser.rd], [1])
                loser.update_player([winner.rating], [winner.rd], [0])
            else:
                winner.add_wld(0, 0, 1)
                loser.add_wld(0, 0, 1)

                winner.update_player([loser.rating], [loser.rd], [0.5])
                loser.update_player([winner.rating], [winner.rd], [0.5])

        # self.display_upsets_and_squashes()
        # self.save_long_data()

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
                + URL_TEMPLATE.format(d["id"])
                + '">{}</a>'.format(get_name(d["id"]))
            )

            output.append(
                [
                    i,
                    html_link,
                    get_promotion_with_location(d["id"]),
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
        rendered_html = template.render(
            the_table=rendered_table, year=2025, sort_column=0, sort_order="asc"
        )
        with open("output/rankings.html", "w") as f:
            f.write(rendered_html)


if __name__ == "__main__":
    r = Ranker()
    r.main()
    r.save_rankings_to_html()
