"""Minimal SPA static file server — serves dist/ with index.html fallback."""
import http.server
import mimetypes
import os

# Fix MIME types — Python's defaults miss modern web types
mimetypes.add_type("application/javascript", ".js")
mimetypes.add_type("application/javascript", ".mjs")
mimetypes.add_type("text/css", ".css")
mimetypes.add_type("image/svg+xml", ".svg")
mimetypes.add_type("application/json", ".json")
mimetypes.add_type("application/wasm", ".wasm")
mimetypes.add_type("font/woff2", ".woff2")
mimetypes.add_type("font/woff", ".woff")

PORT = int(os.environ.get("PORT", 3000))
DIST = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dist")
if not os.path.isdir(DIST):
    DIST = "/app/dist"


class SPAHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIST, **kwargs)

    def do_GET(self):
        path = os.path.join(DIST, self.path.lstrip("/"))
        if not os.path.exists(path) and not self.path.startswith("/assets/"):
            self.path = "/index.html"
        super().do_GET()


if __name__ == "__main__":
    print(f"Serving {DIST} on port {PORT}")
    server = http.server.HTTPServer(("0.0.0.0", PORT), SPAHandler)
    server.serve_forever()
