# -*- coding: utf-8 -*-
"""Practical in-app user guide for Spiker."""
from __future__ import annotations

from PySide6.QtCore import Qt, QEvent, QTimer
from PySide6.QtWidgets import QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QPushButton, QWidget, QFrame, QScrollArea, QStackedWidget

from app_paths import get_app_root
from UI.Main_menu_script import LiquidGlassCard, IconGlass
from UI.theme import apply_window_theme

GUIDE_VIDEOS = {
    'Начало работы': (('Первые шаги', 'start.mp4'),),
    'Диктовка': (('Проверка микрофона', 'dictation.mp4'),),
    'Файлы и участники': (('Распознавание и плеер', 'queue.mp4'), ('Имена и правка реплик', 'speakers.mp4')),
    'Обработка ИИ': (('Отчёт о беседе', 'ai.mp4'),),
    'Озвучка': (('Подготовка дикции и экспорт', 'speech.mp4'),),
    'Модели': (('Проверка компьютера', 'models.mp4'),),
}

GUIDE_PAGES = [
    ('Начало работы',
     '<h2>Какой раздел открыть</h2><ol><li>Микрофон — записать свою речь. Файлы — расшифровать готовое аудио или видео.</li><li>ИИ — сделать краткое содержание, протокол или отчёт о беседе. Озвучка — получить WAV или MP3 из текста.</li><li>Если модель не найдена, откройте Настройки → Папка моделей и проверьте, что архивы из комплекта обработал установщик.</li></ol>'),
    ('Диктовка',
     '<h2>Запись не начинается или прерывается</h2><ol><li>Оставьте «По умолчанию в Windows» или выберите конкретный вход. После подключения гарнитуры обновите список кнопкой «Обновить».</li><li>Дождитесь надписи «Микрофон подключён. Теперь говорите». В режиме «Авто» СПИКЕР попробует Vosk, если T-one слышит сигнал, но не выдаёт текст. Если шкала молчит, откройте «Параметры Windows → Система → Звук → Ввод» и проверьте вход и доступ к микрофону.</li><li>При обрыве проверьте сообщение над текстом, выберите доступный микрофон и запустите снова. Уже распознанный текст можно сохранить или передать в ИИ.</li></ol>'),
    ('Файлы и участники',
     '<h2>Расшифровать запись и проверить, кто говорил</h2><ol><li>Добавьте записи, выберите модель для каждого файла или включите «Одна модель для всей очереди». Нажмите кнопку запуска очереди. Следующие файлы стартуют по одному, даже если вы открыли другой раздел.</li><li>Звуковая волна открыта сразу. В плеере ▶ запускает запись, ■ останавливает, соседние кнопки перематывают. В настройках плеера можно изменить громкость, скорость и шаг.</li><li>Для новых задач установлены два участника. Если говорили один или трое, выставьте число и нажмите «Авто-спикеры». В «Участниках» переименуйте профиль сразу во всех репликах и исправьте спорные места.</li><li>Откройте «Экспорт», чтобы сохранить результат в обычный файл. Проверьте имена и сложные фрагменты на слух.</li></ol>'),
    ('Обработка ИИ',
     '<h2>Превратить расшифровку в документ</h2><ol><li>Откройте TXT или передайте текст из «Диктовки» или очереди. Тайм-коды и метки спикеров можно добавить отдельно: по умолчанию передаётся только текст.</li><li>Выберите краткое содержание, протокол, отчёт «Беседа с кандидатом» или свою задачу. Встроенные GigaChat и Qwen работают на компьютере; внешний провайдер может получить текст по сети.</li><li>Для отчёта о беседе проверьте роли, имена, цитаты и смысл исправлений. ИИ может ошибаться; исходник не изменяется.</li></ol>'),
    ('Озвучка',
     '<h2>Озвучить текст с паузами и ударениями</h2><ol><li>Вставьте текст или откройте TXT/DOCX. Выберите Ирину или Руслана, настройте темп. В диалоге назначьте голоса в «Участниках» очереди.</li><li>Выберите Qwen или GigaChat и нажмите «Подготовить дикцию». Длинный текст делится на фрагменты автоматически и снова собирается в один текст. При озвучке получится один файл. Проверьте предпросмотр; вручную можно написать «за́мок» или «замо́к».</li><li>Прослушайте фрагмент, прежде чем сохранять WAV или MP3. Синтез может ошибаться в фамилиях и омографах.</li></ol>'),
    ('Модели',
     '<h2>Выбрать точность распознавания</h2><ol><li>Для файлов: Small — быстрее; Medium — баланс; Large-v3 — для сложных записей. Если не знаете, что выбрать, запустите диагностику ПК. Ссылки и пути для моделей CTranslate2, Whisper.cpp и GGUF находятся в «Настройки → Где скачать модели».</li><li>Для диктовки оставьте «Авто»: T-one выводит текст в потоке, Vosk служит запасным потоковым движком, Whisper обрабатывает короткими окнами.</li></ol>'),
]

GUIDE_ICONS = (
    "guide-start.png", "guide-dictation.png", "guide-files.png",
    "guide-ai.png", "guide-speech.png", "guide-models.png",
)


