import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from meeting_intelligence import (
    build_timestamped_transcript,
    extract_segment_reference_map,
    render_structured_meeting_markdown,
    validate_structured_meeting_result,
)


class MeetingIntelligenceTests(unittest.TestCase):
    def setUp(self):
        self.segments = [
            {"start": 12.4, "end": 18.7, "text": "Предлагаю перенести запуск.", "speaker_id": "spk-a"},
            {"start": 19.0, "end": 23.0, "text": "Согласен, переносим на пятницу.", "speaker_id": "spk-b"},
        ]
        self.source, self.roster = build_timestamped_transcript(
            self.segments, {"spk-a": "Анна", "spk-b": "Борис"}
        )

    def test_timestamped_source_contains_stable_segment_ids_and_roster(self):
        self.assertIn("[SEGMENT_ID=SEG_000001]", self.source)
        self.assertIn("[00:00:12–00:00:18]", self.source)
        self.assertIn("[SPEAKER_ID=spk-a]", self.source)
        self.assertEqual(self.roster, [
            {"speaker_id": "spk-a", "name": "Анна"},
            {"speaker_id": "spk-b", "name": "Борис"},
        ])

    def test_reference_map_extracts_real_source_timestamps(self):
        references = extract_segment_reference_map(self.source)
        self.assertEqual(references["SEG_000001"]["start"], 12)
        self.assertEqual(references["SEG_000002"]["speaker_id"], "spk-b")

    def test_validator_discards_unknown_segment_ids(self):
        raw = '{"summary":"Встреча","topics":[],"decisions":[{"text":"Перенести запуск","segment_ids":["SEG_000002","SEG_999999"]}],"action_items":[],"open_questions":[]}'
        data, warnings = validate_structured_meeting_result(raw, self.source)
        self.assertIsNotNone(data)
        self.assertEqual(data["decisions"][0]["segment_ids"], ["SEG_000002"])
        self.assertTrue(warnings)

    def test_structured_report_renders_timecode_evidence(self):
        raw = '{"summary":"Кратко","topics":[],"decisions":[{"text":"Перенести запуск на пятницу","segment_ids":["SEG_000002"]}],"action_items":[],"open_questions":[]}'
        data, warnings = validate_structured_meeting_result(raw, self.source)
        output = render_structured_meeting_markdown(data, self.source, warnings)
        self.assertIn("Принятые решения", output)
        self.assertIn("00:00:19–00:00:23", output)
        self.assertIn("SEG_000002", output)

    def test_unknown_responsible_speaker_id_is_not_presented_as_attributed(self):
        raw = (
            '{"summary":"Встреча","topics":[],"decisions":[],'
            '"action_items":[{"task":"Подготовить отчёт",'
            '"responsible_speaker_id":"spk-unknown","responsible_name":"Неизвестный",'
            '"segment_ids":["SEG_000001"]}],"open_questions":[]}'
        )
        data, warnings = validate_structured_meeting_result(raw, self.source)
        action = data["action_items"][0]
        self.assertEqual(action["responsible_speaker_id"], "")
        self.assertEqual(action["responsible_name"], "")
        self.assertTrue(any("ответственный" in warning.lower() for warning in warnings))

    def test_invalid_json_is_not_silently_accepted_as_structured_data(self):
        data, warnings = validate_structured_meeting_result("Это не JSON", self.source)
        self.assertIsNone(data)
        self.assertTrue(warnings)


if __name__ == "__main__":
    unittest.main()
