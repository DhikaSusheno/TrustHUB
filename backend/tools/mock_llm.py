"""Mock OpenAI-compatible LLM untuk verifikasi lokal.

Gunanya satu: membuktikan rantai TrustHub -> provider -> SSE jalan, tanpa
menarik model Ollama (puluhan GB). Menjawab /v1/chat/completions dalam format
OpenAI, streaming maupun tidak.

Jalankan: python tools/mock_llm.py [port]
"""

import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
MODEL = "mock-model-1"

# Potongan jawaban, dikirim satu per satu saat streaming. Sengaja pendek
# supaya respons terlihat cepat di terminal.
CHUNKS = ["Halo", " dari", " mock", " LLM", "."]


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        # Satu baris per request; default handler spam dua baris per request.
        sys.stderr.write("[mock] " + (fmt % args) + "\n")

    def do_GET(self):
        # Dipakai frontend untuk cek sehat; beberapa tool memanggil /v1/models.
        if self.path.startswith("/v1/models"):
            return self._json(
                200,
                {
                    "object": "list",
                    "data": [{"id": MODEL, "object": "model", "owned_by": "mock"}],
                },
            )
        return self._json(404, {"error": {"message": "not found"}})

    def do_POST(self):
        if not self.path.startswith("/v1/chat/completions"):
            return self._json(404, {"error": {"message": "not found"}})

        length = int(self.headers.get("content-length") or 0)
        req = json.loads(self.rfile.read(length) or b"{}")
        model = req.get("model") or MODEL

        if not req.get("stream"):
            return self._json(
                200,
                {
                    "id": "chatcmpl-mock-1",
                    "object": "chat.completion",
                    "model": model,
                    "choices": [
                        {
                            "index": 0,
                            "message": {
                                "role": "assistant",
                                "content": "".join(CHUNKS),
                            },
                            "finish_reason": "stop",
                        }
                    ],
                    "usage": {"prompt_tokens": 8, "completion_tokens": 5},
                },
            )

        # Streaming: chunk OpenAI (delta) lalu penanda [DONE].
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "close")
        self.end_headers()
        for piece in CHUNKS:
            delta = {
                "id": "chatcmpl-mock-1",
                "object": "chat.completion.chunk",
                "model": model,
                "choices": [{"index": 0, "delta": {"content": piece}, "finish_reason": None}],
            }
            self.wfile.write(f"data: {json.dumps(delta)}\n\n".encode())
            self.wfile.flush()
        done = {
            "id": "chatcmpl-mock-1",
            "object": "chat.completion.chunk",
            "model": model,
            "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
        }
        self.wfile.write(f"data: {json.dumps(done)}\n\n".encode())
        self.wfile.write(b"data: [DONE]\n\n")
        self.wfile.flush()
        self.close_connection = True

    def _json(self, status, payload):
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


if __name__ == "__main__":
    print(f"[mock] OpenAI-compatible LLM di http://127.0.0.1:{PORT}/v1")
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
