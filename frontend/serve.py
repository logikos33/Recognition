"""Minimal SPA static file server — serves dist/ with index.html fallback."""
import http.server
import os

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
