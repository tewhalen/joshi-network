import statistics
from collections import Counter, defaultdict

import numpy as np
from sparklines import sparklines
from tabulate import tabulate

import matplotlib as mpl
import matplotlib.patches as patches
from matplotlib import pyplot as plt

from joshirank.joshidb import get_name, get_promotion_with_location, wrestler_db

min_val = 0
max_val = 120


def match_count_report():
    accumulator = []
    promotions = defaultdict(list)
    for wid, wrestler_info in wrestler_db.all_female_wrestlers():
        name = get_name(int(wid))
        matches = wrestler_info.get("matches", [])
        match_count = len(matches)
        promotion = get_promotion_with_location(int(wid))
        promotions[promotion].append((name, match_count))
        # accumulator.append((name, promotion, match_count))

    for promo, wrestlers in promotions.items():
        total_matches = sum(count for _, count in wrestlers)
        total_wrestlers = len(wrestlers)
        # median_match_count = statistics.median(count for _, count in wrestlers)
        series = np.array([count for _, count in wrestlers])
        hist = np.histogram(series, bins=20, range=(min_val, max_val))
        sparkline = sparklines(hist[0])[0]
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
                    "q1": quartiles[0],
                    "median": quartiles[1],
                    "q3": quartiles[2],
                    "max": max_matches,
                    "histogram": sparkline,
                    "hist_data": series.tolist(),
                }
            )

    accumulator.sort(key=lambda x: x["median"], reverse=True)
    return accumulator


def print_results(results):
    # copy the results but remove hist_data

    results = [x.copy() for x in results]
    for i, r in enumerate(results):
        del r["hist_data"]
        r["histogram"] = "<img src='h/{}_histogram_match_counts.png'/>".format(i)
    print(tabulate(results, headers="keys", tablefmt="unsafehtml"))


def plot_results(results):

    for row, d in enumerate(results):
        fig = plt.figure(figsize=(6, 0.5))
        # Option A: black background (make bars light so they show up)
        # ax = plt.gca()
        # fig.patch.set_facecolor("black")
        # ax.set_facecolor("black")
        # plt.hist(
        #    d["hist_data"],
        #    bins=20,
        #    range=(min_val, max_val),
        #    color="white",
        #    alpha=0.9,
        #    edgecolor="gray",
        # )

        # Option B: transparent background
        # (Uncomment this block and comment out Option A to use transparency.
        # For a fully transparent PNG, also pass transparent=True to plt.savefig.)
        ax = plt.gca()
        fig.patch.set_alpha(0.0)
        ax.patch.set_alpha(0.0)
        plt.hist(
            d["hist_data"],
            bins=20,
            range=(min_val, max_val),
            color="blue",
            alpha=0.7,
            edgecolor="black",
        )
        # fig.tight_layout()
        # remove axes and labels
        plt.gca().axes.get_yaxis().set_visible(False)
        plt.gca().spines["top"].set_visible(False)
        plt.gca().spines["right"].set_visible(False)
        plt.gca().spines["left"].set_visible(False)
        plt.gca().spines["bottom"].set_visible(False)
        plt.gca().set_xticks([])
        plt.gca().set_yticks([])
        plt.savefig(
            f"output/h/{row}_histogram_match_counts.png",
            bbox_inches="tight",
            transparent=True,
        )
        plt.close()


if __name__ == "__main__":
    results = match_count_report()
    print_results(results)
    plot_results(results)
