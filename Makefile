

output/2025_ranking.html: data/joshi_wrestlers.sqlite3
	uv run python ./scripts/do_rank.py

output/joshi_net-sm.json: data/joshi_wrestlers.sqlite3
	uv run python ./scripts/generate_network.py

output/promotions.html:  data/joshi_wrestlers.sqlite3
	uv run python ./scripts/promotion_plot.py

all: output/2025_ranking.html output/joshi_net-sm.json output/promotions.html

.PHONY: lint format check test
lint:
	uv run ruff check .

format:
	uv run ruff format .

check:
	uv run ruff check . --fix

test:
	uv run pytest
