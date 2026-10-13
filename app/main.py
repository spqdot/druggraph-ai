import logging

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, field_validator

from app.context_builder import build_disease_context, build_drug_context
from app.graph_queries import (
    get_disease_knowledge,
    get_drug_knowledge,
    get_graph_data,
    get_diseases,
)
from app.llm import generate_answer


logger = logging.getLogger(__name__)


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
        "http://localhost:5175",
        "http://127.0.0.1:5175",
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


@app.get("/api/diseases")
def diseases():
    return {"diseases": get_diseases()}


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

    @field_validator("question")
    @classmethod
    def validate_question(cls, value: str) -> str:
        question = value.strip()
        if not question:
            raise ValueError("Question must not be empty.")
        return question


@app.post("/api/ask")
def ask_knowledge_graph(request: AskRequest):
    try:
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
                "clinical_trial_count": len(trial_ids),
            }

        else:
            data = get_disease_knowledge(request.disease_id)

            if not data:
                raise HTTPException(
                    status_code=404,
                    detail=f"Disease not found: {request.disease_id}"
                )

            context = build_disease_context(data)
            drug_ids = {
                drug.get("id")
                for item in data
                for drug in item.get("drugs", [])
                if drug.get("id")
            }
            trial_ids = {
                trial.get("id")
                for item in data
                for trial in item.get("clinical_trials", [])
                if trial.get("id")
            }
            sources = {
                "disease": data[0].get("disease"),
                "disease_id": request.disease_id,
                "target_count": len(data),
                "drug_count": len(drug_ids),
                "clinical_trial_count": len(trial_ids),
            }
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception(
            "Knowledge graph retrieval failed for disease_id=%s",
            request.disease_id,
        )
        raise HTTPException(
            status_code=503,
            detail="Knowledge graph retrieval is temporarily unavailable.",
        ) from exc

    logger.info(
        "RAG request disease_id=%s targets=%s drugs=%s trials=%s context_chars=%s",
        request.disease_id,
        sources.get("target_count", len(sources.get("target", []))),
        sources.get("drug_count", 1 if request.drug_name else 0),
        sources["clinical_trial_count"],
        len(context),
    )
    try:
        answer = generate_answer(request.question, context)
    except Exception as exc:
        logger.exception(
            "LLM answer generation failed for disease_id=%s",
            request.disease_id,
        )
        raise HTTPException(
            status_code=502,
            detail="Answer generation is temporarily unavailable.",
        ) from exc

    return {
        "question": request.question,
        "answer": answer,
        "sources": sources
    }