"""Manage only Spiker's own loopback llama.cpp process, without an external service."""
import atexit
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import threading
import time
import urllib.request
from app_paths import get_app_root, get_user_data_root

MODEL = 'GigaChat3.1-10B-A1.8B-q4_K_M.gguf'
_process = None
_port = None
_key = secrets.token_urlsafe(32)
_lock = threading.Lock()
_log = None

def model_path():
    root = get_app_root()
    for base in (root, get_user_data_root(root)):
        path = base / 'models/llm' / MODEL
        if path.is_file(): return path
    # Installed releases may share the separately installed model pack on D:.
    settings = get_user_data_root(root) / 'data/model-pack.json'
    if settings.is_file():
        base = Path(json.loads(settings.read_text(encoding='utf-8'))['root'])
        if (base / 'models/llm' / MODEL).is_file(): return base / 'models/llm' / MODEL
    raise FileNotFoundError('Не установлен пакет GigaChat для встроенного ИИ.')

def stop():
    global _process, _log
    process, _process = _process, None
    if process is not None and process.poll() is None:
        process.terminate()
        try: process.wait(timeout=2)
        except subprocess.TimeoutExpired: process.kill(); process.wait(timeout=2)
    if _log is not None:
        _log.close(); _log = None

atexit.register(stop)

def ensure_started(cancelled=None):
    global _process, _port, _log
    with _lock:
        if _process is not None and _process.poll() is None:
            return f'http://127.0.0.1:{_port}/v1', _key
        model = model_path()
        app_root = get_app_root()
        candidates = (app_root / 'runtime/llama', model.parents[2] / 'runtime/llama')
        executable = next((folder / 'llama-server.exe' for folder in candidates if (folder / 'llama-server.exe').is_file()), None)
        if executable is None:
            raise FileNotFoundError('Не установлен встроенный движок llama.cpp. Скопируйте llama-server.exe и DLL в папку runtime/llama рядом с приложением.')
        with socket.socket() as port:
            port.bind(('127.0.0.1', 0)); _port = port.getsockname()[1]
        logs = get_user_data_root() / 'logs'; logs.mkdir(parents=True, exist_ok=True)
        _log = (logs / 'builtin-ai.log').open('ab')
        _process = subprocess.Popen([str(executable), '-m', str(model), '--host', '127.0.0.1',
            '--port', str(_port), '--api-key', _key, '-c', '4096', '-t', '4', '-ngl', '0',
            '--parallel', '1', '--jinja', '--no-webui'],
            stdin=subprocess.DEVNULL, stdout=_log, stderr=_log,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        deadline = time.monotonic() + 180
        while time.monotonic() < deadline:
            if cancelled and cancelled(): stop(); raise InterruptedError('Загрузка ИИ отменена.')
            if _process.poll() is not None:
                stop(); raise RuntimeError('Не удалось загрузить GigaChat. Подробности: logs/builtin-ai.log')
            try:
                with opener.open(f'http://127.0.0.1:{_port}/health', timeout=1) as response:
                    if response.status == 200: return f'http://127.0.0.1:{_port}/v1', _key
            except Exception: pass
            time.sleep(0.15)
        stop(); raise TimeoutError('Встроенный ИИ не успел загрузиться за 3 минуты.')
