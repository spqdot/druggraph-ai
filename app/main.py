from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.context_builder import build_drug_context
from app.graph_queries import (
    get_disease_knowledge,
    get_drug_knowledge,
    get_graph_data,
)
from app.llm import generate_answer


app = FastAPI(
    title="DrugGraph AI API",
    description="Knowledge Graph API for Alzheimer disease drug discovery",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def root():
    return {
        "message": "DrugGraph AI API is running"
    }


@app.get("/api/disease/{disease_id}")
def disease_knowledge(disease_id: str):
    data = get_disease_knowledge(disease_id)

    if not data:
        raise HTTPException(
            status_code=404,
            detail=f"Disease not found: {disease_id}"
        )

    return {
        "disease_id": disease_id,
        "results": data
    }


@app.get("/api/disease/{disease_id}/drug/{drug_name}")
def drug_knowledge(disease_id: str, drug_name: str):
    data = get_drug_knowledge(
        disease_id,
        drug_name
    )

    if not data:
        raise HTTPException(
            status_code=404,
            detail=f"Drug not found: {drug_name}"
        )

    return {
        "disease_id": disease_id,
        "drug": drug_name,
        "results": data
    }
@app.get("/api/graph/{disease_id}")
def graph_data(disease_id: str):
    data = get_graph_data(disease_id)

    if not data["nodes"]:
        raise HTTPException(
            status_code=404,
            detail=f"No graph data found for disease: {disease_id}"
        )

    return data

class AskRequest(BaseModel):
    question: str
    disease_id: str = "MONDO_0004975"
    drug_name: str | None = None


@app.post("/api/ask")
def ask_knowledge_graph(request: AskRequest):
    if request.drug_name:
        data = get_drug_knowledge(
            request.disease_id,
            request.drug_name
        )

        if not data:
            raise HTTPException(
                status_code=404,
                detail=f"Drug not found: {request.drug_name}"
            )

        context = build_drug_context(data)

        targets = sorted({
            item.get("target")
            for item in data
            if item.get("target")
        })

        protein_ids = {
            protein.get("id")
            for item in data
            for protein in item.get("proteins", [])
            if protein and protein.get("id")
        }

        trial_ids = {
            trial.get("id")
            for item in data
            for trial in item.get("clinical_trials", [])
            if trial and trial.get("id")
        }

        sources = {
            "disease": data[0].get("disease"),
            "target": targets,
            "drug": data[0].get("drug"),
            "drug_id": data[0].get("drug_id"),
            "protein_count": len(protein_ids),
            "clinical_trial_count": len(trial_ids)
        }

    else:
        data = get_disease_knowledge(request.disease_id)

        if not data:
            raise HTTPException(
                status_code=404,
                detail=f"Disease not found: {request.disease_id}"
            )

        context_parts = []

        for item in data:
            context_parts.append(
                f"""
Disease: {item.get('disease')}
Target: {item.get('target')}
Target name: {item.get('target_name')}
Drugs: {item.get('drugs')}
Clinical trials: {len([
    x for x in item.get('clinical_trials', [])
    if x.get('id')
])}
"""
            )

        context = "\n".join(context_parts)

        sources = {
            "disease": request.disease_id,
            "target_count": len(data)
        }

    answer = generate_answer(
        request.question,
        context
    )

    return {
        "question": request.question,
        "answer": answer,
        "sources": sources
    }