import json
import os

from dotenv import load_dotenv
from neo4j import GraphDatabase


load_dotenv()

NEO4J_URI = os.getenv("NEO4J_URI")
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")

OUTPUT_FILE = "data/neo4j_export.json"


def export_graph():
    driver = GraphDatabase.driver(
        NEO4J_URI,
        auth=(NEO4J_USERNAME, NEO4J_PASSWORD)
    )

    with driver.session() as session:

        node_result = session.run(
            """
            MATCH (n)
            RETURN
                elementId(n) AS element_id,
                labels(n) AS labels,
                properties(n) AS properties
            """
        )

        nodes = [
            record.data()
            for record in node_result
        ]

        relationship_result = session.run(
            """
            MATCH (a)-[r]->(b)
            RETURN
                elementId(a) AS start_element_id,
                elementId(b) AS end_element_id,
                type(r) AS type,
                properties(r) AS properties
            """
        )

        relationships = [
            record.data()
            for record in relationship_result
        ]

    driver.close()

    export = {
        "nodes": nodes,
        "relationships": relationships
    }

    os.makedirs("data", exist_ok=True)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as file:
        json.dump(export, file, indent=2, default=str)

    print(f"✅ Graph exported successfully!")
    print(f"Nodes: {len(nodes)}")
    print(f"Relationships: {len(relationships)}")
    print(f"Saved to: {OUTPUT_FILE}")


if __name__ == "__main__":
    export_graph()