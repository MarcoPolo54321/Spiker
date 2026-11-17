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
from model_paths import model_roots

MODEL = 'GigaChat3.1-10B-A1.8B-q4_K_M.gguf'
LIGHT_MODEL = 'Qwen3-4B-Q4_K_M.gguf'
MODELS = {MODEL: 'GigaChat 3.1 · 10 млрд', LIGHT_MODEL: 'Qwen3 · 4 млрд (быстрее)'}
_active_model = None
_process = None
_port = None
_key = secrets.token_urlsafe(32)
_lock = threading.Lock()
_log = None

def model_label(name):
    return MODELS.get(name, Path(name).stem)


def _is_gguf(path):
    try:
        if not path.is_file() or path.stat().st_size < 1024**2:
            return False
        with path.open("rb") as stream:
            return stream.read(4) == b"GGUF"
    except OSError:
        return False


def model_path(name=MODEL):
    if Path(name).name != name or not str(name).lower().endswith(".gguf") or ":" in name:
        raise ValueError('Выберите файл GGUF из списка локальных моделей.')
    root = get_app_root()
    for base in model_roots(root, legacy_pack=True):
        path = base / 'llm' / name
        if _is_gguf(path):
            return path
    raise FileNotFoundError(f'Не установлена локальная модель {model_label(name)}.')


def installed_models():
    result = []
    for name in MODELS:
        try:
            model_path(name)
            result.append(name)
        except FileNotFoundError:
            pass
    seen = {name.casefold() for name in result}
    for base in model_roots(get_app_root(), legacy_pack=True):
        for path in sorted((base / "llm").glob("*.gguf"), key=lambda item: item.name.casefold()):
            if path.name.casefold() not in seen and _is_gguf(path):
                seen.add(path.name.casefold())
                result.append(path.name)
    return result

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

def ensure_started(cancelled=None, name=MODEL):
    global _process, _port, _log, _active_model
    with _lock:
        if _process is not None and _process.poll() is None and _active_model == name:
            return f'http://127.0.0.1:{_port}/v1', _key
        model = model_path(name)
        stop()
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
        _active_model = name
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
