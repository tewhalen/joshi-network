# Year targets - generate all outputs for a specific year
output/%/ranking.html output/%/network.json output/%/promotions.html: data/joshi_wrestlers.sqlite3
	uv run python ./scripts/do_rank.py $*
	uv run python ./scripts/generate_network.py $*
	uv run python ./scripts/promotion_plot.py $*

# Don't delete intermediate files
.PRECIOUS: output/%/ranking.html output/%/network.json output/%/promotions.html

# Landing pages - generate hub pages and main index
output/index.html: output/2025/index.html output/2024/index.html output/2023/index.html
	uv run python ./scripts/generate_landing_pages.py

output/%/index.html: output/%/ranking.html output/%/network.json output/%/promotions.html
	uv run python ./scripts/generate_landing_pages.py

# Specific year targets (for backwards compatibility)
output/2025/ranking.html output/2025/network.json output/2025/promotions.html: data/joshi_wrestlers.sqlite3
	uv run python ./scripts/do_rank.py 2025
	uv run python ./scripts/generate_network.py 2025
	uv run python ./scripts/promotion_plot.py 2025

output/2024/ranking.html output/2024/network.json output/2024/promotions.html: data/joshi_wrestlers.sqlite3
	uv run python ./scripts/do_rank.py 2024
	uv run python ./scripts/generate_network.py 2024
	uv run python ./scripts/promotion_plot.py 2024

output/2023/ranking.html output/2023/network.json output/2023/promotions.html: data/joshi_wrestlers.sqlite3
	uv run python ./scripts/do_rank.py 2023
	uv run python ./scripts/generate_network.py 2023
	uv run python ./scripts/promotion_plot.py 2023


# Generate all years
all: output/2025/ranking.html output/2024/ranking.html output/2023/ranking.html output/index.html

.PHONY: lint format check test all
lint:
	uv run ruff check .

format:
	uv run ruff format .

check:
	uv run ruff check . --fix

test:
	uv run pytest
