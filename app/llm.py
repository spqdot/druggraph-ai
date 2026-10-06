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

Answer the user's question using ONLY the knowledge graph context provided below.

If the context does not contain enough information to answer the question, say:
"I don't have enough information in the knowledge graph to answer that."

Do not invent facts.

Knowledge graph context:
{context}

User question:
{question}
"""

    response = client.responses.create(
        model="gpt-6-luna",
        input=prompt
    )

    return response.output_text