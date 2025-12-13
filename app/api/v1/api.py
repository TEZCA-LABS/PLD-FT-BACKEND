
from fastapi import APIRouter
from app.api.v1.endpoints import auth, entities, intelligence, users

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(entities.router, prefix="/entities", tags=["entities"])
api_router.include_router(intelligence.router, prefix="/intelligence", tags=["intelligence"])
