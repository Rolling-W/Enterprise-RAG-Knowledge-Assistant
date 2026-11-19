import unittest
from unittest.mock import MagicMock, patch

from backend.services import answer_generation_service


class AnswerGenerationServiceTests(unittest.TestCase):
    def setUp(self):
        self.question = "How many annual leave days do employees receive?"
        self.context = "Employees receive 23 days of annual leave."

    @patch.dict(
        "os.environ",
        {
            "LLM_MODE": "auto",
            "LLM_LOCAL_ENABLED": "true",
            "OLLAMA_BASE_URL": "http://ollama:11434/v1",
            "OLLAMA_MODEL": "qwen2.5:7b-instruct-q4_K_M",
            "OPENAI_API_KEY": "cloud-key",
            "OPENAI_MODEL": "gpt-4.1-mini",
        },
        clear=True,
    )
    @patch("backend.services.answer_generation_service.OpenAI")
    def test_local_answer_is_preferred(self, openai_class):
        local_response = MagicMock()
        local_response.choices = [MagicMock()]
        local_response.choices[0].message.content = "Employees receive 23 days."

        local_client = MagicMock()
        local_client.chat.completions.create.return_value = local_response
        openai_class.return_value = local_client

        answer = answer_generation_service.generate_answer(
            question=self.question,
            context=self.context,
        )

        self.assertEqual(answer, "Employees receive 23 days.")
        openai_class.assert_called_once_with(
            api_key="ollama",
            base_url="http://ollama:11434/v1",
            timeout=30.0,
        )

    @patch.dict(
        "os.environ",
        {
            "LLM_MODE": "auto",
            "LLM_LOCAL_ENABLED": "false",
            "OPENAI_API_KEY": "cloud-key",
            "OPENAI_MODEL": "gpt-4.1-mini",
        },
        clear=True,
    )
    @patch("backend.services.answer_generation_service.OpenAI")
    def test_cloud_is_used_when_gpu_local_llm_is_disabled(self, openai_class):
        cloud_response = MagicMock()
        cloud_response.choices = [MagicMock()]
        cloud_response.choices[0].message.content = "Employees receive 23 days."

        cloud_client = MagicMock()
        cloud_client.chat.completions.create.return_value = cloud_response
        openai_class.return_value = cloud_client

        answer = answer_generation_service.generate_answer(
            question=self.question,
            context=self.context,
        )

        self.assertEqual(answer, "Employees receive 23 days.")
        openai_class.assert_called_once_with(
            api_key="cloud-key",
            timeout=30.0,
        )

    @patch.dict(
        "os.environ",
        {"LLM_MODE": "cloud", "LLM_CLOUD_FALLBACK": "false"},
        clear=True,
    )
    def test_error_is_clear_when_no_cloud_api_key_is_configured(self):
        with self.assertRaisesRegex(RuntimeError, "OPENAI_API_KEY"):
            answer_generation_service.generate_answer(
                question=self.question,
                context=self.context,
            )

    @patch.dict(
        "os.environ",
        {
            "LLM_MODE": "auto",
            "LLM_LOCAL_ENABLED": "true",
            "LLM_CLOUD_FALLBACK": "true",
            "OLLAMA_BASE_URL": "http://ollama:11434/v1",
            "OLLAMA_MODEL": "qwen2.5:7b-instruct-q4_K_M",
            "OPENAI_API_KEY": "cloud-key",
            "OPENAI_MODEL": "gpt-4.1-mini",
        },
        clear=True,
    )
    @patch("backend.services.answer_generation_service.OpenAI")
    def test_cloud_is_used_when_local_llm_fails(self, openai_class):
        local_client = MagicMock()
        local_client.chat.completions.create.side_effect = RuntimeError(
            "Ollama unavailable"
        )

        cloud_response = MagicMock()
        cloud_response.choices = [MagicMock()]
        cloud_response.choices[0].message.content = "Employees receive 23 days."
        cloud_client = MagicMock()
        cloud_client.chat.completions.create.return_value = cloud_response
        openai_class.side_effect = [local_client, cloud_client]

        answer = answer_generation_service.generate_answer(
            question=self.question,
            context=self.context,
        )

        self.assertEqual(answer, "Employees receive 23 days.")
        self.assertEqual(openai_class.call_count, 2)


if __name__ == "__main__":
    unittest.main()
