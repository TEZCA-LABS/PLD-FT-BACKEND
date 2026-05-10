import json
from typing import Any, List, Union
from pydantic import AnyHttpUrl, Field, validator
from pydantic_settings import BaseSettings, SettingsConfigDict
import os

class Settings(BaseSettings):
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "PLD-FT Backend"
    
    DEBUG: bool = False
    
    # SECURITY
    SECRET_KEY: str = Field(default_factory=lambda: os.getenv("SECRET_KEY", ""))
    @validator("SECRET_KEY")
    def warn_if_default_secret(cls, v):
        if not v:
            raise ValueError("SECRET_KEY must be provided via environment variable.")
        if v in {"key", "dev-key", "change-me"}:
            import warnings
            warnings.warn("The SECRET_KEY is set to a weak default value. Change this in production.", UserWarning)
        return v
        
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    MASTER_PASSWORD: str = Field(default_factory=lambda: os.getenv("MASTER_PASSWORD", ""))
    FIRST_SUPERUSER: str = "admin@example.com"
    FIRST_SUPERUSER_PASSWORD: str = "admin"
    
    # DATABASE
    POSTGRES_SERVER: str = "localhost"
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    POSTGRES_DB: str = "pld_backend"
    SQLALCHEMY_DATABASE_URI: Union[str, None] = None

    @validator("SQLALCHEMY_DATABASE_URI", pre=True)
    def assemble_db_connection(cls, v: Union[str, None], values: dict[str, Any]) -> Any:
        if isinstance(v, str):
            return v
        return f"postgresql+asyncpg://{values.get('POSTGRES_USER')}:{values.get('POSTGRES_PASSWORD')}@{values.get('POSTGRES_SERVER')}/{values.get('POSTGRES_DB')}"

    # REDIS
    REDIS_URL: str = "redis://localhost:6379/0"

    # OPENAI
    OPENAI_API_KEY: str = "sk-placeholder"

    # Sanctions
    UN_SANCTIONS_XML_URL: str = "https://scsanctions.un.org/resources/xml/sp/consolidated.xml"
    MEX_SANCTIONS_CSV_URL: str = "https://repodatos.atdt.gob.mx/api_update/sabg/servidores_publicos_sancionados_vigentes/sancionados_102025_sabg.csv"
    SAT_69B_CSV_URL: str = "http://omawww.sat.gob.mx/cifras_sat/Documents/Listado_Completo_69-B.csv"
    OFAC_SDN_XML_URL: str = "http://www.treasury.gov/ofac/downloads/sanctions/1.0/sdn_advanced.xml"
    OFAC_CONS_XML_URL: str = "https://www.treasury.gov/ofac/downloads/sanctions/1.0/cons_advanced.xml"

    # CORS
    BACKEND_CORS_ORIGINS: List[str] = []  # Cambiar de List[AnyHttpUrl] a List[str]

    @validator("BACKEND_CORS_ORIGINS", pre=True)
    def parse_cors_origins(cls, v):
        """Parse CORS origins from a JSON list or comma-separated string."""
        if isinstance(v, list):
            return v
        if isinstance(v, str):
            if not v or v.strip() == "":
                return []
            if v.strip().startswith("["):
                try:
                    parsed_value = json.loads(v)
                except ValueError:
                    parsed_value = None
                else:
                    if isinstance(parsed_value, list):
                        return parsed_value
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return []

    # LOGGING
    LOG_LEVEL: str = "INFO"

    # ENVIRONMENT
    ENVIRONMENT: str = "development"

    # FEATURE FLAGS
    ENABLE_RAG: bool = True
    ENABLE_CELERY_WORKER: bool = True
    AUTO_MIGRATE: bool = False

    model_config = SettingsConfigDict(case_sensitive=True, env_file=".env", enable_decoding=False)

settings = Settings()