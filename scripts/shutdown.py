"""Bounded shutdown: persist text first, cancel workers, never destroy a live QThread."""
import logging
import os
import time
from PySide6.QtCore import QThread, QTimer
from PySide6.QtWidgets import QApplication, QMessageBox
from app_config import atomic_write_json
from app_paths import get_user_data_root

def begin_shutdown(window, event, root):
    event.ignore()
    if window._closing: return
    app = QApplication.instance()
    # Closing the last visible window must not stop Qt's event loop before the
    # shutdown timer has cancelled workers and saved the session.
    if app is not None:
        app.setQuitOnLastWindowClosed(False)
    drafts = dict(getattr(window, '_drafts', {}))
    if window.dictation_page:
        drafts['dictation'] = window.dictation_page.ui.textEdit_field_to_text_from_audio.toPlainText()
    if window.ai_page:
        drafts['ai_source'] = window.ai_page.source_editor.toPlainText()
        drafts['ai_result'] = window.ai_page.output_editor.toPlainText()
    if window.speech_page:
        drafts['speech'] = window.speech_page.editor.toPlainText()
    try:
        if drafts:
            atomic_write_json(get_user_data_root(root) / 'data/last-session.json', drafts)
        if window.queue_page:
            window.queue_page.prepare_for_shutdown(timeout_ms=0)
    except Exception as exc:
        QMessageBox.warning(window, 'Не удалось сохранить сеанс', str(exc))
        return
    window._closing = True
    page = window.dictation_page
    if page:
        page.is_recording = False
        page.timer.stop()
        if page.audio_processor:
            page.audio_processor.is_recording = False
            page.audio_processor.discard_pending = True
        if page.live_capture_done: page.live_capture_done.set()
    if window.ai_page: window.ai_page.prepare_for_shutdown(timeout_ms=0)
    if window.speech_page: window.speech_page.prepare_for_shutdown(timeout_ms=0)
    threads = list(window.findChildren(QThread))
    # Audio capture threads in the legacy dialog are parentless.
    if page:
        threads.extend(t for t in (page.audio_processor, page.whisper_worker) if t is not None)
    for worker in threads:
        try: worker.requestInterruption()
        except RuntimeError: pass
    window.hide()
    deadline = time.monotonic() + 3
    timer = QTimer(window); window._shutdown_timer = timer
    def poll():
        running = False
        for worker in threads:
            try: running = running or worker.isRunning()
            except RuntimeError: pass
        if running and time.monotonic() < deadline: return
        timer.stop()
        from local_ai import stop
        stop()
        logging.shutdown()
        if running:
            # Native calls may be non-interruptible. The process boundary is safe;
            # QThread.terminate() is not. All user-owned state was saved above.
            os._exit(0)
        if app is not None:
            app.quit()
    timer.timeout.connect(poll); timer.start(50)
