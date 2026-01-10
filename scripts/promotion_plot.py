import datetime
import pathlib
import statistics
from collections import defaultdict

import click
import jinja2
import matplotlib
import numpy as np

# Use Agg backend for faster non-interactive plotting
matplotlib.use("Agg")
from matplotlib import pyplot as plt
from tabulate import tabulate

from joshirank.analysis.promotion import (
    get_short_primary_promotion_for_year,
)
from joshirank.joshidb import wrestler_db

min_val = 0
max_val = 120


class PromotionStats:
    def __init__(self, year: int):
        self.year = year
        self.promotions = defaultdict(list)
        self.output_dir = pathlib.Path(f"output/{year}")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.histogram_dir = self.output_dir / "h"
        self.histogram_dir.mkdir(parents=True, exist_ok=True)

    def match_count_report(self):
        accumulator = []
        promotions = defaultdict(list)
        for wid in wrestler_db.all_female_wrestlers_with_matches_in_year(
            year=self.year
        ):
            match_info = wrestler_db.get_match_info(wid, year=self.year)
            match_count = match_info.get("match_count", 0)

            promotion = get_short_primary_promotion_for_year(wid, year=self.year)

            promotions[promotion].append((wid, match_count))
            # accumulator.append((name, promotion, match_count))

        for promo, wrestlers in promotions.items():
            total_matches = sum(count for _, count in wrestlers)
            total_wrestlers = len(wrestlers)
            # median_match_count = statistics.median(count for _, count in wrestlers)
            series = np.array([count for _, count in wrestlers])
            # hist = np.histogram(series, bins=20, range=(min_val, max_val))
            # sparkline = sparklines(hist[0])[0]
            if total_wrestlers > 2:
                quartiles = statistics.quantiles([count for _, count in wrestlers], n=4)
            else:
                quartiles = (
                    "-",
                    statistics.median([count for _, count in wrestlers]),
                    "-",
                )
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
                        #  "histogram": sparkline,
                        "hist_data": series.tolist(),
                    }
                )
        if not accumulator:
            return []
        accumulator.sort(key=lambda x: x["median"], reverse=True)
        return accumulator

    def plot_results(self, results):
        # Create  histogram subdirectory

        fig, ax = self.setup_resuable_figure()

        for row, d in enumerate(results):
            # Faster than ax.clear() - manually remove previous plot elements
            for artist in ax.patches + ax.lines:
                artist.remove()

            self.draw_histogram(ax, d)
            self.save_histogram(fig, row)

        # Close figure once at the end
        plt.close(fig)

    def setup_resuable_figure(self):
        # Create a single reusable figure to avoid repeated figure creation overhead
        fig, ax = plt.subplots(figsize=(6, 0.5))
        fig.patch.set_alpha(0.0)
        ax.patch.set_alpha(0.0)

        # Pre-configure axes appearance (do once instead of per-plot)
        ax.yaxis.set_visible(False)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.spines["left"].set_visible(False)
        ax.spines["bottom"].set_visible(False)
        ax.set_xticks([])
        ax.set_yticks([])
        return fig, ax

    def draw_histogram(
        self,
        ax,
        d,
    ):
        # Draw percentile lines
        if d.get("hist_data"):
            p25, p50, p75 = np.percentile(d["hist_data"], [25, 50, 75])
            for p, color in ((p25, "red"), (p50, "yellow"), (p75, "red")):
                ax.axvline(p, color=color, linewidth=0.8, alpha=0.9, zorder=3)

        # Draw histogram
        ax.hist(
            d["hist_data"],
            bins=20,
            range=(min_val, max_val),
            color="blue",
            alpha=0.7,
            edgecolor="black",
            histtype="stepfilled",
        )

    def save_histogram(self, fig, row):
        # Save with minimal overhead
        fig.savefig(
            self.histogram_dir / f"histogram_{row}.svg",
            bbox_inches="tight",
            transparent=True,
            # dpi=100,  # Explicit DPI can be faster than auto
        )

    def html_table_results(self, results):
        # copy the results but remove hist_data

        results = [x.copy() for x in results]
        for i, r in enumerate(results):
            del r["hist_data"]
            r["histogram"] = f"<img src='h/histogram_{i}.svg'/>"
        return tabulate(results, headers="keys", tablefmt="unsafehtml")

    def save_results(self, results):
        # load the ranking template and render out the results to a file
        template_loader = jinja2.FileSystemLoader(searchpath="templates")
        template_env = jinja2.Environment(loader=template_loader)
        template_env.globals.update(
            current_year=datetime.date.today().year,
            min_year=1940,
        )
        template = template_env.get_template("promotions.html")
        rendered_table = self.html_table_results(results)
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

        output_text = template.render(
            the_table=rendered_table,
            year=self.year,
            sort_column=4,
            sort_order="desc",
            prev_year=prev_year,
            next_year=next_year,
        )

        with open(self.output_dir / "promotions.html", "w") as f:
            f.write(output_text)


@click.command()
@click.argument("year", type=int, default=2025)
def main(year: int):
    """Generate promotion statistics and plots."""
    stats = PromotionStats(year=year)

    results = stats.match_count_report()
    if not results:
        print(f"No promotion comparison data for year {year}.")
        # delete the output/promotions.html file if it exists for some reason
        output_file = pathlib.Path(f"output/{year}/promotions.html")
        if output_file.exists():
            output_file.unlink()
        # we leave the histograms for someone else to worry about.
        return
    stats.save_results(results)
    stats.plot_results(results)


if __name__ == "__main__":
    main()
