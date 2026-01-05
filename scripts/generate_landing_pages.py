#!/usr/bin/env python
"""Generate landing pages for the output directory structure."""

import pathlib

import jinja2


def generate_year_hub(year: int):
    """Generate an index.html for a specific year directory."""
    template_loader = jinja2.FileSystemLoader(searchpath="templates")
    template_env = jinja2.Environment(loader=template_loader)

    output_dir = pathlib.Path(f"output/{year}")
    if not output_dir.exists():
        print(f"Skipping {year} - directory doesn't exist")
        return

    # Check what files exist
    has_ranking = (output_dir / "ranking.html").exists()
    has_network = (output_dir / "network.json").exists()
    has_promotions = (output_dir / "promotions.html").exists()

    if not (has_ranking or has_network or has_promotions):
        print(f"Skipping {year} - no content files found")
        return

    # Generate year hub page
    hub_template = template_env.get_template("year_hub.html")
    output_text = hub_template.render(year=year)

    with open(output_dir / "index.html", "w") as f:
        f.write(output_text)

    print(f"Generated output/{year}/index.html")

    # Generate network viewer page if network.json exists
    if has_network:
        network_template = template_env.get_template("network.html")
        network_html = network_template.render(
            year=year,
            data_file="network.json",
            alt_network_url="network-jpn.html",
            alt_network_label="Japanese Only",
        )

        with open(output_dir / "network.html", "w") as f:
            f.write(network_html)

        print(f"Generated output/{year}/network.html")

    # Generate Japanese-only network viewer if network-jpn.json exists
    has_network_jpn = (output_dir / "network-jpn.json").exists()
    if has_network_jpn:
        network_template = template_env.get_template("network.html")
        network_jpn_html = network_template.render(
            year=year,
            title_suffix="Japanese Wrestlers Network",
            data_file="network-jpn.json",
            alt_network_url="network.html",
            alt_network_label="All Wrestlers",
        )

        with open(output_dir / "network-jpn.html", "w") as f:
            f.write(network_jpn_html)

        print(f"Generated output/{year}/network-jpn.html")


def generate_main_landing_page(years: list[int]):
    """Generate the main landing page (output/index.html)."""
    # Create a simple landing page with links to each year
    html = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Joshi Network</title>
    <style>
        :root {
            --bg: #1a1a1a;
            --fg: #e0e0e0;
            --accent: #ff69b4;
            --card-bg: #2a2a2a;
            --border: #444;
        }
        
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            background: var(--bg);
            color: var(--fg);
            line-height: 1.6;
            padding: 2rem;
        }
        
        .container {
            max-width: 1200px;
            margin: 0 auto;
        }
        
        header {
            text-align: center;
            margin-bottom: 3rem;
        }
        
        h1 {
            font-size: 4rem;
            color: var(--accent);
            margin-bottom: 0.5rem;
        }
        
        .subtitle {
            font-size: 1.4rem;
            color: #999;
        }
        
        .description {
            text-align: center;
            max-width: 600px;
            margin: 0 auto 3rem;
            color: #aaa;
        }
        
        .years-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
            gap: 1.5rem;
            margin-top: 2rem;
        }
        
        .year-card {
            background: var(--card-bg);
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 2rem 1rem;
            text-align: center;
            transition: transform 0.2s, border-color 0.2s;
        }
        
        .year-card:hover {
            transform: translateY(-4px);
            border-color: var(--accent);
        }
        
        .year-card a {
            color: var(--accent);
            text-decoration: none;
            font-size: 2rem;
            font-weight: 700;
        }
        
        footer {
            text-align: center;
            margin-top: 4rem;
            color: #666;
            font-size: 0.9rem;
        }
        
        footer a {
            color: var(--accent);
            text-decoration: none;
        }
        
        footer a:hover {
            text-decoration: underline;
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>Joshi Network</h1>
            <div class="subtitle">Women's Wrestling Data & Analysis</div>
        </header>
        
        <div class="description">
            <p>Exploring the collaborative network and competitive rankings of Japanese women's professional wrestling (Joshi Puroresu), powered by data from CageMatch.net.</p>
        </div>
        
        <div class="years-grid">
"""

    # Add year cards (newest first)
    for year in sorted(years, reverse=True):
        year_dir = pathlib.Path(f"output/{year}")
        if year_dir.exists() and (year_dir / "index.html").exists():
            html += f"""            <div class="year-card">
                <a href="{year}/index.html">{year}</a>
            </div>
"""

    html += """        </div>
        
        <footer>
            <p>Data sourced from <a href="https://www.cagematch.net/" target="_blank">CageMatch.net</a></p>
            <p style="margin-top: 0.5rem;">Generated with Python, visualized with D3.js</p>
        </footer>
    </div>
</body>
</html>
"""

    with open("output/index.html", "w") as f:
        f.write(html)

    print("Generated output/index.html")


def main():
    """Generate all landing pages."""
    # Find all year directories
    output_path = pathlib.Path("output")
    year_dirs = [d for d in output_path.iterdir() if d.is_dir() and d.name.isdigit()]
    years = sorted([int(d.name) for d in year_dirs])

    print(f"Found year directories: {years}")

    # Generate hub pages for each year
    for year in years:
        generate_year_hub(year)

    # Generate main landing page
    generate_main_landing_page(years)


if __name__ == "__main__":
    main()
