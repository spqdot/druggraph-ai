import os
import requests
from dotenv import load_dotenv
from neo4j import GraphDatabase

load_dotenv()

NEO4J_URI = os.getenv("NEO4J_URI")
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")

OPEN_TARGETS_URL = "https://api.platform.opentargets.org/api/v4/graphql"


QUERY = """
query DiseaseTargets($diseaseId: String!, $size: Int!) {
  disease(efoId: $diseaseId) {
    id
    name
    associatedTargets(page: {index: 0, size: $size}) {
      rows {
        target {
          id
          approvedSymbol
          approvedName
        }
        score
      }
    }
  }
}
"""


def get_alzheimer_targets():
    variables = {
        "diseaseId": "MONDO_0004975",
        "size": 10
    }

    response = requests.post(
        OPEN_TARGETS_URL,
        json={
            "query": QUERY,
            "variables": variables
        },
        timeout=30
    )

    response.raise_for_status()

    data = response.json()

    if "errors" in data:
        raise RuntimeError(data["errors"])

    return data["data"]["disease"]


def save_to_neo4j(disease):
    driver = GraphDatabase.driver(
        NEO4J_URI,
        auth=(NEO4J_USERNAME, NEO4J_PASSWORD)
    )

    with driver.session() as session:

        # Create disease
        session.run(
            """
            MERGE (d:Disease {id: $id})
            SET d.name = $name
            """,
            id=disease["id"],
            name=disease["name"]
        )

        # Create targets and relationships
        for row in disease["associatedTargets"]["rows"]:

            target = row["target"]
            score = row["score"]

            session.run(
                """
                MERGE (g:Gene {id: $id})
                SET g.symbol = $symbol,
                    g.name = $name

                MATCH (d:Disease {id: $disease_id})

                MERGE (d)-[r:ASSOCIATED_WITH]->(g)
                SET r.score = $score
                """,
                id=target["id"],
                symbol=target["approvedSymbol"],
                name=target["approvedName"],
                disease_id=disease["id"],
                score=score
            )

    driver.close()


if __name__ == "__main__":

    print("Fetching Alzheimer disease data...")

    disease = get_alzheimer_targets()

    print(f"Disease: {disease['name']}")
    print(
        f"Targets found: "
        f"{len(disease['associatedTargets']['rows'])}"
    )

    save_to_neo4j(disease)

    print("✅ Data loaded into Neo4j!")