class UserGuidePage(QWidget):
    """Tutorials use a dedicated player screen and return to the same card list."""
    def __init__(self, main_window=None, parent=None):
        super().__init__(parent)
        self.main_window = main_window
        self.setObjectName("userGuidePage")
        apply_window_theme(self)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.pages = QStackedWidget()
        layout.addWidget(self.pages)
        self.cover = QWidget()
        self.pages.addWidget(self.cover)
        self._video_window_state = None
        root = QVBoxLayout(self.cover)
        root.setContentsMargins(24, 18, 24, 20)
        header = QHBoxLayout()
        back = QPushButton("← На главный экран")
        back.setProperty("role", "back")
        back.clicked.connect(self.back_to_home)
        header.addWidget(back, 0, Qt.AlignmentFlag.AlignTop)
        titles = QVBoxLayout()
        heading = QLabel("Обучение")
        heading.setObjectName("dialogTitle")
        titles.addWidget(heading)
        intro = QLabel("Короткие инструкции на одной странице. Нажмите кнопку в карточке, чтобы посмотреть видео.")
        intro.setWordWrap(True)
        intro.setObjectName("mutedLabel")
        titles.addWidget(intro)
        header.addLayout(titles, 1)
        root.addLayout(header)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.viewport().setStyleSheet("background: transparent;")
        self.card_body = QWidget()
        self.card_body.setObjectName("guideCards")
        self.card_grid = QGridLayout(self.card_body)
        self.card_grid.setContentsMargins(2, 8, 7, 13)
        self.card_grid.setSpacing(13)
        self.scroll.setWidget(self.card_body)
        root.addWidget(self.scroll, 1)
        self.cards = []
        self.player_panel = None
        self.active_card = None
        self._columns = 0
        for i, ((title, html), icon) in enumerate(zip(GUIDE_PAGES, GUIDE_ICONS), 1):
            card = LiquidGlassCard(self.card_body)
            body = QVBoxLayout(card)
            body.setContentsMargins(17, 12, 17, 18)
            body.setSpacing(8)
            lead = QHBoxLayout()
            artwork = IconGlass(get_app_root() / "icons" / icon)
            artwork.set_responsive_width(88)
            lead.addWidget(artwork, 0, Qt.AlignmentFlag.AlignVCenter)
            heading = QVBoxLayout()
            eyebrow = QLabel(f"{i:02d}  /  СПИКЕР")
            eyebrow.setObjectName("sectionLabel")
            heading.addWidget(eyebrow)
            label = QLabel(title)
            label.setObjectName("compactCardTitle")
            label.setWordWrap(True)
            heading.addWidget(label)
            lead.addLayout(heading, 1)
            body.addLayout(lead)
            text = QLabel()
            text.setObjectName("guideInstruction")
            text.setTextFormat(Qt.TextFormat.RichText)
            text.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            text.setWordWrap(True)
            subhead = html.replace("<h2>", '<p style="font-weight:600; margin: 2px 0;">').replace("</h2>", "</p>")
            text.setText(subhead)
            body.addWidget(text)
            body.addStretch(1)
            actions = QGridLayout()
            actions.setSpacing(7)
            for j, (clip, filename) in enumerate(GUIDE_VIDEOS[title]):
                watch = QPushButton(f"Видео: {clip}")
                watch.setProperty("role", "primary")
                watch.setToolTip("Открыть видео на весь экран")
                watch.clicked.connect(lambda checked=False, item=card, name=clip, file=filename:
                                      self.play_video(item, name, file))
                actions.addWidget(watch, j, 0)
            body.addLayout(actions)
            card.video_error = QLabel("Видео не найдено. Текст инструкции доступен в этой карточке.")
            card.video_error.setObjectName("mutedLabel")
            card.video_error.setWordWrap(True)
            body.addWidget(card.video_error)
            card.video_error.hide()
            self.cards.append(card)
        self._arrange_cards()
        self.scroll.viewport().installEventFilter(self)

    def _arrange_cards(self):
        width = self.scroll.viewport().width()
        columns = 2 if width >= 812 else 1
        if columns == self._columns:
            return
        self._columns = columns
        for column in range(2):
            self.card_grid.setColumnStretch(column, int(column < columns))
        for index, card in enumerate(self.cards):
            self.card_grid.addWidget(card, index // columns, index % columns)
        self.card_grid.setRowStretch(len(self.cards), 1)

    def eventFilter(self, obj, event):
        if obj is self.scroll.viewport() and event.type() == QEvent.Type.Resize:
            QTimer.singleShot(0, self._arrange_cards)
        return super().eventFilter(obj, event)

    def play_video(self, card, title, filename):
        path = get_app_root() / "docs" / "videos" / filename
        if self.active_card is not None:
            self.active_card.video_error.hide()
        if not path.is_file():
            self.stop_video()
            self.active_card = card
            card.video_error.show()
            return
        if self.player_panel is None:
            from UI.Guide_video import create_video_player
            self.player_panel = create_video_player(self.pages, on_back=self.stop_video)
            self.pages.addWidget(self.player_panel)
        self.active_card = card
        card.video_error.hide()
        self.pages.setCurrentWidget(self.player_panel)
        window = self.window()
        self._video_window_state = window.windowState()
        window.showFullScreen()
        self.player_panel.play_video(title, path)

    def stop_video(self):
        if self.player_panel is None or self.pages.currentWidget() is not self.player_panel:
            return
        state, self._video_window_state = self._video_window_state, None
        self.player_panel.stop_video()
        self.pages.setCurrentWidget(self.cover)
        if state is not None:
            self.window().setWindowState(state)

    def hideEvent(self, event):
        if not event.spontaneous() and self.window().isVisible():
            self.stop_video()
        super().hideEvent(event)

    def back_to_home(self):
        if self.main_window is not None:
            self.main_window.show_home_tab()
