import csv
import datetime
from collections import defaultdict

from columnar import columnar

from joshirank.all_matches import all_matches
from joshirank.glicko2 import Player
from joshirank.joshidb import get_name, get_promotion
from joshirank.record import Record


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

    def main(self):
        # self.reset_wrestlers()
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

        self.display_current_rankings()
        # self.display_upsets_and_squashes()
        # self.save_long_data()

    def display_current_rankings(self):

        rankings = self.current_rankings()

        output = []
        for i, d in enumerate(rankings, start=1):
            p = self.wrestler_objects[d["id"]]
            # name = db.get_name(name)
            # output.append(
            #    f"{i:3} {name:20} {rating:.0f} ({rd:.0f}) {p.record} {p.y_record(month)}"
            # )
            output.append(
                [
                    i,
                    get_name(d["id"]),
                    d["id"],
                    get_promotion(d["id"]),
                    f"{d['rating']:.0f}",
                    f"{d['rd']:.0f}",
                    d["record"],
                ]
            )
        print(columnar(output, no_borders=True))

    def current_rankings(self):

        rankings = [
            {
                "id": wrestler_id,
                "rating": p.rating,
                "rd": p.rd,
                "record": p.record,
            }
            for wrestler_id, p in self.wrestler_objects.items()
            if p.record.wins >= 5
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


if __name__ == "__main__":
    r = Ranker()
    r.main()
