"""
Copyright (c) 2009 Ryan Kirkman

Permission is hereby granted, free of charge, to any person
obtaining a copy of this software and associated documentation
files (the "Software"), to deal in the Software without
restriction, including without limitation the rights to use,
copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the
Software is furnished to do so, subject to the following
conditions:

The above copyright notice and this permission notice shall be
included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES
OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
OTHER DEALINGS IN THE SOFTWARE.
"""

import math


def glicko_rating_to_glicko2(x):
    return (x - 1500) / 173.7178


def glicko_rd_to_glicko2(x):
    return x / 173.7178


def glicko2_rating_to_glicko(x):
    return (x * 173.7178) + 1500


def glicko2_rd_to_glicko(x):
    return x * 173.7178


class Player:
    # Class attribute
    # The system constant, which constrains
    # the change in volatility over time.
    _tau = 0.5

    def __str__(self):
        return f"{self.rating} ({self.rd})"

    def __repr__(self):
        return f"<{self.rating:0.0f} ({self.rd:0.0f})>"

    @property
    def glicko2rating(self):
        return self.__rating

    def getRating(self):
        return glicko2_rating_to_glicko(self.__rating)

    def setRating(self, rating):
        self.__rating = (rating - 1500) / 173.7178

    rating = property(getRating, setRating)

    def getRd(self):
        return glicko2_rd_to_glicko(self.__rd)

    def setRd(self, rd):
        self.__rd = rd / 173.7178

    rd = property(getRd, setRd)

    def __init__(self, rating=1500, rd=350, vol=0.06):
        # For testing purposes, preload the values
        # assigned to an unrated player.
        self.setRating(rating)
        self.setRd(rd)
        self.vol = vol

    def _preRatingRD(self):
        """Calculates and updates the player's rating deviation for the
        beginning of a rating period.

        preRatingRD() -> None

        """
        # Step 6
        # Update the rating deviation to the new pre-rating period value
        self.__rd = math.sqrt(math.pow(self.__rd, 2) + math.pow(self.vol, 2))

    def update_player(self, rating_list, RD_list, outcome_list):
        """Calculates the new rating and rating deviation of the player.

        update_player(list[int], list[int], list[bool]) -> None

        """
        # Convert the rating and rating deviation values for internal use.
        rating_list = [glicko_rating_to_glicko2(x) for x in rating_list]
        RD_list = [glicko_rd_to_glicko2(x) for x in RD_list]

        E_list = [
            self._E(opp_rating, opp_rd)
            for opp_rating, opp_rd in zip(rating_list, RD_list)
        ]

        v = self._v(rating_list, RD_list, E_list)
        self.vol = self._newVol(rating_list, RD_list, outcome_list, v)

        self._preRatingRD()

        # Step 7. Update the rating and RD to the new values
        self.__rd = 1 / math.sqrt((1 / self.__rd**2) + (1 / v))

        self.__rating += math.pow(self.__rd, 2) * sum(
            self._g(opp_rd) * (outcome - opp_E)
            for opp_rating, opp_rd, opp_E, outcome in zip(
                rating_list, RD_list, E_list, outcome_list
            )
        )

    # step 5
    def _newVol(self, rating_list, RD_list, outcome_list, v):
        """Calculating the new volatility as per the Glicko2 system.

        Updated for Feb 22, 2012 revision. -Leo

        _newVol(list, list, list, float) -> float

        """

        # Step 5. Determine the new value of the volatility.

        delta = self._delta(rating_list, RD_list, outcome_list, v)

        # 1.
        a = math.log(self.vol**2)
        eps = 0.000001

        def _f(x):
            ex = math.exp(x)
            num1 = ex * (delta**2 - self.__rd**2 - v - ex)
            denom1 = 2 * ((self.__rd**2 + v + ex) ** 2)
            return (num1 / denom1) - ((x - a) / (self._tau**2))

        # step 2
        A = a

        B = None
        tau = self._tau
        if (delta**2) > ((self.__rd**2) + v):
            B = math.log(delta**2 - self.__rd**2 - v)
        else:
            k = 1
            while _f(a - k * tau) < 0:
                k = k + 1
            B = a - k * tau

        # step 3
        fA = _f(A)
        fB = _f(B)

        # step 4
        while math.fabs(B - A) > eps:
            # a
            C = A + ((A - B) * fA) / (fB - fA)
            fC = _f(C)
            # b
            if fC * fB < 0:
                A = B
                fA = fB
            else:
                fA = fA / 2.0
            # c
            B = C
            fB = fC

        # step 5
        return math.exp(A / 2)

    def _delta(self, rating_list, RD_list, outcome_list, v):
        """The delta function of the Glicko2 system.

        _delta(list, list, list) -> float

        """

        # Step 4. Compute the quantity delta, the estimated improvement
        # in rating by comparing the pre-period rating to the performance
        # rating based only on game outcomes.

        return v * sum(
            self._g(opp_rd) * (outcome - self._E(opp_rating, opp_rd))
            for opp_rating, opp_rd, outcome in zip(rating_list, RD_list, outcome_list)
        )

    def _v(self, rating_list, RD_list, E_list):
        """The v function of the Glicko2 system.

        _v(list[int], list[int]) -> float

        """
        # Step 3. Compute the quantity v. This is the estimated variance
        # of the team's/player's rating based only on game outcomes.
        try:
            return 1 / sum(
                math.pow(self._g(opp_rd), 2) * opp_E * (1 - opp_E)
                for opp_rating, opp_rd, opp_E in zip(rating_list, RD_list, E_list)
            )
        except ZeroDivisionError:
            return 1

    def did_not_compete(self):
        """Applies Step 6 of the algorithm. Use this for
        players who did not compete in the rating period.

        did_not_compete() -> None

        """
        self._preRatingRD()

    def _g(self, RD):
        """The Glicko2 g(RD) function.

        _g() -> float

        """
        return 1 / math.sqrt(1 + 3 * math.pow(RD, 2) / math.pow(math.pi, 2))

    def _E(self, p2rating, p2RD):
        """The Glicko E function.

        _E(int) -> float

        """
        return 1 / (1 + math.exp(-1 * self._g(p2RD) * (self.__rating - p2rating)))


