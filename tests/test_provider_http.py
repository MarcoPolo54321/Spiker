import json
import sys
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import ai_provider


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/api/tags":
            data = {"models": [{"name": "qwen3.5:4b"}]}
            self._send(data)
        elif self.path == "/v1/models":
            self.server.seen_auth = self.headers.get("Authorization", "")
            self._send({"data": [{"id": "example-model"}]})
        else:
            self._send({"error": "not found"}, 404)

    def do_POST(self):
        if self.path != "/v1/chat/completions":
            self._send({"error": "not found"}, 404)
            return
        self.server.seen_auth = self.headers.get("Authorization", "")
        length = int(self.headers.get("Content-Length", "0"))
        self.server.seen_payload = json.loads(self.rfile.read(length).decode("utf-8"))
        self._send({"choices": [{"message": {"content": "Локальный результат"}}]})

    def _send(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_args):
        pass


class ProviderHTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
        cls.server.seen_auth = ""
        cls.server.seen_payload = None
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)

    def test_ollama_model_list(self):
        models = ai_provider.list_local_models(self.base + "/v1")
        self.assertEqual(models, ["qwen3.5:4b"])

    def test_api_model_list_uses_authorization(self):
        models = ai_provider.probe_provider("api", self.base + "/v1", "test-secret")
        self.assertEqual(models, ["example-model"])
        self.assertEqual(self.server.seen_auth, "Bearer test-secret")

    def test_chat_completion_posts_messages_and_returns_text(self):
        output = ai_provider.chat_completion("local", self.base + "/v1", "qwen3.5:4b", [{"role": "user", "content": "test"}])
        self.assertEqual(output, "Локальный результат")
        self.assertEqual(self.server.seen_auth, "Bearer ollama")
        self.assertEqual(self.server.seen_payload["model"], "qwen3.5:4b")
        self.assertFalse(self.server.seen_payload["stream"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
