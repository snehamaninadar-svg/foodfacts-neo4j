"""Load the exported CSVs into Neo4j with batched LOAD CSV, timing each step."""
import argparse, os, time
from dotenv import load_dotenv
from neo4j import GraphDatabase

load_dotenv()

PRODUCTS = """
LOAD CSV WITH HEADERS FROM 'file:///products.csv' AS r
WITH r WHERE $shard IS NULL OR r.shard = $shard
CALL (r) {
  MERGE (p:Product {code: r.code})
  SET p.name = r.name, p.nova = toInteger(r.nova), p.nutriscore = r.nutriscore,
      p.ecoscore = CASE WHEN r.ecoscore <> '' THEN r.ecoscore END,
      p.sugars = toFloat(r.sugars), p.fat = toFloat(r.fat), p.satfat = toFloat(r.satfat),
      p.salt = toFloat(r.salt), p.fiber = toFloat(r.fiber), p.proteins = toFloat(r.proteins),
      p.kcal = toFloat(r.kcal), p.additives_n = toInteger(r.additives_n),
      p.ingredients_n = toInteger(r.ingredients_n)
  MERGE (g:SubGroup {name: r.subgroup})
  MERGE (p)-[:IN_GROUP]->(g)
} IN TRANSACTIONS OF 10000 ROWS
"""

GROUPS = """
LOAD CSV WITH HEADERS FROM 'file:///groups.csv' AS r
MERGE (s:SubGroup {name: r.subgroup})
MERGE (g:FoodGroup {name: r.group})
MERGE (s)-[:PART_OF]->(g)
"""

INGREDIENTS = """
LOAD CSV WITH HEADERS FROM 'file:///product_ingredient.csv' AS r
CALL (r) {
  MATCH (p:Product {code: r.code})
  MERGE (i:Ingredient {id: r.ingredient})
  MERGE (p)-[c:CONTAINS]->(i)
  SET c.rank = toInteger(r.rank), c.percent = toFloat(r.percent),
      c.vegan = CASE WHEN r.vegan <> '' THEN r.vegan END
} IN TRANSACTIONS OF 10000 ROWS
"""

# One template for the five simple Product -> tag relationships
REL = """
LOAD CSV WITH HEADERS FROM 'file:///{file}.csv' AS r
CALL (r) {{
  MATCH (p:Product {{code: r.code}})
  MERGE (t:{label} {{{key}: r.{col}}})
  MERGE (p)-[:{rel}]->(t)
}} IN TRANSACTIONS OF 10000 ROWS
"""
RELS = [('product_brand', 'Brand', 'name', 'brand', 'MADE_BY'),
        ('product_additive', 'Additive', 'id', 'additive', 'HAS_ADDITIVE'),
        ('product_allergen', 'Allergen', 'id', 'allergen', 'HAS_ALLERGEN'),
        ('product_label', 'Label', 'id', 'label', 'HAS_LABEL'),
        ('product_country', 'Country', 'id', 'country', 'SOLD_IN')]

ADDITIVE_NAMES = """
LOAD CSV WITH HEADERS FROM 'file:///additives.csv' AS r
MATCH (a:Additive {id: r.id}) SET a.name = r.name, a.role = r.role
"""

STEPS = ([('products', PRODUCTS), ('groups', GROUPS), ('ingredients', INGREDIENTS)]
         + [(f, REL.format(file=f, label=l, key=k, col=c, rel=t)) for f, l, k, c, t in RELS]
         + [('additive names', ADDITIVE_NAMES)])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--uri', default='bolt://localhost:7687')
    ap.add_argument('--db', default='neo4j')
    ap.add_argument('--shard', choices=['0', '1'], help='load one partition only (Step 8)')
    args = ap.parse_args()

    driver = GraphDatabase.driver(args.uri, auth=('neo4j', os.environ['NEO4J_PASSWORD']))
    start = time.time()
    with driver.session(database=args.db) as s:
        for name, query in STEPS:
            t = time.time()
            s.run(query, shard=args.shard).consume()
            print(f'{name:<18} {time.time() - t:7.1f} s', flush=True)
        print(f'total {time.time() - start:.0f} s')
        for r in s.run('MATCH (n) RETURN labels(n)[0] AS label, count(*) AS n ORDER BY n DESC'):
            print(f"{r['label']:<12} {r['n']:>10,}")
        for r in s.run('MATCH ()-[x]->() RETURN type(x) AS type, count(*) AS n ORDER BY n DESC'):
            print(f"{r['type']:<14} {r['n']:>10,}")
    driver.close()


if __name__ == '__main__':
    main()