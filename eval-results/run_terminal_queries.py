"""
Execute and retrieve openCypher queries from terminal against FalkorDB.
"""

import sys
from pathlib import Path

# Add graph-agent-memory/src to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "graph-agent-memory" / "src"))

from graph_memory.db import get_db

db = get_db()

print("=" * 80)
print("QUERY A: Knowledge cluster for workspace 'hackathon-eval-real-ab01'")
print("=" * 80)
cypher_a = """
MATCH (n) WHERE n.workspace_id = 'hackathon-eval-real-ab01'
OPTIONAL MATCH (n)-[r]->(m)
RETURN labels(n)[0] AS node_type, n.id AS id, type(r) AS relationship, labels(m)[0] AS target_type, m.id AS target_id
"""
res_a = db.query(cypher_a)
for row in res_a.result_set:
    rel_str = f"--({row[2]})--> [{row[3]}] {row[4]}" if row[2] else "-- (isolated node)"
    print(f"[{row[0]}] {row[1]} {rel_str}")

print("\n" + "=" * 80)
print("QUERY B: Architectural Decisions Stored in FalkorDB")
print("=" * 80)
cypher_b = "MATCH (d:Decision) RETURN d.title, d.status, d.rationale"
res_b = db.query(cypher_b)
for row in res_b.result_set:
    print(f"* TITLE: {row[0]}")
    print(f"  STATUS: {row[1]}")
    print(f"  RATIONALE: {row[2]}\n")

print("=" * 80)
print("QUERY C: Session Checkpoints & Handoff State")
print("=" * 80)
cypher_c = "MATCH (s:Session) RETURN s.id, s.workspace_id, s.summary, s.next_steps, s.changed_files"
res_c = db.query(cypher_c)
for row in res_c.result_set:
    print(f"* SESSION ID: {row[0]} (Workspace: {row[1]})")
    print(f"  SUMMARY: {row[2]}")
    print(f"  NEXT STEPS: {row[3]}")
    print(f"  CHANGED FILES: {row[4]}\n")
