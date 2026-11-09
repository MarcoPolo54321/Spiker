"""Regression guards for the 3.0.7.4 UX fixes.

These source-level tests intentionally run without Qt, PortAudio or optional ML wheels.
Runtime Windows/GUI behavior remains covered by docs/TEST_PLAN_3.0.7.4.md.
"""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class QueueUxRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.queue = (ROOT / "scripts" / "Queue_page.py").read_text(encoding="utf-8")

    def test_queue_table_prioritizes_filename_and_status(self):
        self.assertIn("QTableWidget(0, 2)", self.queue)
        self.assertIn('["Файл", "Статус"]', self.queue)
        self.assertIn("setColumnWidth(1, 116)", self.queue)
        self.assertIn("media_splitter.setSizes([320, 680])", self.queue)

    def test_editor_and_progress_panels_are_user_resizable(self):
        self.assertIn('QSplitter(Qt.Orientation.Vertical, self.player_panel)', self.queue)
        self.assertIn('self.work_splitter.setSizes([120, 210])', self.queue)
        self.assertIn('self.media_splitter.setHandleWidth(8)', self.queue)

    def test_new_segments_are_appended_incrementally_without_rebuilding_document(self):
        start = self.queue.index("    def _on_segments_changed(self, segments):")
        end = self.queue.index("    @staticmethod\n    def _task_has_speakers", start)
        handler = self.queue[start:end]
        self.assertIn("def _on_segment_added(self, segment: dict):", handler)
        self.assertIn("cursor.insertText(prefix + rendered)", handler)
        self.assertNotIn("self._set_task_editor_text(task)", handler)
        self.assertIn("self._save_queue()", handler)
        self.assertIn("bar.setValue(old_scroll)", handler)

    def test_manual_speaker_tools_do_not_require_automatic_diarization(self):
        self.assertIn('has_segments and safe_for_manual_edit', self.queue)
        self.assertIn('if not segments:', self.queue)
        self.assertIn('Если pyannote не установлена или не определила голоса', self.queue)
        self.assertIn('speaker_id = f"SPEAKER_MANUAL_', self.queue)
        self.assertIn('QPushButton("Авто-спикеры")', self.queue)
        self.assertIn('def run_speaker_diarization(self):', self.queue)
        self.assertIn('Не запускает ИИ', self.queue)

    def test_force_cancel_is_explicit_and_preserves_original_media(self):
        self.assertIn('QPushButton("Прервать и сбросить")', self.queue)
        self.assertIn('Исходный файл останется на диске', self.queue)


class SettingsUxRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.settings = (ROOT / "scripts" / "UI" / "Settings_page.py").read_text(encoding="utf-8")

    def test_diagnostics_persist_recommended_settings(self):
        start = self.settings.index("    def run_diagnostics(self):")
        end = self.settings.index("    def _select_whispercpp_model_for_recommendation", start)
        method = self.settings[start:end]
        self.assertIn("self.save_preferences()", method)
        self.assertIn("параметры применены и сохранены", method)

    def test_ui_reports_actual_active_backends(self):
        self.assertIn("def _refresh_backend_status", self.settings)
        self.assertIn("Whisper.cpp (резерв Авто)", self.settings)
        self.assertIn("Sherpa/T-one", self.settings)
        self.assertIn("pyannote", self.settings)
        self.assertIn("CUDA / FP16 / batch для Whisper.cpp не используются", self.settings)

    def test_performance_presets_save_immediately(self):
        start = self.settings.index("    def _performance_preset_changed(")
        end = self.settings.index("    def refresh_models(", start)
        self.assertIn("self.save_preferences()", self.settings[start:end])

    def test_model_formats_are_explained_separately(self):
        for value in ("CTranslate2", "model.onnx", "tokens.txt", "Whisper.cpp", "ИИ-модель"):
            self.assertIn(value, self.settings)


class DictationUxRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.main = (ROOT / "scripts" / "main.py").read_text(encoding="utf-8")
        cls.dialog = (ROOT / "scripts" / "UI" / "Dictation_audio_menu_script.py").read_text(encoding="utf-8")

    def test_live_cancel_and_reset_controls_exist(self):
        self.assertIn('self.pushButton_cancel_dictation = QPushButton("Прервать")', self.dialog)
        self.assertIn('self.ui.pushButton_cancel_dictation.clicked.connect(self.abort_live_dictation)', self.main)
        self.assertIn('self.abort_live_dictation(clear_text=True)', self.main)

    def test_live_decoder_has_a_force_cancel_path(self):
        self.assertIn('def cancel(self):', self.main)
        self.assertIn('self.requestInterruption()', self.main)
        self.assertIn('self.cancelled.emit(self._committed_text)', self.main)
        self.assertIn('self.whisper_worker.finished.connect(self._on_live_worker_finished)', self.main)
        self.assertIn('self.audio_processor.finished.connect(self._on_live_capture_finished)', self.main)
        self.assertIn('def _maybe_finish_live_cancellation(self):', self.main)
        self.assertIn('if processor is not None and processor.isRunning():', self.main)
        self.assertIn('capture_running = self.audio_processor is not None and self.audio_processor.isRunning()', self.main)

    def test_live_output_explains_interim_text(self):
        self.assertIn("Текст появляется во время речи", self.dialog)
        self.assertIn("текущая фраза может уточняться", self.dialog)


