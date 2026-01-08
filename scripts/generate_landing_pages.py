#!/usr/bin/env python
"""Generate landing pages for the output directory structure.

Includes generating index.html for each year, main landing page, and
placeholders for missing data.

Also generates the html pages that wrap the network visualizer.

Uses Jinja2 templates located in the 'templates' directory."""

import datetime
import pathlib
import shutil

import jinja2

from joshirank.joshidb import wrestler_db


class OutputGenerator:
    template_env: jinja2.Environment
    template_loader: jinja2.FileSystemLoader
    output_dir: pathlib.Path

    def __init__(self, years: list[int]):
        self.years = years
        self.template_loader = jinja2.FileSystemLoader(searchpath="templates")
        self.template_env = jinja2.Environment(loader=self.template_loader)
        # Make boundary years available globally to templates without per-render args
        self.template_env.globals.update(
            current_year=datetime.date.today().year,
            min_year=min(years),
        )
        self.output_dir = pathlib.Path("output")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._ensure_base_css()

    def get_template(self, template_name: str) -> jinja2.Template:
        """Get a Jinja2 template by name."""
        return self.template_env.get_template(template_name)

    def _ensure_base_css(self):
        """Copy shared base stylesheet to output/base.css."""
        src = pathlib.Path("templates/base.css")
        dest = self.output_dir / "base.css"
        if src.exists():
            shutil.copyfile(src, dest)

    def generate_placeholder_year_page(self, year: int):
        """Generate a placeholder page for a year with no data."""

        template = self.get_template("placeholder_year.html")

        html = template.render(year=year)

        with open(self.output_dir / f"{year}" / "index.html", "w") as f:
            f.write(html)

        print(f"Generated placeholder output/{year}/index.html")

    def handle_year(self, year: int):
        # make the year index.html page
        self.generate_year_hub(year)

        # if the ranking.html file does not exist, generate placeholder
        has_ranking = (self.output_dir / f"{year}" / "ranking.html").exists()
        if not has_ranking:
            self.generate_ranking_placeholder(year)
        # if the network.html file does not exist, generate placeholder
        has_network = (self.output_dir / f"{year}" / "network.json").exists()
        if not has_network:
            self.generate_network_placeholder(year)
        else:
            self.generate_network_viewer(year)
        has_network_jpn = (self.output_dir / f"{year}" / "network-jpn.json").exists()
        if has_network_jpn:
            self.generate_jpn_network_viewer(year)
        else:
            # remove the jpn network viewer if it exists for some reason
            jpn_viewer = self.output_dir / f"{year}" / "network-jpn.html"
            if jpn_viewer.exists():
                jpn_viewer.unlink()
        # if the promotions.html file does not exist, generate placeholder
        has_promotions = (self.output_dir / f"{year}" / "promotions.html").exists()
        if not has_promotions:
            self.generate_promotions_placeholder(year)

    def generate_year_hub(self, year: int):
        """Generate an index.html for a specific year directory."""

        output_dir = self.output_dir / f"{year}"
        if not output_dir.exists():
            output_dir.mkdir(parents=True, exist_ok=True)

        # Check what files exist
        has_ranking = (output_dir / "ranking.html").exists()
        has_network = (output_dir / "network.json").exists()
        has_network_jpn = (output_dir / "network-jpn.json").exists()
        has_promotions = (output_dir / "promotions.html").exists()

        if not (has_ranking or has_network or has_promotions):
            # Generate placeholder instead
            self.generate_placeholder_year_page(year)
            return
        # Generate year hub page
        hub_template = self.get_template("year_hub.html")
        output_text = hub_template.render(
            year=year,
            has_network_jpn=has_network_jpn,
            has_ranking=has_ranking,
            has_network=has_network,
            has_promotions=has_promotions,
        )

        with open(self.output_dir / f"{year}" / "index.html", "w") as f:
            f.write(output_text)

        print(f"Generated output/{year}/index.html")

    def generate_network_viewer(self, year: int):
        # Generate network viewer page if network.json exists

        network_template = self.get_template("network.html")
        network_html = network_template.render(
            year=year,
            data_file="network.json",
            alt_network_url="network-jpn.html",
            alt_network_label="Japanese Only",
        )

        with open(self.output_dir / f"{year}" / "network.html", "w") as f:
            f.write(network_html)

        print(f"Generated output/{year}/network.html")

    def generate_jpn_network_viewer(self, year: int):
        """Generate Japanese-only network viewer for a year if data exists."""
        # Generate Japanese-only network viewer if network-jpn.json exists
        has_network_jpn = (self.output_dir / f"{year}" / "network-jpn.json").exists()
        if has_network_jpn:
            network_template = self.get_template("network.html")
            network_jpn_html = network_template.render(
                year=year,
                title_suffix="Japanese Wrestlers Network",
                data_file="network-jpn.json",
                alt_network_url="network.html",
                alt_network_label="All Wrestlers",
            )

            with open(self.output_dir / f"{year}" / "network-jpn.html", "w") as f:
                f.write(network_jpn_html)

            print(f"Generated output/{year}/network-jpn.html")

    def generate_ranking_placeholder(self, year: int):
        """Generate a placeholder ranking.html for a year with no ranking data."""
        # Generate placeholder for missing ranking

        ranking_template = self.get_template("placeholder_ranking.html")
        ranking_html = ranking_template.render(year=year)
        with open(self.output_dir / f"{year}" / "ranking.html", "w") as f:
            f.write(ranking_html)
        print(f"Generated placeholder output/{year}/ranking.html")

    def generate_network_placeholder(self, year: int):
        # Generate placeholder for missing network

        network_template = self.get_template("placeholder_network.html")
        network_html = network_template.render(year=year)
        with open(self.output_dir / f"{year}" / "network.html", "w") as f:
            f.write(network_html)
        print(f"Generated placeholder output/{year}/network.html")

    def generate_promotions_placeholder(self, year: int):
        # Generate placeholder for missing promotions

        promotions_template = self.get_template("placeholder_promotions.html")
        promotions_html = promotions_template.render(year=year)
        with open(self.output_dir / f"{year}" / "promotions.html", "w") as f:
            f.write(promotions_html)
        print(f"Generated placeholder output/{year}/promotions.html")

    def generate_main_landing_page(self, years: list[int]):
        """Generate the main landing page (output/index.html)."""
        template = self.get_template("main_index.html")
        # Collect year data with stats (newest first)
        years_data = []
        for year in sorted(years, reverse=True):
            year_dir = self.output_dir / f"{year}"
            if year_dir.exists() and (year_dir / "index.html").exists():
                stats = get_year_stats(year)
                years_data.append(
                    {
                        "year": year,
                        "female_wrestlers": stats["female_wrestlers"],
                        "matches": stats["matches"],
                    }
                )

        html = template.render(years_data=years_data)

        with open(self.output_dir / "index.html", "w") as f:
            f.write(html)

        print("Generated output/index.html")


