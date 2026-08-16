from fastapi import FastAPI
from app.api.video import router as video_router

app = FastAPI(
    title="BAIF Video Pipeline",
    version="0.1.0",
)

app.include_router(video_router)


@app.get("/health")
def health():
    return {"status": "ok"}
