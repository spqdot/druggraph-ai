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