class UserGuideRegressionTests(unittest.TestCase):
    def test_guide_is_embedded_in_the_main_navigation_with_practical_sections(self):
        guide = (ROOT / "scripts" / "UI" / "UserGuide.py").read_text(encoding="utf-8")
        main_menu = (ROOT / "scripts" / "UI" / "Main_menu_script.py").read_text(encoding="utf-8")
        main = (ROOT / "scripts" / "main.py").read_text(encoding="utf-8")
        self.assertIn('class UserGuidePage(QWidget)', guide)
        self.assertNotIn('Qt.WindowType.Window', guide)
        self.assertIn('QTabWidget', guide)
        self.assertIn('pushButton_user_guide', main_menu)
        self.assertIn('setAccessibleName("Обучение")', main_menu)
        self.assertIn('QIcon(str(ICON_ROOT / "training_button.png"))', main_menu)
        settings_pos = main_menu.index('utility_buttons.addWidget(self.pushButton_settings)')
        help_pos = main_menu.index('utility_buttons.addWidget(self.pushButton_about_prog)')
        training_pos = main_menu.index('utility_buttons.addWidget(self.pushButton_user_guide)')
        self.assertLess(settings_pos, help_pos)
        self.assertLess(help_pos, training_pos)
        self.assertIn('def open_user_guide(self):', main)
        self.assertIn('self.tabs.addTab(self.user_guide_page, "Обучение")', main)
        for topic in ("Диктовка", "Файлы и очередь", "Участники", "Модели и производительность", "ИИ, экспорт и приватность"):
            self.assertIn(topic, guide)

    def test_user_icons_are_two_separate_transparent_png_resources(self):
        icons = ROOT / "icons"
        for name in ("ai_processing.png", "training_button.png"):
            payload = (icons / name).read_bytes()
            self.assertEqual(payload[:8], b"\x89PNG\r\n\x1a\n")
            self.assertGreater(len(payload), 100_000)
        main_menu = (ROOT / "scripts" / "UI" / "Main_menu_script.py").read_text(encoding="utf-8")
        self.assertIn('ICON_ROOT / "ai_processing.png"', main_menu)
        self.assertIn('ICON_ROOT / "training_button.png"', main_menu)
        # The training control stays in the header, not as an additional home-screen card.
        self.assertEqual(main_menu.count('self.training_card ='), 0)

    def test_manual_test_plan_covers_user_reported_issues(self):
        plan = (ROOT / "docs" / "TEST_PLAN_3.0.7.4.md").read_text(encoding="utf-8")
        for topic in ("завершённая фраза", "сброс", "участников", "pyannote", "Обучение"):
            self.assertIn(topic, plan)


    def test_guide_content_uses_translucent_blue_panel_and_transparent_viewport(self):
        guide = (ROOT / "scripts" / "UI" / "UserGuide.py").read_text(encoding="utf-8")
        theme = (ROOT / "scripts" / "UI" / "theme.py").read_text(encoding="utf-8")
        self.assertIn('setObjectName("userGuideContentPanel")', guide)
        self.assertIn('browser.viewport().setAutoFillBackground(False)', guide)
        self.assertIn('browser.viewport().setStyleSheet("background: transparent; border: 0;")', guide)
        self.assertIn('QPalette.ColorRole.Base', guide)
        self.assertIn('QFrame#userGuideContentPanel', theme)
        self.assertIn('background: rgba(8, 38, 97, 168)', theme)
        self.assertIn('QWidget#userGuidePage, QWidget#userGuideTabPage { background: transparent; }', theme)
        self.assertNotIn('background: #333333', theme)

    def test_training_utility_button_uses_same_transparent_style_as_settings_and_help(self):
        theme = (ROOT / "scripts" / "UI" / "theme.py").read_text(encoding="utf-8")
        for state in ("", ":hover", ":pressed"):
            selector = (
                "QPushButton#pushButton_settings" + state + ",\n"
                "QPushButton#pushButton_about_prog" + state + ",\n"
                "QPushButton#pushButton_user_guide" + state + " {"
            )
            self.assertIn(selector, theme)
        # The original user-supplied PNG remains intact and carries real alpha transparency.
        from PIL import Image
        icon_path = ROOT / "icons" / "training_button.png"
        with Image.open(icon_path) as icon:
            self.assertEqual(icon.mode, "RGBA")
            alpha = icon.getchannel("A")
            self.assertEqual(alpha.getextrema()[0], 0)
        self.assertIn('setIcon(QIcon(str(ICON_ROOT / "training_button.png")))',
                      (ROOT / "scripts" / "UI" / "Main_menu_script.py").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
