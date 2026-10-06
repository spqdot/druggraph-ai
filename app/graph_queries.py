import os

from dotenv import load_dotenv
from neo4j import GraphDatabase


load_dotenv()

NEO4J_URI = os.getenv("NEO4J_URI")
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")


def get_driver():
    return GraphDatabase.driver(
        NEO4J_URI,
        auth=(NEO4J_USERNAME, NEO4J_PASSWORD)
    )


def get_disease_knowledge(disease_id):
    query = """
    MATCH (d:Disease {id: $disease_id})
    OPTIONAL MATCH (d)-[:ASSOCIATED_WITH]->(t:Target)

    OPTIONAL MATCH (t)-[:HAS_PROTEIN]->(p:Protein)

    OPTIONAL MATCH (t)-[:TARGETED_BY]->(drug:Drug)

    OPTIONAL MATCH (drug)-[:HAS_CLINICAL_TRIAL]->(trial:ClinicalTrial)

    RETURN
        d.id AS disease_id,
        d.name AS disease,
        t.id AS target_id,
        t.symbol AS target,
        t.name AS target_name,
        collect(DISTINCT {
            id: p.id,
            source: p.source
        }) AS proteins,
        collect(DISTINCT CASE
            WHEN drug.id IS NOT NULL THEN {
                id: drug.id,
                name: drug.name,
                type: drug.drug_type,
                maximum_stage: drug.maximum_clinical_stage
            }
        END) AS drugs,
        collect(DISTINCT CASE
            WHEN trial.id IS NOT NULL THEN {
                id: trial.id,
                phase: trial.phase,
                status: trial.overall_status,
                title: trial.title
            }
        END) AS clinical_trials
    ORDER BY target
    """

    with get_driver() as driver:
        with driver.session() as session:
            result = session.run(
                query,
                disease_id=disease_id
            )

            return [record.data() for record in result]


def get_drug_knowledge(disease_id, drug_name):
    query = """
    MATCH (d:Disease {id: $disease_id})
          -[:ASSOCIATED_WITH]->(t:Target)
          -[:TARGETED_BY]->(drug:Drug)
    WHERE toLower(drug.name) = toLower($drug_name)

    OPTIONAL MATCH (t)-[:HAS_PROTEIN]->(p:Protein)

    OPTIONAL MATCH (drug)-[:HAS_CLINICAL_TRIAL]->(trial:ClinicalTrial)

    RETURN
        d.id AS disease_id,
        d.name AS disease,
        t.id AS target_id,
        t.symbol AS target,
        t.name AS target_name,
        drug.id AS drug_id,
        drug.name AS drug,
        drug.drug_type AS drug_type,
        drug.maximum_clinical_stage AS maximum_clinical_stage,
        collect(DISTINCT CASE
            WHEN p.id IS NOT NULL THEN {
                id: p.id,
                source: p.source
            }
        END) AS proteins,
        collect(DISTINCT CASE
            WHEN trial.id IS NOT NULL THEN {
                id: trial.id,
                phase: trial.phase,
                status: trial.overall_status,
                title: trial.title
            }
        END) AS clinical_trials
    ORDER BY target
    """

    with get_driver() as driver:
        with driver.session() as session:
            result = session.run(
                query,
                disease_id=disease_id,
                drug_name=drug_name
            )

            return [record.data() for record in result]


def get_drug_trials(disease_id, drug_name):
    query = """
    MATCH (d:Disease {id: $disease_id})
          -[:ASSOCIATED_WITH]->(t:Target)
          -[:TARGETED_BY]->(drug:Drug)
    WHERE toLower(drug.name) = toLower($drug_name)

    MATCH (drug)-[:HAS_CLINICAL_TRIAL]->(trial:ClinicalTrial)

    RETURN DISTINCT
        d.name AS disease,
        t.symbol AS target,
        drug.id AS drug_id,
        drug.name AS drug,
        trial.id AS trial_id,
        trial.phase AS phase,
        trial.overall_status AS status,
        trial.title AS title,
        trial.start_date AS start_date
    ORDER BY trial.phase, trial.id
    """

    with get_driver() as driver:
        with driver.session() as session:
            result = session.run(
                query,
                disease_id=disease_id,
                drug_name=drug_name
            )

            return [record.data() for record in result]


def get_graph_data(disease_id):
    query = """
    MATCH (d:Disease {id: $disease_id})
    OPTIONAL MATCH (d)-[:ASSOCIATED_WITH]->(t:Target)
    OPTIONAL MATCH (t)-[:TARGETED_BY]->(drug:Drug)

    

    RETURN
        d,
        t,
        drug
    """

    with get_driver() as driver:
        with driver.session() as session:
            result = session.run(
                query,
                disease_id=disease_id
            )

            nodes = {}
            links = []

            for record in result:
                disease = record["d"]
                target = record["t"]
                drug = record["drug"]
                

                if disease:
                    disease_id_value = disease["id"]

                    nodes[disease_id_value] = {
                        "id": disease_id_value,
                        "label": disease.get("name"),
                        "type": "Disease"
                    }

                if target:
                    target_id = target["id"]

                    nodes[target_id] = {
                        "id": target_id,
                        "label": target.get("symbol"),
                        "type": "Target"
                    }

                    links.append({
                        "source": disease["id"],
                        "target": target_id,
                        "type": "ASSOCIATED_WITH"
                    })

                if drug:
                    drug_id = drug["id"]

                    nodes[drug_id] = {
                        "id": drug_id,
                        "label": drug.get("name"),
                        "type": "Drug"
                    }

                    if target:
                        links.append({
                            "source": target["id"],
                            "target": drug_id,
                            "type": "TARGETED_BY"
                        })

                

                    

                unique_links = {
                    (
                        link["source"],
                        link["target"],
                        link["type"]
                    ): link
                    for link in links
                }

                        count_result = session.run(
            """
            MATCH (d:Disease {id: $disease_id})
            OPTIONAL MATCH (d)-[:ASSOCIATED_WITH]->(t:Target)
            OPTIONAL MATCH (t)-[:TARGETED_BY]->(drug:Drug)
            OPTIONAL MATCH (drug)-[:HAS_CLINICAL_TRIAL]->(trial:ClinicalTrial)

            RETURN
                count(DISTINCT t) AS target_count,
                count(DISTINCT drug) AS drug_count,
                count(DISTINCT trial) AS clinical_trial_count
            """,
            disease_id=disease_id
        )

        counts = count_result.single()

                count_result = session.run(
            """
            MATCH (d:Disease {id: $disease_id})
            OPTIONAL MATCH (d)-[:ASSOCIATED_WITH]->(t:Target)
            OPTIONAL MATCH (t)-[:TARGETED_BY]->(drug:Drug)
            OPTIONAL MATCH (drug)-[:HAS_CLINICAL_TRIAL]->(trial:ClinicalTrial)

            RETURN
                count(DISTINCT t) AS target_count,
                count(DISTINCT drug) AS drug_count,
                count(DISTINCT trial) AS clinical_trial_count
            """,
            disease_id=disease_id
        )

        counts = count_result.single()

        return {
            "nodes": list(nodes.values()),
            "links": list(unique_links.values()),
            "stats": {
                "target_count": counts["target_count"],
                "drug_count": counts["drug_count"],
                "clinical_trial_count": counts["clinical_trial_count"]
            }
        }