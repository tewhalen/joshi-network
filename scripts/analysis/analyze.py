import random
import statistics
from collections import Counter, defaultdict

import jinja2
import numpy as np
from matplotlib import pyplot as plt
from sparklines import sparklines
from tabulate import tabulate

from joshirank.analysis.promotion import get_primary_promotion_for_year
from joshirank.joshidb import get_name, wrestler_db


def match_count_report(year: int = 2025):
    accumulator = []
    promotions = defaultdict(list)
    for wid, wrestler_info in wrestler_db.all_female_wrestlers():
        name = get_name(wid)
        matches = wrestler_db.get_matches(wid, year=year)
        match_count = len(matches)
        promotion = get_primary_promotion_for_year(wid, year)
        promotions[promotion].append((name, match_count))
        # accumulator.append((name, promotion, match_count))

    for promo, wrestlers in promotions.items():
        total_matches = sum(count for _, count in wrestlers)
        total_wrestlers = len(wrestlers)
        # median_match_count = statistics.median(count for _, count in wrestlers)
        series = np.array([count for _, count in wrestlers])

        if total_wrestlers > 2:
            quartiles = statistics.quantiles([count for _, count in wrestlers], n=4)
        else:
            quartiles = "-", statistics.median([count for _, count in wrestlers]), "-"
        max_matches = max(count for _, count in wrestlers)

        if total_wrestlers >= 5:
            accumulator.append(
                {
                    "promotion": promo,
                    "women": total_wrestlers,
                    "matches": total_matches,
                    "25%": quartiles[0],
                    "median": quartiles[1],
                    "75%": quartiles[2],
                    "max": max_matches,
                    "hist_data": series.tolist(),
                }
            )

    accumulator.sort(key=lambda x: x["median"], reverse=True)
    return accumulator


def simulate_tag_match(match_data: list[int]):
    result = list(match_data)
    # pick the indexes of 4 random wrestlers from the match data
    indexes = random.sample(range(len(match_data)), 4)
    # add 1 to the value at each index
    for i in indexes:
        result[i] += 1
    return result


def summary_stats(match_data: list[int]):
    return statistics.quantiles(match_data, n=4)


def simulate_until_median(match_data, target_median):
    """Returns the new match data and number of added 4-person tag matches to reach target median"""
    current_data = list(match_data)
    added_matches = 0
    while True:
        current_median = statistics.median(current_data)
        if current_median >= target_median:
            break
        current_data = simulate_tag_match(current_data)
        added_matches += 1
    return current_data, added_matches


def monte_carlo_simulation(match_data, target_median, simulations=1000):
    iteration_counts = []
    for _ in range(simulations):
        _, iterations = simulate_until_median(match_data, target_median)
        iteration_counts.append(iterations)
    average_iterations = statistics.mean(iteration_counts)
    return average_iterations, iteration_counts


if __name__ == "__main__":
    report = match_count_report()
    aew = next(x for x in report if x["promotion"] == "AEW")
    aew_matches = tuple(sorted(aew["hist_data"]))

    print(aew)
    simulated_results = aew_matches
    target_median = 65
    average_iterations, iteration_counts = monte_carlo_simulation(
        simulated_results, target_median, simulations=1000
    )
    print(f"Average iterations to reach median {target_median}: {average_iterations}")
