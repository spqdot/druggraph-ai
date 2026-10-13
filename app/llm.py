import os

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY")
)


def generate_answer(question: str, context: str) -> str:
    prompt = f"""
You are a biomedical knowledge assistant.

Use the Cosmos DB knowledge graph context for questions about the selected
disease, its targets, drugs, clinical trials, and their relationships. State
only relationships and availability that the context explicitly contains.
If the requested graph information is absent, clearly say that it is not
available in the current graph. Do not invent facts.

For general educational questions, such as what a biological target, protein,
or clinical trial is, or how diseases, targets, and drugs are generally
related, you may use general biomedical knowledge. Begin those answers with:
"General educational explanation (not retrieved from Cosmos DB):"
Do not claim general explanations were retrieved from the graph.

Cosmos DB knowledge graph context:
{context}

User question:
{question}
"""

    response = client.responses.create(
        model="gpt-6-luna",
        input=prompt
    )

    return response.output_text