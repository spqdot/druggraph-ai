import os
import requests
from dotenv import load_dotenv
from neo4j import GraphDatabase

load_dotenv()

NEO4J_URI = os.getenv("NEO4J_URI")
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")

OPEN_TARGETS_URL = "https://api.platform.opentargets.org/api/v4/graphql"


def get_target_proteins(ensembl_id):
    query = """
    query TargetInfo($ensemblId: String!) {
        target(ensemblId: $ensemblId) {
            id
            approvedSymbol
            approvedName
            proteinIds {
                id
                source
            }
        }
    }
    """

    response = requests.post(
        OPEN_TARGETS_URL,
        json={
            "query": query,
            "variables": {"ensemblId": ensembl_id}
        },
        timeout=30
    )

    response.raise_for_status()

    data = response.json()

    if "errors" in data:
        print(f"Open Targets error for {ensembl_id}:")
        print(data["errors"])
        return None

    return data.get("data", {}).get("target")


def save_proteins(driver, target, proteins):
    with driver.session() as session:
        for protein in proteins:
            protein_id = protein.get("id")
            source = protein.get("source")

            if not protein_id:
                continue

            session.run(
                """
                MATCH (t:Target {id: $target_id})

                MERGE (p:Protein {id: $protein_id})
                SET p.source = $source

                MERGE (t)-[:HAS_PROTEIN]->(p)
                """,
                target_id=target["id"],
                protein_id=protein_id,
                source=source
            )


def main():
    print("Loading Target → Protein relationships...")

    driver = GraphDatabase.driver(
        NEO4J_URI,
        auth=(NEO4J_USERNAME, NEO4J_PASSWORD)
    )

    with driver.session() as session:
        result = session.run(
            """
            MATCH (t:Target)
            RETURN t.id AS id, t.symbol AS symbol
            ORDER BY t.symbol
            """
        )

        targets = [record.data() for record in result]

    print(f"Targets found in Neo4j: {len(targets)}")

    total_proteins = 0

    for target in targets:
        target_id = target["id"]
        symbol = target["symbol"]

        print(f"\nProcessing {symbol} ({target_id})...")

        data = get_target_proteins(target_id)

        if not data:
            print("  No target data found.")
            continue

        proteins = data.get("proteinIds", [])

        print(f"  Proteins found: {len(proteins)}")

        save_proteins(driver, target, proteins)

        total_proteins += len(proteins)

    driver.close()

    print("\nProtein loading complete!")
    print(f"Protein records processed: {total_proteins}")


if __name__ == "__main__":
    main()
