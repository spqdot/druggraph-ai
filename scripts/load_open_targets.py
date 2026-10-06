import os

import requests
from dotenv import load_dotenv
from neo4j import GraphDatabase


load_dotenv()

NEO4J_URI = os.getenv("NEO4J_URI")
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")

OPEN_TARGETS_URL = (
    "https://api.platform.opentargets.org/api/v4/graphql"
)


DISEASES = [
    {
        "id": "MONDO_0004975",
        "name": "Alzheimer disease",
    },
    {
        "id": "MONDO_0005180",
        "name": "Parkinson disease",
    },
]


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


def get_disease_targets(disease_id, size=10):
    variables = {
        "diseaseId": disease_id,
        "size": size,
    }

    response = requests.post(
        OPEN_TARGETS_URL,
        json={
            "query": QUERY,
            "variables": variables,
        },
        timeout=30,
    )

    response.raise_for_status()

    data = response.json()

    if "errors" in data:
        raise RuntimeError(data["errors"])

    disease = data["data"]["disease"]

    if disease is None:
        raise RuntimeError(
            f"Disease not found: {disease_id}"
        )

    return disease


def save_to_neo4j(disease):
    driver = GraphDatabase.driver(
        NEO4J_URI,
        auth=(
            NEO4J_USERNAME,
            NEO4J_PASSWORD,
        ),
    )

    with driver.session() as session:

        session.run(
            """
            MERGE (d:Disease {id: $id})
            SET d.name = $name
            """,
            id=disease["id"],
            name=disease["name"],
        )

        for row in disease["associatedTargets"]["rows"]:

            target = row["target"]
            score = row["score"]

            session.run(
                """
                MERGE (t:Target {id: $id})
                SET t.symbol = $symbol,
                    t.name = $name

                MATCH (d:Disease {id: $disease_id})

                MERGE (d)-[r:ASSOCIATED_WITH]->(t)
                SET r.score = $score
                """,
                id=target["id"],
                symbol=target["approvedSymbol"],
                name=target["approvedName"],
                disease_id=disease["id"],
                score=score,
            )

    driver.close()


if __name__ == "__main__":

    for disease_config in DISEASES:

        disease_id = disease_config["id"]

        print(
            f"\nFetching "
            f"{disease_config['name']}..."
        )

        disease = get_disease_targets(
            disease_id
        )

        target_count = len(
            disease["associatedTargets"]["rows"]
        )

        print(
            f"Disease: {disease['name']}"
        )

        print(
            f"Targets found: {target_count}"
        )

        save_to_neo4j(disease)

        print(
            "✅ Data loaded into Neo4j!"
        )

    print(
        "\n✅ Disease target loading complete!"
    )