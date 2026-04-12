from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api.routes import router
from app.core.config import settings
from app.services.docling_client import DoclingClient
from app.services.job_service import JobService
from app.services.job_store import JobStore


app = FastAPI(title=settings.app_name)

job_store = JobStore(output_root=settings.output_root)
docling_client = DoclingClient()
job_service = JobService(store=job_store, docling_client=docling_client)

app.include_router(router)


@app.get("/health")
async def health():
    return {"status": "ok", "env": settings.app_env}


if settings.serve_artifacts:
    out_dir = Path(settings.output_root).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/artifacts", StaticFiles(directory=str(out_dir)), name="artifacts")
