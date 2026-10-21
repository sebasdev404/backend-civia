from fastapi import APIRouter
from app.api.v1.auth import router as auth_router
from app.api.v1.cases import router as cases_router
from app.api.v1.incidents import router as map_router
from app.api.v1.analytics import router as analytics_router
from app.api.v1.seed import router as seed_router
from app.api.v1.ai import router as ai_router
from app.api.v1.meta import router as meta_router
from app.api.v1.system import router as system_router
from app.api.v1.citizens import router as citizens_router

api_v1_router = APIRouter()

api_v1_router.include_router(auth_router)
api_v1_router.include_router(cases_router)
api_v1_router.include_router(map_router)
api_v1_router.include_router(analytics_router)
api_v1_router.include_router(seed_router)
api_v1_router.include_router(ai_router)
api_v1_router.include_router(meta_router)
api_v1_router.include_router(system_router)
api_v1_router.include_router(citizens_router)
