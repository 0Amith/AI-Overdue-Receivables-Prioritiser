
"""Production entry point for Render."""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "app"))

import server

PORT = int(os.environ.get("PORT", "10000"))

httpd = server.ThreadingHTTPServer(
    ("0.0.0.0", PORT),
    server.Handler
)

print(f"Server running on port {PORT}")

httpd.serve_forever()
