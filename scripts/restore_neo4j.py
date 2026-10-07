import json
import os

from dotenv import load_dotenv
from neo4j import GraphDatabase

load_dotenv()

URI = os.getenv("NEO4J_URI", "neo4j://127.0.0.1:7687")
USERNAME = os.getenv("NEO4J_USERNAME", "neo4j")
PASSWORD = os.getenv("NEO4J_PASSWORD")

EXPORT_FILE = "data/neo4j_export.json"

if not PASSWORD:
    raise RuntimeError("NEO4J_PASSWORD is not set in .env")

with open(EXPORT_FILE, "r", encoding="utf-8") as f:
    data = json.load(f)

nodes = data["nodes"]
relationships = data["relationships"]

print(f"Nodes to restore: {len(nodes)}")
print(f"Relationships to restore: {len(relationships)}")
print(f"Connecting to: {URI}")

driver = GraphDatabase.driver(
    URI,
    auth=(USERNAME, PASSWORD)
)

with driver.session() as session:

    # Clear the local database before restoration.
    session.run("MATCH (n) DETACH DELETE n").consume()

    # Restore nodes.
    node_query = """
    CREATE (n)
    SET n = $properties
    SET n:$( $label )
    """

    for node in nodes:
        labels = node.get("labels", [])
        properties = node.get("properties", {})

        for label in labels:
            session.run(
                node_query,
                properties={
                    **properties,
                    "_export_element_id": node["element_id"],
                },
                label=label,
            ).consume()

    print("Nodes restored.")

    # Restore relationships using the temporary export element ID.
    relationship_query = """
    MATCH (a {_export_element_id: $start_id})
    MATCH (b {_export_element_id: $end_id})
    CREATE (a)-[r:$( $type )]->(b)
    SET r = $properties
    """

    for relationship in relationships:
        session.run(
            relationship_query,
            start_id=relationship["start_element_id"],
            end_id=relationship["end_element_id"],
            type=relationship["type"],
            properties=relationship.get("properties", {}),
        ).consume()

    print("Relationships restored.")

    # Remove temporary mapping property.
    session.run(
        "MATCH (n) REMOVE n._export_element_id"
    ).consume()

    node_count = session.run(
        "MATCH (n) RETURN count(n) AS count"
    ).single()["count"]

    relationship_count = session.run(
        "MATCH ()-[r]->() RETURN count(r) AS count"
    ).single()["count"]

driver.close()

print()
print("RESTORE COMPLETE")
print(f"Nodes: {node_count}")
print(f"Relationships: {relationship_count}")
