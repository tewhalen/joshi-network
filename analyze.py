import json
import pathlib
from collections import Counter

import networkx

w_directory = json.load(open("joshi_dir.json"))

g = networkx.node_link_graph(json.load(open("joshi_net.json")))
print(g)
c = networkx.community.louvain_communities(g)
for x in c:
    print(len(x), [w_directory[w]["name"] for w in x])
print(len(c))
