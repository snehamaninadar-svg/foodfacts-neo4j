"""GDS: additive cocktails (G7), recipe twins and substitutes (G8), subgroup similarity (G9).
Calls the GDS procedures through plain Cypher with the neo4j driver."""
import os
import pandas as pd
from dotenv import load_dotenv
from neo4j import GraphDatabase

load_dotenv()
driver = GraphDatabase.driver('bolt://localhost:7687', auth=('neo4j', os.environ['NEO4J_PASSWORD']))
CODE, AVOID = '0038000122903', 'en:milk'   # Pringles tortilla crisps, nacho cheese
pd.set_option('display.width', 250)
pd.set_option('display.max_colwidth', 120)


def run(query, **params):
    with driver.session() as s:
        return s.run(query, **params).data()


def show(title, query, **params):
    print(f'\n=== {title} ===', flush=True)
    rows = run(query, **params)
    print(pd.DataFrame(rows).to_string(index=False) if rows else '(no rows)', flush=True)


def drop(name):
    run('CALL gds.graph.drop($n, false) YIELD graphName RETURN graphName', n=name)


print('GDS version', run('RETURN gds.version() AS v')[0]['v'], flush=True)

# ---------- G7: additive cocktails ----------
drop('additive-net')
run("""CALL gds.graph.project('additive-net', 'Additive',
         {CO_OCCURS: {orientation: 'UNDIRECTED', properties: ['lift', 'count']}})
       YIELD nodeCount, relationshipCount RETURN nodeCount, relationshipCount""")
r = run("""CALL gds.louvain.write('additive-net', {relationshipWeightProperty: 'lift', writeProperty: 'community'})
           YIELD communityCount, modularity RETURN communityCount, modularity""")[0]
print('Louvain:', r['communityCount'], 'communities, modularity', round(r['modularity'], 3), flush=True)
run("""CALL gds.pageRank.write('additive-net', {relationshipWeightProperty: 'count', writeProperty: 'pagerank'})
       YIELD nodePropertiesWritten RETURN nodePropertiesWritten""")
drop('additive-net')

show('G7a Additive communities and how ultra-processed their products are', """
MATCH (a:Additive) WHERE a.community IS NOT NULL
WITH a.community AS community, collect(a) AS members WHERE size(members) >= 3
UNWIND members AS a
MATCH (a)<-[:HAS_ADDITIVE]-(p:Product)
WITH community, members, count(DISTINCT p) AS products,
     count(DISTINCT CASE WHEN p.nova = 4 THEN p END) AS upf
RETURN community, [m IN members | coalesce(m.name, m.id)][..8] AS additives,
       products, round(100.0 * upf / products, 1) AS upf_pct
ORDER BY products DESC""")

show('G7b Hub additives by PageRank', """
MATCH (a:Additive) WHERE a.pagerank IS NOT NULL
RETURN coalesce(a.name, a.id) AS additive, round(a.pagerank, 3) AS pagerank, a.community AS community
ORDER BY a.pagerank DESC LIMIT 10""")

# ---------- G8: recipe similarity ----------
drop('recipes')
run("""CALL gds.graph.project('recipes', ['Product', 'Ingredient'], 'CONTAINS')
       YIELD nodeCount, relationshipCount RETURN nodeCount, relationshipCount""")
CONFIG = """{topK: 10, similarityCutoff: 0.5, degreeCutoff: 3,
             writeRelationshipType: 'SIMILAR', writeProperty: 'score'}"""
est = run(f"CALL gds.nodeSimilarity.write.estimate('recipes', {CONFIG}) YIELD requiredMemory RETURN requiredMemory")
print('Estimated memory:', est[0]['requiredMemory'], flush=True)
r = run(f"""CALL gds.nodeSimilarity.write('recipes', {CONFIG})
            YIELD relationshipsWritten, computeMillis RETURN relationshipsWritten, computeMillis""")[0]
print('SIMILAR edges written:', r['relationshipsWritten'], 'in', r['computeMillis'], 'ms', flush=True)
drop('recipes')

show('G8a White-label twins: different brands, identical ingredient sets', """
MATCH (b1:Brand)<-[:MADE_BY]-(p:Product)-[s:SIMILAR]->(q:Product)-[:MADE_BY]->(b2:Brand)
WHERE s.score = 1.0 AND p.ingredients_n >= 5 AND b1.name < b2.name
RETURN b1.name AS brand_1, b2.name AS brand_2, count(DISTINCT p) AS identical_recipes,
       collect(DISTINCT p.name)[..2] AS examples
ORDER BY identical_recipes DESC LIMIT 15""")

show('G8b Substitutes from precomputed similarity', """
MATCH (p:Product {code: $code})-[s:SIMILAR]->(q:Product)
WHERE q.nutriscore < p.nutriscore
  AND NOT EXISTS { (q)-[:HAS_ALLERGEN]->(:Allergen {id: $avoid}) }
RETURN q.name AS name, q.nutriscore AS nutriscore, q.nova AS nova, round(s.score, 2) AS score
ORDER BY score DESC LIMIT 5""", code=CODE, avoid=AVOID)

# ---------- G9: food subgroups built from similar ingredients ----------
drop('subgroup-ingredient')
run("""
MATCH (s:SubGroup)<-[:IN_GROUP]-(p:Product)
WITH s, count(p) AS total WHERE total >= 200
MATCH (s)<-[:IN_GROUP]-(p:Product)-[:CONTAINS]->(i:Ingredient)
WITH s, total, i, count(p) AS n WHERE n >= 10
WITH s, i, toFloat(n) / total AS share
RETURN gds.graph.project('subgroup-ingredient', s, i,
         {relationshipProperties: {share: share}}).graphName AS g""")
show('G9 Food subgroups with the most similar recipes (weighted Jaccard on ingredient shares)', """
CALL gds.nodeSimilarity.stream('subgroup-ingredient', {relationshipWeightProperty: 'share', topK: 3})
YIELD node1, node2, similarity
WITH gds.util.asNode(node1) AS s1, gds.util.asNode(node2) AS s2, similarity
WHERE s1.name < s2.name
RETURN s1.name AS subgroup_1, s2.name AS subgroup_2, round(similarity, 3) AS similarity
ORDER BY similarity DESC LIMIT 20""")
drop('subgroup-ingredient')
driver.close()
