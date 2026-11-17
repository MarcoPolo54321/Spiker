import json
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from ai_provider import process_transcript
from interview_report import process_interview


class InterviewWorkflowTests(unittest.TestCase):
    def test_clear_dialogue_evidence_prevents_swapped_names_and_roles(self):
        source = (
            "[SEGMENT_ID=SEG_1] [00:00:00–00:00:04] [SPEAKER_ID=a] Меня зовут Мария Власова. Расскажите немного о себе.\n"
            "[SEGMENT_ID=SEG_2] [00:00:04–00:00:08] [SPEAKER_ID=b] Меня зовут Алексей Миронов. Я три года работаю разработчиком.\n"
            "[SEGMENT_ID=SEG_3] [00:00:08–00:00:12] [SPEAKER_ID=b] Как ваша команда проверяет качество кода?"
        )
        proposal = {"turns": [[1, "К", 1, "Меня зовут Мария Власова. Расскажите немного о себе."],
                              [2, "И", 6, "Меня зовут Алексей Миронов. Я три года работаю разработчиком."],
                              [3, "И", 7, "Как ваша команда проверяет качество кода?"]],
                    "names": {"К": [1, "Мария Власова"]}}
        result = process_interview(source, {}, [], lambda _: json.dumps(proposal), None, None)
        self.assertTrue(result.startswith("# Беседа с кандидатом: Алексей Миронов"))
        self.assertIn("**И** [00:00:00]", result)
        self.assertIn("**К** [00:00:08]", result)
        self.assertIn("## Вопросы кандидата", result)
        self.assertNotIn("Дальнейшие шаги", result)

    def test_known_names_sections_roles_and_corrections(self):
        source = (
            "[SEGMENT_ID=SEG_1] [00:00:01–00:00:05] [SPEAKER_ID=a] С каким стеком вы работали\n"
            "[SEGMENT_ID=SEG_2] [00:00:05–00:00:09] [SPEAKER_ID=b] Я работал с Постгресом и писал тесты\n"
            "[SEGMENT_ID=SEG_3] [00:00:09–00:00:13] [SPEAKER_ID=b] Как у вас проходит ревью?"
        )
        reply = {"turns": [[1, "К", 3, "С каким стеком вы работали?"],
                           [2, "К", 3, "Я работал с Постгресом и писал тесты."],
                           [3, "И", 6, "Как у вас проходит ревью?"]]}
        roster = [{"speaker_id": "a", "name": "Мария"}, {"speaker_id": "b", "name": "Алексей"}]
        with patch("ai_provider.chat_completion", return_value=json.dumps(reply, ensure_ascii=False)) as request:
            report = process_transcript("builtin", "", "qwen", "", "interview", source,
                                        speaker_context=roster,
                                        interview_names={"interviewer": "Мария", "candidate": "Алексей"})
        self.assertTrue(report.startswith("# Беседа с кандидатом: Алексей"))
        self.assertIn("## Навыки и инструменты", report)
        self.assertIn("**И** [00:00:01]: С каким стеком вы работали?", report)
        self.assertIn("**К** [00:00:09]: Как у вас проходит ревью?", report)
        self.assertIn("## Вопросы кандидата", report)
        self.assertEqual(request.call_args.args[3][0]["role"], "system")

    def test_missing_rows_and_changed_fact_are_kept_verbatim(self):
        def reply(_messages):
            return json.dumps({"turns": [[1, "К", 2, "Я работал над сервисом 5 лет."],
                                          [999, "И", 1, "Фрагмент, которого нет."]],
                               "names": {"К": [1, "Пётр"]}}, ensure_ascii=False)

        report = process_interview("Я не работал над сервисом 3 года.\nВстреча началась вчера.",
                                   {}, [], reply, None, None)
        self.assertIn("Я не работал над сервисом 3 года.", report)
        self.assertIn("Встреча началась вчера.", report)
        self.assertNotIn("5 лет", report)
        self.assertNotIn("Пётр", report)
        self.assertNotIn("которого нет", report)
        self.assertIn("Реплик с неопределённой ролью: 2", report)

    def test_split_an_unlabelled_line_and_ground_a_name_in_introduction(self):
        source = "С кем мы беседуем? Меня зовут Анна Орлова."
        reply = {"turns": [[1, "И", 1, "С кем мы беседуем?"], [1, "К", 1, "Меня зовут Анна Орлова."]],
                 "names": {"К": [1, "Анна Орлова"]}}
        report = process_interview(source, {}, [], lambda _: json.dumps(reply), None, None)
        self.assertIn("**И**: С кем мы беседуем?", report)
        self.assertIn("**К**: Меня зовут Анна Орлова.", report)
        report2 = process_interview("Меня зовут Анна Орлова.", {}, [], lambda _: json.dumps(
            {"turns": [[1, "К", 1, "Меня зовут Анна Орлова."]], "names": {"К": [1, "Анна Орлова"]}}), None, None)
        self.assertTrue(report2.startswith("# Беседа с кандидатом: Анна Орлова"))

    def test_long_transcript_is_batched_and_missing_content_is_not_summarized_away(self):
        attempts = []
        source = "\n".join(f"Реплика номер {i}. Это проверяемый фрагмент разговора." for i in range(1, 64))
        def reply(messages):
            attempts.append(messages)
            self.assertLess(len(messages[1]["content"]), 1900)
            return "невалидный JSON"
        report = process_interview(source, {}, [], reply, None, None)
        self.assertGreater(len(attempts), 1)
        self.assertEqual(report.count("Это проверяемый фрагмент разговора."), 63)


