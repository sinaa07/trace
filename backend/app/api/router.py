from fastapi import APIRouter

from app.api import cases, evidence, investigation, quality, timeline

api_router = APIRouter()
api_router.include_router(cases.router)
api_router.include_router(evidence.router)
api_router.include_router(timeline.router)
api_router.include_router(quality.router)
api_router.include_router(investigation.router)
