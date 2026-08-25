from fastapi import APIRouter

from app.api import cases, evidence, quality, timeline

api_router = APIRouter()
api_router.include_router(cases.router)
api_router.include_router(evidence.router)
api_router.include_router(timeline.router)
api_router.include_router(quality.router)
