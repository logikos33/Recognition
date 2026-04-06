"""Minimal static file server for SPA (fallback to index.html)."""
import http.server
import os

PORT = int(os.environ.get("PORT", 3000))

# Resolve dist directory relative to this script
_script_dir = os.path.dirname(os.path.abspath(__file__))
_candidates = [
    os.path.join(_script_dir, "dist"),       # frontend/dist
    os.path.join(os.getcwd(), "frontend", "dist"),  # /app/frontend/dist
    os.path.join(os.getcwd(), "dist"),        # /app/dist
]
DIST = next((d for d in _candidates if os.path.exists(d)), _script_dir)


class SPAHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIST, **kwargs)

    def do_GET(self):
        # Serve file if exists, otherwise index.html (SPA routing)
        path = os.path.join(DIST, self.path.lstrip("/"))
        if not os.path.exists(path) or os.path.isdir(path):
            if not self.path.startswith("/assets/"):
                self.path = "/index.html"
        super().do_GET()


if __name__ == "__main__":
    print(f"Serving {DIST} on port {PORT}")
    server = http.server.HTTPServer(("0.0.0.0", PORT), SPAHandler)
    server.serve_forever()
