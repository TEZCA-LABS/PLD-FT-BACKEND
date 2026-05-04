from fastapi import APIRouter
from app.api.v1.endpoints import (
	audit_logs,
	auth,
	entities,
	intelligence,
	roles,
	sanctions,
	search,
	users,
)

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(entities.router, prefix="/entities", tags=["entities"])
api_router.include_router(intelligence.router, prefix="/intelligence", tags=["intelligence"])
api_router.include_router(sanctions.router, prefix="/sanctions", tags=["sanctions"])
api_router.include_router(search.router, prefix="/search", tags=["search"])
api_router.include_router(audit_logs.router, prefix="/audit", tags=["audit"])
api_router.include_router(audit_logs.router, prefix="/audit-logs", tags=["audit"])
api_router.include_router(roles.router, prefix="/roles", tags=["roles"])
