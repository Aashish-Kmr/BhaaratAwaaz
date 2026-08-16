from fastapi import FastAPI

from api.audio import router as audio_router


app = FastAPI(
    title="BhaaratAwaaz",
    description="Offline multilingual audio translation API",
    version="1.0.0",
)


app.include_router(audio_router)


@app.get("/")
def root():
    return {
        "service": "BhaaratAwaaz",
        "status": "running",
    }


@app.get("/health")
def health():
    return {
        "status": "healthy",
    }