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
query TargetDrugs($ensemblId: String!) {
    target(ensemblId: $ensemblId) {
        approvedSymbol

        drugAndClinicalCandidates {
            count

            rows {
                id
                maxClinicalStage

                drug {
                    id
                    name
                    drugType
                    maximumClinicalStage
                }
            }
        }
    }
}
"""


def get_targets_from_neo4j():
    driver = GraphDatabase.driver(
        NEO4J_URI,
        auth=(NEO4J_USERNAME, NEO4J_PASSWORD)
    )

    with driver.session() as session:
        result = session.run("""
            MATCH (t:Target)
            RETURN t.id AS id,
                   t.symbol AS symbol,
                   t.name AS name
            ORDER BY t.symbol
        """)

        targets = [record.data() for record in result]

    driver.close()

    return targets


def get_drugs_from_open_targets(ensembl_id):
    response = requests.post(
        OPEN_TARGETS_URL,
        json={
            "query": QUERY,
            "variables": {
                "ensemblId": ensembl_id
            }
        },
        timeout=30
    )

    response.raise_for_status()

    data = response.json()

    if "errors" in data:
        print("Open Targets error:")
        print(data["errors"])
        return []

    target = data.get("data", {}).get("target")

    if not target:
        return []

    candidates = target.get(
        "drugAndClinicalCandidates",
        {}
    )

    return candidates.get("rows", [])


def save_drug_to_neo4j(
    target_id,
    drug,
    clinical_stage
):
    driver = GraphDatabase.driver(
        NEO4J_URI,
        auth=(NEO4J_USERNAME, NEO4J_PASSWORD)
    )

    with driver.session() as session:
        session.run(
            """
            MATCH (t:Target {id: $target_id})

            MERGE (d:Drug {id: $drug_id})

            SET d.name = $drug_name,
                d.drug_type = $drug_type,
                d.maximum_clinical_stage = $maximum_stage

            MERGE (t)-[r:TARGETED_BY]->(d)

            SET r.clinical_stage = $clinical_stage
            """,
            target_id=target_id,
            drug_id=drug["id"],
            drug_name=drug["name"],
            drug_type=drug["drugType"],
            maximum_stage=drug["maximumClinicalStage"],
            clinical_stage=clinical_stage
        )

    driver.close()


def main():

    print("Fetching targets from Neo4j...\n")

    targets = get_targets_from_neo4j()

    print(f"Targets found: {len(targets)}\n")

    total_drugs = 0

    for target in targets:

        target_id = target["id"]
        symbol = target["symbol"]

        print(
            f"Processing {symbol} ({target_id})..."
        )

        rows = get_drugs_from_open_targets(
            target_id
        )

        print(
            f"  Drugs/candidates found: {len(rows)}"
        )

        for row in rows:

            drug = row.get("drug")

            if not drug:
                continue

            save_drug_to_neo4j(
                target_id,
                drug,
                row["maxClinicalStage"]
            )

            print(
                f"    → {drug['name']} "
                f"({row['maxClinicalStage']})"
            )

            total_drugs += 1

    print()
    print(
        f"✅ Drug loading complete! "
        f"Records processed: {total_drugs}"
    )


if __name__ == "__main__":
    main()