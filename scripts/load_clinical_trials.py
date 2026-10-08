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
query TargetTrials($ensemblId: String!) {
    target(ensemblId: $ensemblId) {
        approvedSymbol

        drugAndClinicalCandidates {
            rows {
                drug {
                    id
                    name
                }

                diseases {
                    disease {
                        id
                        name
                    }
                }

                clinicalReports {
                    id
                    provider
                    title
                    trialStartDate
                    clinicalStage
                    trialOverallStatus
                    trialPhase
                    url
                    trialOfficialTitle
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
                   t.symbol AS symbol
            ORDER BY t.symbol
        """)

        targets = [record.data() for record in result]

    driver.close()

    return targets


def get_disease_ids_from_neo4j():
    driver = GraphDatabase.driver(
        NEO4J_URI,
        auth=(NEO4J_USERNAME, NEO4J_PASSWORD)
    )

    with driver.session() as session:
        result = session.run("""
            MATCH (d:Disease)
            RETURN d.id AS id
        """)

        disease_ids = {
            record["id"]
            for record in result
        }

    driver.close()

    return disease_ids


def get_trials_from_open_targets(ensembl_id):
    response = requests.post(
        OPEN_TARGETS_URL,
        json={
            "query": QUERY,
            "variables": {
                "ensemblId": ensembl_id
            }
        },
        timeout=60
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

    return target.get(
        "drugAndClinicalCandidates", {}
    ).get("rows", [])


def get_matching_disease_ids(row, valid_disease_ids):
    matched_ids = []

    for item in row.get("diseases", []):
        disease = item.get("disease")

        if not disease:
            continue

        disease_id = disease.get("id")

        if disease_id in valid_disease_ids:
            matched_ids.append(disease_id)

    return matched_ids


def save_clinical_trial(drug_id, report, disease_ids):

    driver = GraphDatabase.driver(
        NEO4J_URI,
        auth=(NEO4J_USERNAME, NEO4J_PASSWORD)
    )

    with driver.session() as session:

        session.run(
            """
            MATCH (d:Drug {id: $drug_id})

            MERGE (t:ClinicalTrial {id: $trial_id})

            SET t.provider = $provider,
                t.title = $title,
                t.start_date = $start_date,
                t.clinical_stage = $clinical_stage,
                t.overall_status = $overall_status,
                t.phase = $phase,
                t.url = $url,
                t.official_title = $official_title

            MERGE (d)-[:HAS_CLINICAL_TRIAL]->(t)
            """,
            drug_id=drug_id,
            trial_id=report["id"],
            provider=report.get("provider"),
            title=report.get("title"),
            start_date=report.get("trialStartDate"),
            clinical_stage=report.get("clinicalStage"),
            overall_status=report.get("trialOverallStatus"),
            phase=report.get("trialPhase"),
            url=report.get("url"),
            official_title=report.get("trialOfficialTitle")
        )

    driver.close()


def main():

    print("Fetching targets from Neo4j...\n")

    targets = get_targets_from_neo4j()

    print(f"Targets found: {len(targets)}")

    print("Fetching disease IDs from Neo4j...\n")

    valid_disease_ids = get_disease_ids_from_neo4j()

    print(f"Diseases found: {len(valid_disease_ids)}\n")

    total_trials = 0
    total_candidates = 0

    for target in targets:

        target_id = target["id"]
        symbol = target["symbol"]

        print(f"Processing {symbol}...")

        rows = get_trials_from_open_targets(target_id)

        candidate_count = 0
        trial_count = 0

        for row in rows:

            drug = row.get("drug")

            if not drug:
                continue

            matched_disease_ids = get_matching_disease_ids(
                row,
                valid_disease_ids
            )

            if not matched_disease_ids:
                continue

            candidate_count += 1
            total_candidates += 1

            for report in row.get("clinicalReports", []):

                if report.get("provider") != "AACT":
                    continue

                trial_id = report.get("id", "")

                if not trial_id.lower().startswith("nct"):
                    continue

                save_clinical_trial(
                    drug["id"],
                    report,
                    matched_disease_ids
                )

                trial_count += 1
                total_trials += 1

        print(
            f"  Disease-associated candidates: {candidate_count}"
        )

        print(
            f"  Clinical trials: {trial_count}"
        )

    print()
    print("✅ Clinical Trial loading complete!")
    print(f"Disease-associated candidates processed: {total_candidates}")
    print(f"Clinical trial records processed: {total_trials}")


if __name__ == "__main__":
    main()
