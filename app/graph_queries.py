
import os
from collections import defaultdict

from dotenv import load_dotenv
from gremlin_python.driver import client, serializer

load_dotenv()

COSMOS_GREMLIN_ENDPOINT = os.getenv("COSMOS_GREMLIN_ENDPOINT")
COSMOS_DATABASE = os.getenv("COSMOS_DATABASE", "druggraphdb")
COSMOS_GRAPH = os.getenv("COSMOS_GRAPH", "druggraph")
COSMOS_GREMLIN_PASSWORD = os.getenv("COSMOS_GREMLIN_PASSWORD")
PARTITION_KEY = "druggraph"


def get_driver():
    if not COSMOS_GREMLIN_ENDPOINT or not COSMOS_GREMLIN_PASSWORD:
        raise RuntimeError("Missing Cosmos DB Gremlin configuration.")

    return client.Client(
        COSMOS_GREMLIN_ENDPOINT,
        "g",
        username=f"/dbs/{COSMOS_DATABASE}/colls/{COSMOS_GRAPH}",
        password=COSMOS_GREMLIN_PASSWORD,
        message_serializer=serializer.GraphSONSerializersV2d0(),
    )


def _submit(c, query, bindings=None):
    if bindings:
        return c.submit(query, bindings).all().result()
    return c.submit(query).all().result()


def _first(value):
    return value[0] if isinstance(value, list) and value else (
        None if isinstance(value, list) else value
    )


def _vertex(raw):
    return {key: _first(value) for key, value in raw.items()}


def _vertices(c, label):
    query = (
        f"g.V().has('partitionKey', pk).hasLabel('{label}')"
        ".valueMap(true)"
    )
    return [
        _vertex(row)
        for row in _submit(c, query, {"pk": PARTITION_KEY})
    ]


def _edges(c, label):
    query = (
        f"g.E().hasLabel('{label}')"
        ".project('source','target')"
        ".by(outV().id()).by(inV().id())"
    )
    return _submit(c, query)

def _disease_targets(c, disease_id):
    query = (
        "g.V().has('partitionKey', pk).hasLabel('Disease')"
        ".has('id', did).out('ASSOCIATED_WITH')"
        ".hasLabel('Target').valueMap(true)"
    )
    rows = _submit(c, query, {"pk": PARTITION_KEY, "did": disease_id})
    return [_vertex(row) for row in rows]


def _target_proteins(c, target_id):
    query = (
        "g.V().has('partitionKey', pk).has('id', tid)"
        ".hasLabel('Target').out('HAS_PROTEIN')"
        ".hasLabel('Protein').valueMap(true)"
    )
    rows = _submit(c, query, {"pk": PARTITION_KEY, "tid": target_id})
    return [_vertex(row) for row in rows]


def _target_drugs(c, target_id):
    query = (
        "g.V().has('partitionKey', pk).has('id', tid)"
        ".hasLabel('Target').out('TARGETED_BY')"
        ".hasLabel('Drug').valueMap(true)"
    )
    rows = _submit(c, query, {"pk": PARTITION_KEY, "tid": target_id})
    return [_vertex(row) for row in rows]


def _drug_trials(c, drug_id):
    query = (
        "g.V().has('partitionKey', pk).has('id', did)"
        ".hasLabel('Drug').out('HAS_CLINICAL_TRIAL')"
        ".hasLabel('ClinicalTrial').valueMap(true)"
    )
    rows = _submit(c, query, {"pk": PARTITION_KEY, "did": drug_id})
    return [_vertex(row) for row in rows]

def _connected(vertices, edges, source_id, edge_type, target_label=None):
    vertices = {}
    for label in ("Disease", "Target", "Protein", "Drug", "ClinicalTrial"):
        for vertex in _vertices(c, label):
            vertices[vertex["id"]] = vertex

    edges = defaultdict(list)
    for label in (
        "ASSOCIATED_WITH",
        "HAS_PROTEIN",
        "TARGETED_BY",
        "HAS_CLINICAL_TRIAL",
    ):
        for edge in _edges(c, label):
            edges[(edge["source"], label)].append(edge["target"])

    return vertices, edges


