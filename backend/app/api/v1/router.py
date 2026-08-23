from fastapi import APIRouter

from app.api.v1.routes.auth import router as auth_router
from app.api.v1.routes.bootstrap import router as bootstrap_router
from app.api.v1.routes.chat import router as chat_router
from app.api.v1.routes.health import router as health_router
from app.api.v1.routes.ingest import router as ingest_router
from app.api.v1.routes.persona_config import router as persona_config_router
from app.api.v1.routes.knowledge import router as knowledge_router
from app.api.v1.routes.context_contract import router as context_contract_router
from app.api.v1.routes.development import router as development_router
from app.api.v1.routes.deployment_control import router as deployment_control_router
from app.api.v1.routes.protected import router as protected_router
from app.api.v1.routes.realtime import router as realtime_router
from app.api.v1.routes.reviews import router as reviews_router
from app.api.v1.routes.studio import router as studio_router
from app.api.v1.routes.collaboration import router as collaboration_router
from app.api.v1.routes.system import router as system_router
from app.api.v1.routes.tools import router as tools_router

v1_router = APIRouter(prefix="/v1")
v1_router.include_router(health_router)
v1_router.include_router(auth_router)
v1_router.include_router(protected_router)
v1_router.include_router(bootstrap_router)
v1_router.include_router(system_router)
v1_router.include_router(ingest_router)
v1_router.include_router(studio_router)
v1_router.include_router(collaboration_router)
v1_router.include_router(chat_router)
v1_router.include_router(persona_config_router)
v1_router.include_router(knowledge_router)
v1_router.include_router(context_contract_router)
v1_router.include_router(development_router)
v1_router.include_router(deployment_control_router)
v1_router.include_router(reviews_router)
v1_router.include_router(realtime_router)
v1_router.include_router(tools_router)
