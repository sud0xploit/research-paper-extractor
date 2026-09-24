from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.export import router as export_router
from app.api.process import router as process_router
from app.api.review import router as review_router
from app.api.upload import router as upload_router


app = FastAPI(
    title="Research Document Extractor API",
    description="API for document extraction, classification, verification, and reporting.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH", "OPTIONS"],
    allow_headers=["Content-Type"],
)

app.include_router(upload_router)
app.include_router(review_router)
app.include_router(export_router)
app.include_router(process_router)


@app.get("/api/health", tags=["health"])
def health_check() -> dict[str, str]:
    """Return a lightweight liveness response for local and deployment checks."""
    return {"status": "ok"}
