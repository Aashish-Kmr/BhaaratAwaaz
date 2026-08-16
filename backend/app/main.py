from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app import config
from app.jobs import worker
from app.routers.api import router as api_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    worker.start()
    yield


app = FastAPI(title="BAIF Bhasha", version="1.0.0", lifespan=lifespan)

app.include_router(api_router)


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    # API_CONTRACT.md expects error bodies shaped {"message": ..., "code": ...}
    # at the top level, not FastAPI's default {"detail": {...}} wrapper.
    if isinstance(exc.detail, dict) and "message" in exc.detail:
        body = exc.detail
    else:
        body = {"message": str(exc.detail), "code": "error"}
    return JSONResponse(status_code=exc.status_code, content=body, headers=exc.headers)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={"message": "Invalid request.", "code": "validation_error"},
    )


if config.FRONTEND_DIST_DIR.exists():
    app.mount(
        "/", StaticFiles(directory=str(config.FRONTEND_DIST_DIR), html=True), name="frontend"
    )
