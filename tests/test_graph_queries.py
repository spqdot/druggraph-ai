import unittest
from unittest.mock import MagicMock, patch

from gremlin_python.driver.protocol import GremlinServerError

from app.graph_queries import _submit


def server_error(status_code):
    return GremlinServerError(
        {
            "code": status_code,
            "message": "test error",
            "attributes": {},
        }
    )


class SubmitTests(unittest.TestCase):
    @patch("app.graph_queries.time.sleep")
    def test_retries_retryable_gremlin_error(self, mock_sleep):
        client = MagicMock()
        response = client.submit.return_value
        response.all.return_value.result.side_effect = [
            server_error(429),
            ["result"],
        ]

        result = _submit(client, "g.V().count()")

        self.assertEqual(result, ["result"])
        self.assertEqual(client.submit.call_count, 2)
        mock_sleep.assert_called_once_with(0.25)

    @patch("app.graph_queries.time.sleep")
    def test_does_not_retry_non_retryable_gremlin_error(self, mock_sleep):
        client = MagicMock()
        response = client.submit.return_value
        response.all.return_value.result.side_effect = server_error(400)

        with self.assertRaises(GremlinServerError):
            _submit(client, "invalid")

        self.assertEqual(client.submit.call_count, 1)
        mock_sleep.assert_not_called()


if __name__ == "__main__":
    unittest.main()
