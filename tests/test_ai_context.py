import unittest
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import ai_provider


class BuiltinContextBudgetTests(unittest.TestCase):
    def test_long_transcript_is_chunked_for_builtin_4096_context(self):
        transcript = ("[SEGMENT_ID=SEG_000001] [00:00:00–00:00:03] [SPEAKER_ID=Спикер 1] "
                      "Это длинная русская расшифровка с временными метками.\n") * 900
        requests = []

        def reply(provider, base_url, model, messages, **kwargs):
            requests.append((messages, kwargs))
            return "Краткое резюме фрагмента."

        with patch.object(ai_provider, "chat_completion", side_effect=reply):
            result = ai_provider.process_transcript(
                "builtin", "", "GigaChat", "", "summary", transcript
            )

        self.assertTrue(result)
        self.assertGreater(len(requests), 1)
        source_calls = [messages[1]["content"] for messages, _ in requests
                        if "--- ФРАГМЕНТ ---" in messages[1]["content"]]
        self.assertTrue(source_calls)
        self.assertTrue(all(len(prompt) <= ai_provider.BUILTIN_CONTEXT_CHAR_BUDGET
                            for prompt in source_calls))
        self.assertTrue(all(kwargs["max_tokens"] == ai_provider.BUILTIN_MAX_OUTPUT_TOKENS
                            for _, kwargs in requests))

    def test_other_providers_keep_existing_chunk_and_output_limits(self):
        transcript = "Пример. " * 5000
        requests = []

        def reply(provider, base_url, model, messages, **kwargs):
            requests.append(kwargs)
            return "Краткое резюме фрагмента."

        with patch.object(ai_provider, "chat_completion", side_effect=reply):
            ai_provider.process_transcript("api", "https://example.test", "model", "key",
                                           "summary", transcript)

        self.assertGreater(len(requests), 1)
        self.assertTrue(all(call["max_tokens"] == 4096 for call in requests))


if __name__ == "__main__":
    unittest.main()
