
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.core.config import settings
from app.api.v1.api import api_router
import logging

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json"
)

# DEBUG: Print CORS configuration
logger.info(f"[CORS DEBUG] BACKEND_CORS_ORIGINS type: {type(settings.BACKEND_CORS_ORIGINS)}")
logger.info(f"[CORS DEBUG] BACKEND_CORS_ORIGINS value: {settings.BACKEND_CORS_ORIGINS}")
logger.info(f"[CORS DEBUG] BACKEND_CORS_ORIGINS bool: {bool(settings.BACKEND_CORS_ORIGINS)}")

# Set all CORS enabled origins
if hasattr(settings, 'BACKEND_CORS_ORIGINS') and settings.BACKEND_CORS_ORIGINS:
    cors_origins = settings.BACKEND_CORS_ORIGINS  # Ya son strings, sin conversión
    logger.info(f"[CORS DEBUG] CORS middleware enabled with origins: {cors_origins}")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
else:
    logger.warning("[CORS DEBUG] CORS middleware NOT enabled - BACKEND_CORS_ORIGINS is empty or not set!")

app.include_router(api_router, prefix=settings.API_V1_STR)

@app.get("/")
def root():
    return {"message": "Welcome to PLD-FT Backend API"}

@app.get("/health")
def health_check():
    """Health check endpoint for container orchestration"""
    return JSONResponse(
        status_code=200,
        content={
            "status": "healthy",
            "service": settings.PROJECT_NAME,
            "version": "1.0.0"
        }
    )