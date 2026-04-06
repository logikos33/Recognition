"""Minimal static file server for SPA (fallback to index.html).
Builds frontend if dist/ doesn't exist.
"""
import http.server
import os
import subprocess

PORT = int(os.environ.get("PORT", 3000))

# Resolve frontend directory
_script_dir = os.path.dirname(os.path.abspath(__file__))
FRONTEND_DIR = _script_dir
DIST = os.path.join(FRONTEND_DIR, "dist")

# Build if dist/ doesn't exist
if not os.path.exists(DIST) or not os.path.exists(os.path.join(DIST, "index.html")):
    print(f"dist/ not found at {DIST}, building...")
    subprocess.run(["npm", "ci"], cwd=FRONTEND_DIR, check=True)
    subprocess.run(["npm", "run", "build"], cwd=FRONTEND_DIR, check=True)

print(f"Serving {DIST} on port {PORT}")


class SPAHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIST, **kwargs)

    def do_GET(self):
        path = os.path.join(DIST, self.path.lstrip("/"))
        if not os.path.exists(path) or os.path.isdir(path):
            if not self.path.startswith("/assets/"):
                self.path = "/index.html"
        super().do_GET()

    def log_message(self, format, *args):
        pass  # Silence request logs


if __name__ == "__main__":
    server = http.server.HTTPServer(("0.0.0.0", PORT), SPAHandler)
    print(f"Frontend server running on port {PORT}")
    server.serve_forever()
