# Joshi Network

Attempts to deduce who-works-with-who based on cagematch data.

* Starts with known freelancers and builds a network based on who they've worked with
* Attempts to deduce who is a "Joshi" based on participation in specific promotions.

## To use:

* run ```scrape.py``` to download cagematch data.
* run ```directory.py``` to process scraped data into a directory ('joshi_dir.json').
* run ```generate_network.py``` to process directory/scraped data into a json file suitable use in network graphs. ('joshi_net.json').