from __future__ import annotations

import threading
import webbrowser

import uvicorn

from app import config


def _open_browser_when_ready(url: str) -> None:
    threading.Timer(1.5, lambda: webbrowser.open(url)).start()


def main() -> None:
    url = f"http://{config.MEDIA_HOST}:{config.MEDIA_PORT}"
    _open_browser_when_ready(url)

    uvicorn.run(
        "app.main:app",
        host=config.MEDIA_HOST,
        port=config.MEDIA_PORT,
        log_level="info",
    )


if __name__ == "__main__":
    main()
