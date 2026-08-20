from fastapi import FastAPI

from app.api.video import router


app = FastAPI(
    title="BAIF Offline Video Translation",
    version="1.0.0",
)

app.include_router(router)


@app.get("/health")
def health():
    return {
        "status": "ok"
    }