class DefaultMicrophoneTests(unittest.TestCase):
    def test_windows_float_mix_format_preserves_pcm_amplitude_and_silence(self):
        import struct
        from PySide6.QtMultimedia import QAudioFormat
        from transcription.qt_microphone import _as_pcm16
        data = struct.pack("<6f", 0, .5, -.5, 1.2, -1.2, float("nan"))
        converted = _as_pcm16(data, QAudioFormat.SampleFormat.Float)
        self.assertEqual(struct.unpack("<6h", converted), (0, 16384, -16384, 32767, -32768, 0))

    def test_picker_shows_real_input_endpoints_and_keeps_headset_selectable(self):
        from transcription.microphone import input_devices
        audio = Mock()
        audio.get_host_api_info_by_type.return_value = {"index": 2, "defaultInputDevice": 9, "deviceCount": 4}
        mic = {"index": 9, "name": "Микрофон", "maxInputChannels": 1}
        headset = {"index": 10, "name": "Гарнитура", "maxInputChannels": 1}
        audio.get_device_info_by_index.return_value = mic
        audio.get_device_info_by_host_api_device_index.side_effect = [
            mic, {"name": "Динамики", "maxInputChannels": 0}, headset,
            {"name": "МИКРОФОН", "maxInputChannels": 1},
        ]
        catalog = input_devices(audio)
        self.assertEqual([key for key, _, _ in catalog], ["", "Микрофон", "Гарнитура"])
        self.assertEqual(catalog[-1][2]["index"], 10)
        audio.get_default_input_device_info.assert_not_called()

    def test_only_default_wasapi_endpoint_is_tried(self):
        from transcription.microphone import default_input_device, open_capture
        audio = Mock()
        audio.get_host_api_info_by_type.return_value = {"defaultInputDevice": 9}
        audio.get_device_info_by_index.return_value = {
            "index": 9, "maxInputChannels": 2, "defaultSampleRate": 44100, "name": "Default input",
        }
        device = default_input_device(audio)
        audio.open.side_effect = [OSError("mono unsupported"), Mock()]
        capture = open_capture(audio, device)
        self.assertEqual(capture._rate, 44100)
        self.assertEqual(capture._channels, 2)
        self.assertEqual(audio.open.call_args_list[0].kwargs["rate"], 44100)
        self.assertTrue(all(call.kwargs["input_device_index"] == 9 for call in audio.open.call_args_list))
        audio.get_default_input_device_info.assert_not_called()
        audio.get_device_count.assert_not_called()

    def test_stereo_resampling_never_cancels_opposite_phase_and_detects_eof(self):
        import struct
        from transcription.microphone import ResampledCapture
        stream = Mock()
        stream.read.side_effect = [struct.pack("<hh", 650, -650) * 1600, b""]
        wrapped = ResampledCapture(stream, 16000, 2)
        self.assertEqual(wrapped.read(1600), struct.pack("<h", 650) * 1600)
        self.assertEqual(wrapped.read(1600), b"")

    def test_auto_decoder_replays_initial_audio_when_the_primary_is_silent(self):
        import struct
        from transcription.live_streaming import AutoDictationSession
        primary = Mock()
        primary.feed_pcm16.return_value = ("", False)
        backup = Mock()
        backup.feed_pcm16.return_value = ("первая фраза", False)
        notifications = []
        engine = AutoDictationSession(lambda: primary, lambda: backup, notifications.append)
        for _ in range(40):
            result = engine.feed_pcm16(struct.pack("<h", 650) * 1600)
        self.assertEqual(result[0], "первая фраза")
        self.assertEqual(backup.feed_pcm16.call_count, 40)
        self.assertEqual(len(notifications), 1)

    def test_missing_default_does_not_choose_unrelated_input(self):
        from transcription.microphone import default_input_device
        audio = Mock()
        audio.get_host_api_info_by_type.return_value = {"defaultInputDevice": -1}
        with self.assertRaisesRegex(OSError, "по умолчанию"):
            default_input_device(audio)
        audio.get_device_info_by_index.assert_not_called()
        audio.get_default_input_device_info.assert_not_called()
