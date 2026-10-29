"""Graph microservice: Neo4j analytics over HTTP, cached in Redis."""
import json, os, time
import redis
from fastapi import FastAPI
from neo4j import GraphDatabase

graph = GraphDatabase.driver(os.getenv('NEO4J_URI', 'bolt://localhost:7687'),
                             auth=('neo4j', os.environ['NEO4J_PASSWORD']))
cache = redis.Redis.from_url(os.getenv('REDIS_URL', 'redis://localhost:6379'), decode_responses=True)
app = FastAPI(title='Food Graph API (Neo4j)')


def q(cypher, **params):
    with graph.session() as s:
        return s.run(cypher, **params).data()


def cached(key, ttl, compute):
    t = time.perf_counter()
    hit = cache.get(key)
    if hit:
        data, source = json.loads(hit), 'redis'
    else:
        data, source = compute(), 'neo4j'
        cache.setex(key, ttl, json.dumps(data, default=str))
    return {'source': source, 'ms': round((time.perf_counter() - t) * 1000, 1), 'data': data}


SUBSTITUTES = """
MATCH (p:Product {code: $code})-[:IN_GROUP]->(sg:SubGroup)
MATCH (p)-[:CONTAINS]->(i:Ingredient)<-[:CONTAINS]-(q:Product)-[:IN_GROUP]->(sg)
WHERE q.nutriscore < p.nutriscore
  AND ($avoid IS NULL OR NOT EXISTS { (q)-[:HAS_ALLERGEN]->(:Allergen {id: $avoid}) })
WITH p, q, count(DISTINCT i) AS shared
WITH q, shared, COUNT { (p)-[:CONTAINS]->() } AS mine, COUNT { (q)-[:CONTAINS]->() } AS theirs
RETURN q.code AS code, q.name AS name, q.nutriscore AS nutriscore, q.nova AS nova, shared,
       round(toFloat(shared) / (mine + theirs - shared), 2) AS jaccard
ORDER BY jaccard DESC LIMIT 5"""

COCKTAILS = """
MATCH (a:Additive) WHERE a.community IS NOT NULL
WITH a.community AS community, collect(a.id) AS members, max(a.community_name) AS name
WHERE size(members) >= 3
RETURN community, name, size(members) AS size, members ORDER BY size DESC"""

PARTNERS = """
MATCH (a:Additive {id: $id})-[c:CO_OCCURS]-(b:Additive)
RETURN b.id AS partner, c.count AS products, c.lift AS lift ORDER BY lift DESC LIMIT 10"""


@app.get('/health')
def health():
    return {'neo4j': q('RETURN 1 AS ok')[0]['ok'] == 1, 'redis': cache.ping()}


@app.get('/graph/substitutes/{code}')
def substitutes(code: str, avoid: str | None = None):
    return cached(f'gsub:{code}:{avoid}', 600, lambda: q(SUBSTITUTES, code=code, avoid=avoid))


@app.get('/graph/cocktails')
def cocktails():
    return cached('gcocktails', 3600, lambda: q(COCKTAILS))


@app.get('/graph/additives/{additive_id}/partners')
def partners(additive_id: str):
    return cached(f'gpartners:{additive_id}', 3600, lambda: q(PARTNERS, id=additive_id))
