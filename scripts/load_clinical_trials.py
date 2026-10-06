import os
import requests
from dotenv import load_dotenv
from neo4j import GraphDatabase

load_dotenv()

NEO4J_URI = os.getenv("NEO4J_URI")
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")

OPEN_TARGETS_URL = "https://api.platform.opentargets.org/api/v4/graphql"

ALZHEIMER_ID = "MONDO_0004975"

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


def is_alzheimer_candidate(row):
    for item in row.get("diseases", []):
        disease = item.get("disease")

        if disease and disease.get("id") == ALZHEIMER_ID:
            return True

    return False


def looks_like_alzheimer_trial(report):
    title = (
        report.get("title") or
        report.get("trialOfficialTitle") or
        ""
    ).lower()

    keywords = [
        "alzheimer",
        "alzheimer's",
        "alzheimer’s",
        "dominantly inherited alzheimer"
    ]

    return any(keyword in title for keyword in keywords)


def save_clinical_trial(drug_id, report):

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
            provider=report["provider"],
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

    print(f"Targets found: {len(targets)}\n")

    total_trials = 0

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

            # Only candidates associated with Alzheimer disease
            if not is_alzheimer_candidate(row):
                continue

            candidate_count += 1

            for report in row.get("clinicalReports", []):

                # Only ClinicalTrials.gov / AACT records
                if report.get("provider") != "AACT":
                    continue

                trial_id = report.get("id", "")

                if not trial_id.lower().startswith("nct"):
                    continue

                # Secondary title-level filter
                if not looks_like_alzheimer_trial(report):
                    continue

                save_clinical_trial(
                    drug["id"],
                    report
                )

                trial_count += 1
                total_trials += 1

        print(
            f"  Alzheimer candidates: {candidate_count}"
        )
        print(
            f"  Alzheimer clinical trials: {trial_count}"
        )

    print()
    print("✅ Clinical Trial loading complete!")
    print(f"Clinical trial records processed: {total_trials}")


if __name__ == "__main__":
    main()