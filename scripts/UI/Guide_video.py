"""Read bundled tutorials in a local player, opened on demand."""
from PySide6.QtCore import Qt, QRect, QUrl
from PySide6.QtGui import QColor, QImage, QKeySequence, QPainter, QShortcut
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer, QVideoSink
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QSlider, QVBoxLayout, QWidget


class GuideVideoSurface(QWidget):
    """Paint video at the largest size that preserves its aspect ratio."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self._image = QImage()
        self.sink = QVideoSink(self)
        self.sink.videoFrameChanged.connect(self._frame_changed)
        self.setMinimumSize(240, 195)

    def _frame_changed(self, frame):
        self._image = frame.toImage() if frame.isValid() else QImage()
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#061636"))
        if not self._image.isNull():
            size = self._image.size().scaled(self.size(), Qt.AspectRatioMode.KeepAspectRatio)
            target = QRect((self.width() - size.width()) // 2, (self.height() - size.height()) // 2,
                           size.width(), size.height())
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
            painter.drawImage(target, self._image)


def create_video_player(parent, *, on_back):
    panel = QFrame(parent)
    panel.setObjectName("userGuideContentPanel")
    layout = QVBoxLayout(panel)
    header = QHBoxLayout()
    close = QPushButton("← К инструкции")
    close.setProperty("role", "back")
    close.setToolTip("Вернуться к обучению (Esc)")
    close.clicked.connect(on_back)
    escape = QShortcut(QKeySequence(Qt.Key.Key_Escape), panel)
    escape.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
    escape.activated.connect(on_back)
    header.addWidget(close)
    heading = QLabel()
    heading.setObjectName("dialogTitle")
    heading.setWordWrap(True)
    header.addWidget(heading, 1)
    layout.addLayout(header)
    video = GuideVideoSurface(panel)
    layout.addWidget(video, 1)
    caption = QLabel("Короткий пример в интерфейсе СПИКЕР · доступен без интернета")
    caption.setObjectName("mutedLabel")
    caption.setWordWrap(True)
    layout.addWidget(caption)

    controls = QHBoxLayout()
    toggle = QPushButton("Воспроизвести")
    toggle.setProperty("role", "primary")
    controls.addWidget(toggle)
    timeline = QSlider(Qt.Orientation.Horizontal)
    timeline.setAccessibleName("Позиция видео")
    timeline.setRange(0, 0)
    controls.addWidget(timeline, 1)
    clock = QLabel("0:00 / 0:00")
    controls.addWidget(clock)
    layout.addLayout(controls)

    player = panel.player = QMediaPlayer(panel)
    player.setAudioOutput(QAudioOutput(panel))
    player.setVideoSink(video.sink)

    def format_time(ms):
        seconds = max(0, int(ms) // 1000)
        return f"{seconds // 60}:{seconds % 60:02d}"

    def update_time(position):
        if not timeline.isSliderDown():
            timeline.setValue(position)
        clock.setText(f"{format_time(position)} / {format_time(player.duration())}")

    def toggle_play():
        if player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            player.pause()
        else:
            if player.mediaStatus() == QMediaPlayer.MediaStatus.EndOfMedia:
                player.setPosition(0)
            player.play()

    def playback_failed(*_):
        caption.setText("Не удалось воспроизвести видео в СПИКЕР. Откройте MP4 из папки docs/videos.")
        toggle.setEnabled(False)

    toggle.clicked.connect(toggle_play)
    timeline.sliderMoved.connect(player.setPosition)
    player.positionChanged.connect(update_time)
    player.durationChanged.connect(lambda duration: (timeline.setRange(0, duration), update_time(player.position())))
    player.playbackStateChanged.connect(lambda state: toggle.setText(
        "Пауза" if state == QMediaPlayer.PlaybackState.PlayingState else "Воспроизвести"))
    player.errorOccurred.connect(playback_failed)
    def stop_video():
        player.stop()
        player.setSource(QUrl())

    def play_video(title, path):
        heading.setText(title)
        caption.setText("Короткий пример в интерфейсе СПИКЕР · доступен без интернета")
        toggle.setEnabled(True)
        close.setFocus(Qt.FocusReason.OtherFocusReason)
        player.setSource(QUrl.fromLocalFile(str(path.resolve())))
        player.play()

    panel.play_video = play_video
    panel.stop_video = stop_video
    return panel
