def build_drug_context(data):
    if not data:
        return ""

    sections = []

    for item in data:
        section = f"""
Disease: {item.get("disease")}
Target: {item.get("target")}
Target name: {item.get("target_name")}

Drug: {item.get("drug")}
Drug ID: {item.get("drug_id")}
Drug type: {item.get("drug_type")}
Maximum clinical stage: {item.get("maximum_clinical_stage")}

Proteins:
"""

        proteins = item.get("proteins", [])

        # Keep the context focused: prefer current Swiss-Prot
        # identifiers and limit the number sent to the LLM.
        preferred_proteins = [
            protein
            for protein in proteins
            if protein
            and protein.get("id")
            and protein.get("source") == "uniprot_swissprot"
        ]

        for protein in preferred_proteins[:10]:
            section += (
                f"- {protein['id']} "
                f"(source: {protein.get('source')})\n"
            )

        section += "\nClinical trials:\n"

        trials = item.get("clinical_trials", [])

        for trial in trials:
            if trial and trial.get("id"):
                section += (
                    f"- Trial ID: {trial.get('id')}\n"
                    f"  Phase: {trial.get('phase')}\n"
                    f"  Status: {trial.get('status')}\n"
                    f"  Title: {trial.get('title')}\n"
                )

        sections.append(section)

    return "\n".join(sections)


def build_disease_context(data):
    """Build an explicit, disease-scoped representation of graph relationships."""
    if not data:
        return ""

    first = data[0]
    disease = first.get("disease") or "Unknown disease"
    disease_id = first.get("disease_id") or "unknown"
    lines = [
        f"Selected disease: {disease} ({disease_id})",
        "The following facts were retrieved from Cosmos DB:",
    ]

    seen_targets = set()
    seen_drugs = set()
    seen_trials = set()

    for item in data:
        target = item.get("target") or item.get("target_name")
        target_id = item.get("target_id") or "unknown"
        target_key = (target_id, target)

        if target and target_key not in seen_targets:
            lines.append(
                f"- {disease} --ASSOCIATED_WITH--> "
                f"{target} ({item.get('target_name') or target}; {target_id})"
            )
            seen_targets.add(target_key)

        drugs = item.get("drugs") or []
        if not drugs and target:
            lines.append(
                f"  - No drugs are currently linked to {target} in this graph."
            )

        for drug in drugs:
            drug_name = drug.get("name") or "Unnamed drug"
            drug_id = drug.get("id") or "unknown"
            relationship_key = (target_key, drug_id)
            if relationship_key not in seen_drugs:
                details = []
                if drug.get("type"):
                    details.append(f"type: {drug['type']}")
                if drug.get("maximum_stage"):
                    details.append(
                        f"maximum clinical stage: {drug['maximum_stage']}"
                    )
                suffix = f" ({'; '.join(details)})" if details else ""
                lines.append(
                    f"  - {target} --TARGETED_BY--> {drug_name} "
                    f"({drug_id}){suffix}"
                )
                seen_drugs.add(relationship_key)

        for trial in item.get("clinical_trials") or []:
            trial_id = trial.get("id")
            if not trial_id or trial_id in seen_trials:
                continue

            details = []
            if trial.get("phase"):
                details.append(f"phase: {trial['phase']}")
            if trial.get("status"):
                details.append(f"status: {trial['status']}")
            if trial.get("title"):
                details.append(f"title: {trial['title']}")
            suffix = f" ({'; '.join(details)})" if details else ""
            lines.append(f"  - Drug --HAS_CLINICAL_TRIAL--> {trial_id}{suffix}")
            seen_trials.add(trial_id)

    if not seen_trials:
        lines.append(
            "- No clinical trials are currently linked to this disease's "
            "retrieved drugs in the graph."
        )

    return "\n".join(lines)




def build_trial_context(data):
    if not data:
        return ""

    first = data[0]

    context = f"""
Disease: {first.get("disease")}
Target: {first.get("target")}
Drug: {first.get("drug")}
Drug ID: {first.get("drug_id")}

Clinical trials:
"""

    for trial in data:
        context += (
            f"- Trial ID: {trial.get('trial_id')}\n"
            f"  Phase: {trial.get('phase')}\n"
            f"  Status: {trial.get('status')}\n"
            f"  Start date: {trial.get('start_date')}\n"
            f"  Title: {trial.get('title')}\n"
        )

    return context