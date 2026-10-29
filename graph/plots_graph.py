"""Report figures: allergen heatmap (G5) and ultra-processing marker ingredients (G2)."""
import os
import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns
from dotenv import load_dotenv
from neo4j import GraphDatabase

load_dotenv()
G5 = """
MATCH (g:FoodGroup)<-[:PART_OF]-(:SubGroup)<-[:IN_GROUP]-(p:Product)
WITH g, count(p) AS total
MATCH (g)<-[:PART_OF]-(:SubGroup)<-[:IN_GROUP]-(p:Product)-[:HAS_ALLERGEN]->(a:Allergen)
WHERE a.id IN ['en:milk', 'en:gluten', 'en:eggs', 'en:nuts', 'en:soybeans', 'en:peanuts']
WITH g, total, a, count(p) AS n
RETURN g.name AS food_group, a.id AS allergen, round(100.0 * n / total, 1) AS pct"""
G2 = """
MATCH (i:Ingredient)<-[:CONTAINS]-(p:Product)
WITH i, count(p) AS products, count(CASE WHEN p.nova = 4 THEN 1 END) AS upf
WHERE products >= 300 AND upf = products
RETURN i.id AS ingredient, products ORDER BY products DESC LIMIT 15"""

driver = GraphDatabase.driver('bolt://localhost:7687', auth=('neo4j', os.environ['NEO4J_PASSWORD']))
with driver.session() as s:
    allergens = pd.DataFrame(s.run(G5).data())
    markers = pd.DataFrame(s.run(G2).data())
driver.close()
os.makedirs('report', exist_ok=True)

matrix = allergens.pivot(index='food_group', columns='allergen', values='pct').fillna(0)
matrix.columns = [c.replace('en:', '') for c in matrix.columns]
plt.figure(figsize=(8, 5))
sns.heatmap(matrix, annot=True, fmt='.0f', cmap='Blues', cbar_kws={'label': '% of products'})
plt.title('Share of products declaring each allergen, by food group')
plt.xlabel(''); plt.ylabel('')
plt.tight_layout(); plt.savefig('report/fig_allergen_heatmap.png', dpi=150); plt.close()

markers['ingredient'] = markers['ingredient'].str.replace('en:', '')
ax = markers.iloc[::-1].plot.barh(x='ingredient', y='products', legend=False, figsize=(8, 6))
ax.set_title('Most common markers of ultra-processing (100% of their products are NOVA 4)')
ax.set_xlabel('Number of products containing the ingredient'); ax.set_ylabel('')
plt.tight_layout(); plt.savefig('report/fig_upf_markers.png', dpi=150)
print('Saved report/fig_allergen_heatmap.png and report/fig_upf_markers.png')
