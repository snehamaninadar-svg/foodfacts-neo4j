"""Interactive HTML of the additive co-occurrence network, coloured by Louvain community."""
import os
from dotenv import load_dotenv
from neo4j import GraphDatabase
from pyvis.network import Network

load_dotenv()
COLORS = ['#4e79a7', '#f28e2b', '#e15759', '#76b7b2', '#59a14f',
          '#edc948', '#b07aa1', '#ff9da7', '#9c755f', '#bab0ac']
QUERY = """
MATCH (a:Additive)-[c:CO_OCCURS]->(b:Additive) WHERE c.lift >= 3 AND c.count >= 100
RETURN a.id AS a, a.community AS a_com, a.pagerank AS a_pr,
       coalesce(a.community_name, 'community ' + toString(a.community)) AS a_cn,
       b.id AS b, b.community AS b_com, b.pagerank AS b_pr,
       coalesce(b.community_name, 'community ' + toString(b.community)) AS b_cn,
       c.count AS together, c.lift AS lift"""

driver = GraphDatabase.driver('bolt://localhost:7687', auth=('neo4j', os.environ['NEO4J_PASSWORD']))
net = Network(height='850px', width='100%', bgcolor='#ffffff', font_color='#222222')
with driver.session() as s:
    for r in s.run(QUERY):
        for k in ('a', 'b'):
            pr, com = r[f'{k}_pr'] or 0, r[f'{k}_com'] or 0
            net.add_node(r[k], label=r[k].replace('en:', '').upper(), size=12 + 5 * pr,
                         color=COLORS[com % len(COLORS)], font={'size': 22},
                         title=f"{r[k]} | {r[f'{k}_cn']} | PageRank {pr:.2f}")
        net.add_edge(r['a'], r['b'], value=r['together'], color='#cccccc',
                     title=f"{r['together']} products, lift {r['lift']}")
driver.close()
net.set_options("""{
  "physics": {"solver": "forceAtlas2Based",
              "forceAtlas2Based": {"gravitationalConstant": -120, "springLength": 150},
              "stabilization": {"iterations": 300}},
  "edges": {"smooth": false, "scaling": {"min": 1, "max": 6}}
}""")
os.makedirs('report', exist_ok=True)
with open('report/additive_network.html', 'w', encoding='utf-8') as f:
    f.write(net.generate_html())
print('Wrote report/additive_network.html')
