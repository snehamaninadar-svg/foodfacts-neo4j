// G1a Additive popularity, needed for lift
MATCH (a:Additive)<-[:HAS_ADDITIVE]-(p:Product)
WITH a, count(p) AS n
SET a.products = n;

// G1b Materialize co-occurrence for pairs sharing at least 50 products
MATCH (a1:Additive)<-[:HAS_ADDITIVE]-(p:Product)-[:HAS_ADDITIVE]->(a2:Additive)
WHERE a1.id < a2.id
  AND NOT a2.id STARTS WITH a1.id   // skip parent/child codes such as e322 and e322i
WITH a1, a2, count(p) AS together
WHERE together >= 50
MERGE (a1)-[c:CO_OCCURS]->(a2)
SET c.count = together;

// G1c Lift = observed pair count / count expected if independent
MATCH (p:Product) WITH count(p) AS total
MATCH (a1:Additive)-[c:CO_OCCURS]->(a2:Additive)
SET c.lift = round(toFloat(c.count) * total / (a1.products * a2.products), 2);

// G1d Strongest additive pairs
MATCH (a1:Additive)-[c:CO_OCCURS]->(a2:Additive)
RETURN coalesce(a1.name, a1.id) AS additive_1, coalesce(a2.name, a2.id) AS additive_2,
       c.count AS products, c.lift AS lift
ORDER BY lift DESC LIMIT 15;

// G2 Ultra-processing marker ingredients
MATCH (i:Ingredient)<-[c:CONTAINS]-(p:Product)
WITH i, count(p) AS products, count(CASE WHEN p.nova = 4 THEN 1 END) AS upf
WHERE products >= 300
RETURN i.id AS ingredient, products, round(100.0 * upf / products, 1) AS upf_pct
ORDER BY upf_pct DESC LIMIT 20;

// G3a Vegan-labelled products with ingredients flagged non-vegan
MATCH (p:Product)-[:HAS_LABEL]->(:Label {id: 'en:vegan'})
MATCH (p)-[c:CONTAINS]->(i:Ingredient) WHERE c.vegan = 'no'
RETURN i.id AS ingredient, count(DISTINCT p) AS vegan_labelled_products,
       collect(DISTINCT p.name)[..3] AS examples
ORDER BY vegan_labelled_products DESC LIMIT 15;

// G3b No-gluten products that declare gluten (US data uses en:no-gluten)
MATCH (p:Product)-[:HAS_LABEL]->(:Label {id: 'en:no-gluten'})
WITH count(p) AS labelled,
     sum(CASE WHEN EXISTS { (p)-[:HAS_ALLERGEN]->(:Allergen {id: 'en:gluten'}) } THEN 1 ELSE 0 END) AS conflict
RETURN labelled, conflict, round(100.0 * conflict / labelled, 2) AS conflict_pct;

// G4 Additive reach across food groups
MATCH (a:Additive)<-[:HAS_ADDITIVE]-(p:Product)-[:IN_GROUP]->(:SubGroup)-[:PART_OF]->(g:FoodGroup)
WITH a, count(DISTINCT p) AS products, collect(DISTINCT g.name) AS groups
WHERE products >= 100
RETURN coalesce(a.name, a.id) AS additive, size(groups) AS food_groups, products, groups
ORDER BY food_groups DESC, products DESC LIMIT 15;

// G5 Allergen x food group matrix
MATCH (g:FoodGroup)<-[:PART_OF]-(:SubGroup)<-[:IN_GROUP]-(p:Product)
WITH g, count(p) AS total
MATCH (g)<-[:PART_OF]-(:SubGroup)<-[:IN_GROUP]-(p:Product)-[:HAS_ALLERGEN]->(a:Allergen)
WHERE a.id IN ['en:milk', 'en:gluten', 'en:eggs', 'en:nuts', 'en:soybeans', 'en:peanuts']
WITH g, total, a, count(p) AS n
RETURN g.name AS food_group, a.id AS allergen, round(100.0 * n / total, 1) AS pct
ORDER BY food_group, pct DESC;

// G5b Cross-check with MongoDB Q1: products per subgroup
MATCH (p:Product)-[:IN_GROUP]->(s:SubGroup)
WITH s, count(p) AS products, count(CASE WHEN p.nova = 4 THEN 1 END) AS upf
RETURN s.name AS subgroup, products, round(100.0 * upf / products, 1) AS upf_pct
ORDER BY upf_pct DESC;

// G6 Healthier substitute by shared ingredients (replace the barcode and allergen with your US example)
WITH '0038000122903' AS code, 'en:milk' AS avoid
MATCH (p:Product {code: code})-[:IN_GROUP]->(sg:SubGroup)
MATCH (p)-[:CONTAINS]->(i:Ingredient)<-[:CONTAINS]-(q:Product)-[:IN_GROUP]->(sg)
WHERE q.nutriscore < p.nutriscore
  AND (avoid IS NULL OR NOT EXISTS { (q)-[:HAS_ALLERGEN]->(:Allergen {id: avoid}) })
WITH p, q, count(DISTINCT i) AS shared
WITH p, q, shared, COUNT { (p)-[:CONTAINS]->() } AS mine, COUNT { (q)-[:CONTAINS]->() } AS theirs
RETURN q.code AS code, q.name AS name, q.nutriscore AS nutriscore, q.nova AS nova, shared,
       round(toFloat(shared) / (mine + theirs - shared), 2) AS jaccard
ORDER BY jaccard DESC, nutriscore LIMIT 5;
