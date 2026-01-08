from typing import NamedTuple


class Record(NamedTuple):
    wins: int = 0
    losses: int = 0
    draws: int = 0

    def __str__(self):
        if self.draws:
            return f"{self.wins}-{self.losses}-{self.draws}"
        else:
            return f"{self.wins}-{self.losses}"

    def __add__(self, x) -> Record:
        return Record(
            wins=self.wins + x[0],
            losses=self.losses + x[1],
            draws=self.draws + x[2],
        )

    def total_matches(self) -> int:
        return self.wins + self.losses + self.draws


if __name__ == "__main__":
    assert Record(2, 1, 3) + Record(2, 3, 4) == Record(4, 4, 7)
    assert Record(3, 4, 2).draws == 2
    assert str(Record(3, 2, 3)) == "3-2-3"
    # assert Record(2, 3, 4) + 4