def get_year_stats(year: int) -> dict:
    """Get statistics for a given year from the database."""
    wrestlers_with_matches = set()
    total_matches = 0

    # Count all wrestlers with matches in this year (regardless of female flag)
    for wrestler_id in wrestler_db.all_wrestler_ids():
        available_years = wrestler_db.match_years_available(wrestler_id)
        if year in available_years:
            info = wrestler_db.get_match_info(wrestler_id, year)
            match_count = info.get("match_count", 0)
            if match_count > 0:
                wrestlers_with_matches.add(wrestler_id)
                total_matches += match_count

    return {
        "female_wrestlers": len(wrestlers_with_matches),
        "matches": total_matches,
    }


def main():
    """Generate all landing pages."""
    # Find all year directories AND get years from database
    output_path = pathlib.Path("output")
    year_dirs = [d for d in output_path.iterdir() if d.is_dir() and d.name.isdigit()]
    output_years = set(int(d.name) for d in year_dirs)

    # Get years from database (all years with match data)
    from scripts.list_available_years import get_available_years

    db_years = set(get_available_years())

    # Combine both sources - we want to generate pages for all years
    all_years = sorted(output_years | db_years)

    print(f"Found years: {all_years}")

    output_generator = OutputGenerator(years=all_years)

    # Generate hub pages for each year with prev/next info
    for i, year in enumerate(all_years):
        output_generator.handle_year(year)

    # Generate main landing page (only include years with actual content)
    years_with_content = [
        year
        for year in all_years
        if (pathlib.Path(f"output/{year}") / "index.html").exists()
    ]
    output_generator.generate_main_landing_page(years_with_content)


if __name__ == "__main__":
    main()
