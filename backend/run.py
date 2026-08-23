from __future__ import annotations

import threading
import webbrowser

import uvicorn

from app import config
from app.main import app as fastapi_app


def _open_browser_when_ready(url: str) -> None:
    threading.Timer(1.5, lambda: webbrowser.open(url)).start()


def main() -> None:
    url = f"http://{config.MEDIA_HOST}:{config.MEDIA_PORT}"
    _open_browser_when_ready(url)

    # Pass the app object directly rather than the "app.main:app" import
    # string uvicorn also accepts: PyInstaller bundles by statically tracing
    # real `import` statements, and can't see into a string to know it needs
    # to include app.main (and everything it pulls in) -- passing the
    # object here makes that import traceable, so the frozen build actually
    # contains the application. (The string form only matters for
    # reload=/workers>1, neither of which run.py uses.)
    uvicorn.run(
        fastapi_app,
        host=config.MEDIA_HOST,
        port=config.MEDIA_PORT,
        log_level="info",
    )


if __name__ == "__main__":
    main()
