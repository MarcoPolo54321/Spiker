from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))


class DictionPreparationTests(unittest.TestCase):
    def test_long_lecture_is_processed_in_order_and_reports_all_sections(self):
        import json
        from speech_synthesis import DICTION_SECTION_SIZE, prepare_diction
        source = "Спикер 1: " + " ".join(f"Раздел {i}: договор." for i in range(920))
        calls, progress = [], []
        def echo(*args, **kwargs):
            fragment = args[3][-1]["content"]
            calls.append(fragment)
            self.assertLessEqual(len(fragment), DICTION_SECTION_SIZE)
            return json.dumps({"text": fragment.replace("договор", "догово́р")})
        with patch("ai_provider.chat_completion", side_effect=echo):
            output = prepare_diction(source, "test.gguf", lambda: False, lambda *p: progress.append(p))
        self.assertGreater(len(source), 12000)
        self.assertGreater(len(calls), 10)
        self.assertEqual(output, source.replace("договор", "догово́р"))
        self.assertEqual(progress[-1], (len(calls), len(calls)))

    def test_contextual_stress_is_kept_without_changing_the_script(self):
        from speech_synthesis import prepare_diction, speech_phrases
        with patch("ai_provider.chat_completion", return_value='{"text":"Открыли замо́к. Увидели за́мок!"}') as completion:
            output = prepare_diction("Открыли замок увидели замок", "", lambda: False)
        self.assertTrue(completion.call_args.kwargs["json_mode"])
        self.assertEqual(output, "Открыли замо́к. Увидели за́мок!")
        phrases = list(speech_phrases(output))
        self.assertEqual([x[0] for x in phrases], ["Открыли замо́к.", "Увидели за́мок!"])
        self.assertGreater(phrases[-1][1], phrases[0][1])

    def test_protects_words_and_speaker_labels_from_rewriting(self):
        from speech_synthesis import prepare_diction
        def reply(provider, _url, _model, messages, **_):
            self.assertEqual(provider, "builtin")
            if "спросил" in messages[-1]["content"]:
                return "Я спросил: А где ёлка?"
            return "Совсем другой вывод."
        with patch("ai_provider.chat_completion", side_effect=reply):
            source = "Спикер 1: Я спросил а где елка\nСпикер 2: Она в парке"
            self.assertEqual(prepare_diction(source, "", lambda: False),
                             "Спикер 1: Я спросил: А где ёлка?\nСпикер 2: Она в парке")
