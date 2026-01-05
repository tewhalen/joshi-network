import statistics
from collections import Counter, defaultdict

import jinja2
import matplotlib as mpl
import matplotlib.patches as patches
import numpy as np
from matplotlib import pyplot as plt
from sparklines import sparklines
from tabulate import tabulate

from joshirank.joshidb import get_name, get_promotion_with_location, wrestler_db

min_val = 0
max_val = 120


def match_count_report(year: int = 2025):
    accumulator = []
    promotions = defaultdict(list)
    for wid in wrestler_db.all_female_wrestlers():
        name = get_name(int(wid))
        matches = wrestler_db.get_matches(int(wid), year=year)
        match_count = len(matches)
        if not match_count:
            continue  # don't count zeros
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
                    "25%": quartiles[0],
                    "median": quartiles[1],
                    "75%": quartiles[2],
                    "max": max_matches,
                    "histogram": sparkline,
                    "hist_data": series.tolist(),
                }
            )

    accumulator.sort(key=lambda x: x["median"], reverse=True)
    return accumulator


def html_table_results(results):
    # copy the results but remove hist_data

    results = [x.copy() for x in results]
    for i, r in enumerate(results):
        del r["hist_data"]
        r["histogram"] = "<img src='h/{}_histogram_match_counts.png'/>".format(i)
    return tabulate(results, headers="keys", tablefmt="unsafehtml")


def save_results(results, year: int = 2025):
    # load the ranking template and render out the results to a file
    template_loader = jinja2.FileSystemLoader(searchpath="templates")
    template_env = jinja2.Environment(loader=template_loader)
    template = template_env.get_template("promotions.html")
    rendered_table = html_table_results(results)
    rendered_table = rendered_table.replace(
        "<table>", '<table id="ranking-table" class="display">'
    )

    output_text = template.render(
        the_table=rendered_table, year=year, sort_column=4, sort_order="desc"
    )
    with open(f"output/promotions.html", "w") as f:
        f.write(output_text)


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
        # draw thin red lines at the 25th, 50th and 75th percentiles
        if d.get("hist_data"):
            p25, p50, p75 = np.percentile(d["hist_data"], [25, 50, 75])
            for p in (p25, p50, p75):
                ax.axvline(p, color="red", linewidth=0.8, alpha=0.9, zorder=3)
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


def main():
    """Generate promotion statistics and plots."""
    results = match_count_report()

    save_results(results)
    plot_results(results)


if __name__ == "__main__":
    main()