import unittest


class TestP(unittest.TestCase):
    def setUp(self):
        self.player = Player(rating=1500, rd=200, vol=0.06)

    def test_player(self):
        self.assertAlmostEqual(self.player.rating, 1500)

    def test_rating_conv(self):
        self.assertAlmostEqual(glicko_rating_to_glicko2(1400), -0.5756, 4)
        self.assertAlmostEqual(glicko_rating_to_glicko2(1550), 0.2878, 4)
        self.assertAlmostEqual(glicko_rating_to_glicko2(1700), 1.1513, 4)

    def test_e(self):
        opp_ratings = [1400, 1550, 1700]
        opp_rds = [30, 100, 300]
        outcomes = [1, 0, 0]
        rating_list = [glicko_rating_to_glicko2(x) for x in opp_ratings]
        RD_list = [glicko_rd_to_glicko2(x) for x in opp_rds]
        E_list = [
            self.player._E(opp_rating, opp_rd)
            for opp_rating, opp_rd in zip(rating_list, RD_list)
        ]
        self.assertAlmostEqual(E_list[0], 0.639, 3)
        self.assertAlmostEqual(E_list[1], 0.432, 3)
        self.assertAlmostEqual(E_list[2], 0.303, 3)

    def test_v_rating(self):
        p = self.player
        opp_ratings = [1400, 1550, 1700]
        opp_rds = [30, 100, 300]
        outcomes = [1, 0, 0]
        rating_list = [glicko_rating_to_glicko2(x) for x in opp_ratings]
        RD_list = [glicko_rd_to_glicko2(x) for x in opp_rds]
        E_list = [
            p._E(opp_rating, opp_rd) for opp_rating, opp_rd in zip(rating_list, RD_list)
        ]

        self.assertAlmostEqual(p._v(rating_list, RD_list, E_list), 1.7785, places=3)

    def test_delta(self):
        p = self.player
        opp_ratings = [1400, 1550, 1700]
        opp_rds = [30, 100, 300]
        outcomes = [1, 0, 0]
        rating_list = [glicko_rating_to_glicko2(x) for x in opp_ratings]
        RD_list = [glicko_rd_to_glicko2(x) for x in opp_rds]

        self.assertAlmostEqual(
            p._delta(rating_list, RD_list, outcomes, 1), -0.2717, places=3
        )

    def test_update(self):
        p = self.player
        opp_ratings = [1400, 1550, 1700]
        opp_rds = [30, 100, 300]
        outcomes = [1, 0, 0]
        p.update_player(opp_ratings, opp_rds, outcomes)
        self.assertAlmostEqual(p.vol, 0.05999, 4)
        self.assertAlmostEqual(p.rd, 151.52, 2)
        self.assertAlmostEqual(p.glicko2rating, -0.2069, 3)
        self.assertAlmostEqual(p.rating, 1464.06, 1)


if __name__ == "__main__":
    unittest.main()
