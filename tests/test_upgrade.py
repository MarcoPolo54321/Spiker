import os
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import ai_provider
from app_config import load_settings, save_settings
from app_paths import get_user_data_root

class UpgradeTests(unittest.TestCase):
    def tearDown(self):
        ai_provider._context.cancelled = None
        ai_provider._context.builtin = False
        get_user_data_root.cache_clear()

    def test_compatible_server_needs_no_api_key(self):
        with patch.object(ai_provider, '_request_json', return_value={'choices':[{'message':{'content':'Ответ'}}]}) as request:
            self.assertEqual(ai_provider.chat_completion('compatible','http://localhost:1234/v1','model',[]), 'Ответ')
            self.assertEqual(request.call_args.args[0], 'http://localhost:1234/v1/chat/completions')
            self.assertEqual(request.call_args.kwargs['headers'], {})

    def test_slow_http_does_not_prevent_cancel(self):
        cancelled, entered = threading.Event(), threading.Event()
        ai_provider._context.cancelled = cancelled.is_set
        def blocked(*args, control=None):
            entered.set()
            while not control.cancelled:
                time.sleep(0.01)
            return {}
        timer = threading.Timer(0.1, cancelled.set)
        try:
            with patch.object(ai_provider, '_request_json_blocking', side_effect=blocked):
                timer.start(); start=time.monotonic()
                with self.assertRaises(InterruptedError): ai_provider._request_json('http://localhost/test')
                self.assertLess(time.monotonic()-start, 1)
                self.assertTrue(entered.is_set())
        finally:
            timer.join()

    def test_new_providers_and_microphone_survive_restart(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {'SPIKER_DATA_DIR': tmp}):
            for provider in ('builtin','compatible'):
                save_settings(Path(tmp), {'ai_provider':provider,'microphone_name':'USB Microphone','faster_whisper_model':'medium'})
                actual=load_settings(Path(tmp))
                self.assertEqual(actual['ai_provider'],provider)
                self.assertEqual(actual['microphone_name'],'USB Microphone')
                self.assertEqual(actual['faster_whisper_model'],'medium')