def _connected(vertices, edges, source_id, edge_type, target_label=None):
    results = []
    for target_id in edges.get((source_id, edge_type), []):
        vertex = vertices.get(target_id)
        if vertex and (
            target_label is None or vertex.get("label") == target_label
        ):
            results.append(vertex)
    return results


def _protein_records(vertices, edges, target_id):
    return [
        {"id": p.get("id"), "source": p.get("source")}
        for p in _connected(vertices, edges, target_id, "HAS_PROTEIN", "Protein")
    ]


def _trial_records(vertices, edges, drug_id):
    return [
        {
            "id": t.get("id"),
            "phase": t.get("phase"),
            "status": t.get("overall_status"),
            "title": t.get("title") or t.get("official_title"),
        }
        for t in _connected(
            vertices, edges, drug_id, "HAS_CLINICAL_TRIAL", "ClinicalTrial"
        )
    ]


def get_diseases():
    c = get_driver()
    try:
        return sorted(
            [
                {"id": d.get("id"), "name": d.get("name")}
                for d in _vertices(c, "Disease")
            ],
            key=lambda item: item.get("name") or "",
        )
    finally:
        c.close()



def get_disease_knowledge(disease_id):
    c = get_driver()
    try:
        disease_rows = _submit(
            c,
            "g.V().has('partitionKey', pk).hasLabel('Disease')"
            ".has('id', did).valueMap(true)",
            {"pk": PARTITION_KEY, "did": disease_id},
        )
        if not disease_rows:
            return []

        disease = _vertex(disease_rows[0])
        targets = _disease_targets(c, disease_id)
        results = []

        for target in targets:
            proteins = _target_proteins(c, target["id"])
            drugs = _target_drugs(c, target["id"])

            drug_records = []
            clinical_trials = []

            for drug in drugs:
                drug_records.append({
                    "id": drug.get("id"),
                    "name": drug.get("name"),
                    "type": drug.get("drug_type"),
                    "maximum_stage": drug.get("maximum_clinical_stage"),
                })
                clinical_trials.extend([
                    {
                        "id": trial.get("id"),
                        "phase": trial.get("phase"),
                        "status": trial.get("overall_status"),
                        "title": trial.get("title") or trial.get("official_title"),
                    }
                    for trial in _drug_trials(c, drug["id"])
                ])

            results.append({
                "disease_id": disease.get("id"),
                "disease": disease.get("name"),
                "target_id": target.get("id"),
                "target": target.get("symbol") or target.get("name"),
                "target_name": target.get("name"),
                "proteins": [
                    {"id": p.get("id"), "source": p.get("source")}
                    for p in proteins
                ],
                "drugs": drug_records,
                "clinical_trials": clinical_trials,
            })

        return results
    finally:
        c.close()



def get_drug_knowledge(disease_id, drug_name):
    c = get_driver()
    try:
        disease_rows = _submit(
            c,
            "g.V().has('partitionKey', pk).hasLabel('Disease')"
            ".has('id', did).valueMap(true)",
            {"pk": PARTITION_KEY, "did": disease_id},
        )
        if not disease_rows:
            return []

        disease = _vertex(disease_rows[0])
        results = []

        for target in _disease_targets(c, disease_id):
            drugs = _target_drugs(c, target["id"])

            for drug in drugs:
                if (drug.get("name") or "").casefold() != drug_name.casefold():
                    continue

                proteins = _target_proteins(c, target["id"])
                trials = _drug_trials(c, drug["id"])

                results.append({
                    "disease_id": disease.get("id"),
                    "disease": disease.get("name"),
                    "target_id": target.get("id"),
                    "target": target.get("symbol") or target.get("name"),
                    "target_name": target.get("name"),
                    "drug_id": drug.get("id"),
                    "drug": drug.get("name"),
                    "drug_type": drug.get("drug_type"),
                    "maximum_clinical_stage": drug.get(
                        "maximum_clinical_stage"
                    ),
                    "proteins": [
                        {"id": p.get("id"), "source": p.get("source")}
                        for p in proteins
                    ],
                    "clinical_trials": [
                        {
                            "id": trial.get("id"),
                            "phase": trial.get("phase"),
                            "status": trial.get("overall_status"),
                            "title": trial.get("title")
                            or trial.get("official_title"),
                        }
                        for trial in trials
                    ],
                })

        return results
    finally:
        c.close()




