

output/2025_ranking.html: data/joshi_wrestlers.sqlite3
	poetry run python ./do_rank.py

output/joshi_net-sm.json: data/joshi_wrestlers.sqlite3
	poetry run python ./generate_network.py

output/promotions.html:  data/joshi_wrestlers.sqlite3
	poetry run python ./promotion_plot.py

all: output/2025_ranking.html output/joshi_net-sm.json output/promotions.html
