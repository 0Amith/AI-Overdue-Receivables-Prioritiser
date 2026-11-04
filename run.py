"""Launcher: starts the local assistant and opens the browser."""
from __future__ import annotations

import sys
import threading
import webbrowser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "app"))

import server  # noqa: E402


def main() -> None:
    preferred = 8000
    if len(sys.argv) > 1:
        try:
            preferred = int(sys.argv[1])
        except ValueError:
            pass
    httpd, port = server.serve(preferred)
    url = f"http://127.0.0.1:{port}/"
    print("=" * 66)
    print("  ABC Traders Receivables Assistant")
    print(f"  {url}")
    print(f"  {len(server.BOT.invoices)} invoices loaded · reporting date 31 Oct 2026")
    print("  Ctrl+C to stop")
    print("=" * 66)
    threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        while True:
            threading.Event().wait(1)
    except KeyboardInterrupt:
        print("\nstopping…")
        httpd.shutdown()


if __name__ == "__main__":
    main()
