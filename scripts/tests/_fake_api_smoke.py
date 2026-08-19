"""API falsa para exercitar scripts/smoke_test.sh sem backend real.

Contrato imitado: /health e /api/streams/status são públicos; /api/auth/me e
/api/cameras exigem `Authorization: Bearer <token válido>`. O login devolve um
token que AUTENTICA só com a senha certa — com a senha errada devolve um token
que existe mas não vale, que é exatamente o caso que a versão anterior do
smoke aprovava por engano (ver test_smoke_test.sh).
"""
import json, threading
from http.server import BaseHTTPRequestHandler, HTTPServer

BOM = "tok-bom"

class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def _send(self, code, body=b""):
        self.send_response(code); self.send_header("Content-Length", str(len(body)))
        self.end_headers(); self.wfile.write(body)
    def do_GET(self):
        if self.path in ("/health", "/api/streams/status"):
            return self._send(200, b"{}")
        if self.path in ("/api/auth/me", "/api/cameras"):
            auth = self.headers.get("Authorization", "")
            return self._send(200 if auth == f"Bearer {BOM}" else 401, b"{}")
        self._send(404)
    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        d = json.loads(self.rfile.read(n) or b"{}")
        # senha certa -> token bom; senha errada -> token que NÃO autentica
        tok = BOM if d.get("password") == "senha-certa" else "tok-ruim"
        self._send(200, json.dumps({"data": {"token": tok}}).encode())

srv = HTTPServer(("127.0.0.1", 8099), H)
threading.Thread(target=srv.serve_forever, daemon=True).start()
import time; time.sleep(float(__import__("os").environ.get("FAKE_API_TTL", "60")))
