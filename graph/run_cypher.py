
"""Run every query in a .cypher file, time it, and print the first rows."""
import os, sys, time
from dotenv import load_dotenv
from neo4j import GraphDatabase

load_dotenv()
driver = GraphDatabase.driver('bolt://localhost:7687', auth=('neo4j', os.environ['NEO4J_PASSWORD']))
blocks = [b.strip() for b in open(sys.argv[1], encoding='utf-8').read().split(';') if b.strip()]
with driver.session() as s:
    for block in blocks:
        t = time.perf_counter()
        rows = s.run(block).data()
        print(f'\n=== {block.splitlines()[0]}  ({(time.perf_counter() - t) * 1000:.0f} ms) ===', flush=True)
        for row in rows[:100]:
            print(row)
driver.close()
