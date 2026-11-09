"""Run in a child process: emulate a blocked native worker and close the window."""
import os
from pathlib import Path
import time
ROOT=Path(__file__).resolve().parents[1]
os.environ['SPIKER_DATA_DIR']=str(ROOT/'validation_samples/shutdown-data')
from PySide6.QtCore import QThread, QTimer
from PySide6.QtWidgets import QApplication
import main

class BlockedWorker(QThread):
    def run(self): time.sleep(30)

app=QApplication([])
window=main.MainWindow()
window.open_speech('Сохранённый черновик перед закрытием')
worker=BlockedWorker(window); worker.start()
QTimer.singleShot(100,window.close)
app.exec()
