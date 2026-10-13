import unittest
from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.context_builder import build_disease_context
from app.llm import generate_answer
from app.main import app


PARKINSON_DATA = [
    {
        "disease_id": "MONDO_0005180",
        "disease": "Parkinson disease",
        "target_id": "ENSG00000145335",
        "target": "SNCA",
        "target_name": "synuclein alpha",
        "drugs": [
            {
                "id": "CHEMBL4298077",
                "name": "PRASINEZUMAB",
                "type": "antibody",
                "maximum_stage": "Phase 3",
            }
        ],
        "clinical_trials": [],
    },
    {
        "disease_id": "MONDO_0005180",
        "disease": "Parkinson disease",
        "target_id": "ENSG00000188906",
        "target": "LRRK2",
        "target_name": "leucine rich repeat kinase 2",
        "drugs": [],
        "clinical_trials": [],
    },
]


class RagEndpointTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.data_patch = patch(
            "app.main.get_disease_knowledge",
            return_value=PARKINSON_DATA,
        )
        self.mock_data = self.data_patch.start()
        self.addCleanup(self.data_patch.stop)

    def ask(self, question):
        return self.client.post(
            "/api/ask",
            json={"question": question, "disease_id": "MONDO_0005180"},
        )

    @patch("app.main.generate_answer")
    def test_general_educational_question_uses_disease_scoped_context(
        self, mock_answer
    ):
        mock_answer.return_value = (
            "General educational explanation (not retrieved from Cosmos DB): "
            "A biological target is a molecule affected by a therapy."
        )

        response = self.ask("What is a biological target?")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["answer"].startswith("General educational"))
        context = mock_answer.call_args.args[1]
        self.assertIn("Selected disease: Parkinson disease", context)
        self.assertIn("SNCA --TARGETED_BY--> PRASINEZUMAB", context)

    @patch("app.main.generate_answer", return_value="SNCA and LRRK2 are associated.")
    def test_disease_target_question(self, _mock_answer):
        response = self.ask("Which biological targets are associated with this disease?")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["sources"]["target_count"], 2)
        self.assertEqual(response.json()["sources"]["disease"], "Parkinson disease")

    @patch("app.main.generate_answer", return_value="PRASINEZUMAB targets SNCA.")
    def test_drug_question_with_known_relationship(self, _mock_answer):
        response = self.ask("Which drugs are linked to this disease?")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["sources"]["drug_count"], 1)

    @patch(
        "app.main.generate_answer",
        return_value="No clinical trials are currently linked in the graph.",
    )
    def test_unavailable_clinical_trials_are_present_in_context(self, mock_answer):
        response = self.ask("What clinical trial information is available?")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["sources"]["clinical_trial_count"], 0)
        self.assertIn(
            "No clinical trials are currently linked",
            mock_answer.call_args.args[1],
        )

    def test_empty_question_is_rejected(self):
        response = self.ask("   ")

        self.assertEqual(response.status_code, 422)
        self.assertIn("Question must not be empty", response.text)

    @patch("app.main.get_disease_knowledge", side_effect=RuntimeError("offline"))
    def test_graph_retrieval_failure_is_explicit(self, _mock_data):
        response = self.ask("Which targets are associated?")

        self.assertEqual(response.status_code, 503)
        self.assertEqual(
            response.json()["detail"],
            "Knowledge graph retrieval is temporarily unavailable.",
        )

    @patch("app.main.generate_answer", side_effect=RuntimeError("LLM unavailable"))
    def test_llm_failure_is_explicit(self, _mock_answer):
        response = self.ask("Which targets are associated?")

        self.assertEqual(response.status_code, 502)
        self.assertEqual(
            response.json()["detail"],
            "Answer generation is temporarily unavailable.",
        )


class RagPromptTests(unittest.TestCase):
    def test_context_represents_target_drug_relationship_and_missing_trials(self):
        context = build_disease_context(PARKINSON_DATA)

        self.assertIn(
            "Parkinson disease --ASSOCIATED_WITH--> SNCA",
            context,
        )
        self.assertIn("SNCA --TARGETED_BY--> PRASINEZUMAB", context)
        self.assertIn("No clinical trials are currently linked", context)

    @patch("app.llm.client.responses.create")
    def test_general_education_prompt_requires_explicit_provenance(self, mock_create):
        mock_create.return_value = SimpleNamespace(output_text="example")

        generate_answer("What is a biological target?", "Selected disease: Parkinson disease")

        prompt = mock_create.call_args.kwargs["input"]
        self.assertIn(
            "General educational explanation (not retrieved from Cosmos DB):",
            prompt,
        )
        self.assertIn("Do not claim general explanations were retrieved from the graph", prompt)


if __name__ == "__main__":
    unittest.main()