def get_drug_trials(disease_id, drug_name):
    c = get_driver()
    try:
        disease_rows = _submit(
            c,
            "g.V().has('partitionKey', pk).hasLabel('Disease')"
            ".has('id', did).valueMap(true)",
            {"pk": PARTITION_KEY, "did": disease_id},
        )
        if not disease_rows:
            return []

        disease = _vertex(disease_rows[0])
        results = []

        for target in _disease_targets(c, disease_id):
            for drug in _target_drugs(c, target["id"]):
                if (drug.get("name") or "").casefold() != drug_name.casefold():
                    continue

                for trial in _drug_trials(c, drug["id"]):
                    results.append({
                        "disease": disease.get("name"),
                        "target": target.get("symbol") or target.get("name"),
                        "drug_id": drug.get("id"),
                        "drug": drug.get("name"),
                        "trial_id": trial.get("id"),
                        "phase": trial.get("phase"),
                        "status": trial.get("overall_status"),
                        "title": trial.get("title")
                        or trial.get("official_title"),
                        "start_date": trial.get("start_date"),
                    })

        return sorted(
            results,
            key=lambda row: (
                row.get("phase") or "",
                row.get("trial_id") or "",
            ),
        )
    finally:
        c.close()




def get_graph_data(disease_id):
    c = get_driver()
    try:
        disease_rows = _submit(
            c,
            "g.V().has('partitionKey', pk).hasLabel('Disease')"
            ".has('id', did).valueMap(true)",
            {"pk": PARTITION_KEY, "did": disease_id},
        )

        if not disease_rows:
            return {
                "nodes": [],
                "links": [],
                "stats": {
                    "target_count": 0,
                    "drug_count": 0,
                    "clinical_trial_count": 0,
                },
            }

        disease = _vertex(disease_rows[0])
        nodes = []
        links = []
        included = set()

        def add_node(vertex):
            vertex_id = vertex["id"]
            if vertex_id not in included:
                nodes.append({
                    "id": vertex_id,
                    "label": (
                        vertex.get("name")
                        or vertex.get("symbol")
                        or vertex_id
                    ),
                    "type": vertex.get("label"),
                })
                included.add(vertex_id)

        def add_link(source, target, edge_type):
            links.append({
                "source": source,
                "target": target,
                "type": edge_type,
            })

        add_node(disease)

        targets = _disease_targets(c, disease_id)
        drugs_by_id = {}

        for target in targets:
            add_node(target)
            add_link(disease_id, target["id"], "ASSOCIATED_WITH")

            for drug in _target_drugs(c, target["id"]):
                drugs_by_id[drug["id"]] = drug
                add_node(drug)
                add_link(target["id"], drug["id"], "TARGETED_BY")

        trials_by_id = {}

        for drug in drugs_by_id.values():
            for trial in _drug_trials(c, drug["id"]):
                trials_by_id[trial["id"]] = trial
                add_node(trial)
                add_link(
                    drug["id"], trial["id"], "HAS_CLINICAL_TRIAL"
                )

        return {
            "nodes": nodes,
            "links": links,
            "stats": {
                "target_count": len(targets),
                "drug_count": len(drugs_by_id),
                "clinical_trial_count": len(trials_by_id),
            },
        }
    finally:
        c.close()
