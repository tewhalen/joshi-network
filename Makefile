# Get available years from database
AVAILABLE_YEARS := $(shell uv run python ./scripts/list_available_years.py)
AVAILABLE_YEAR_TARGETS := $(addprefix output/,$(addsuffix /ranking.html,$(AVAILABLE_YEARS)))

# Year targets - generate all outputs for a specific year
output/%/ranking.html output/%/network.json output/%/promotions.html: data/joshi_wrestlers.sqlite3
	uv run joshi-rank --seed $*
	uv run python ./scripts/generate_network.py $*
	uv run python ./scripts/promotion_plot.py $*

# Don't delete intermediate files
.PRECIOUS: output/%/ranking.html output/%/network.json output/%/promotions.html

# Landing pages - generate hub pages and main index
# Note: generate_landing_pages.py generates ALL index files at once
output/index.html: $(AVAILABLE_YEAR_TARGETS)
	uv run python ./scripts/generate_landing_pages.py

.PHONY: lint format check test all list-years deploy
lint:
	uv run ruff check .

format:
	uv run ruff format .

check:
	uv run ruff check . --fix

test:
	uv run pytest

list-years:
	@echo "Available years: $(AVAILABLE_YEARS)"

deploy: output/index.html
	rsync -avz --delete output/ introvert.net:~/introvert.net/joshinet/
