
from typing import List, Union
from pydantic import AnyHttpUrl, validator
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "PLD-FT Backend"
    
    DEBUG: bool = False
    
    # SECURITY
    SECRET_KEY: str = "key" 
    @validator("SECRET_KEY")
    def warn_if_default_secret(cls, v):
        if v == "key":
            import warnings
            warnings.warn("The SECRET_KEY is set to the default insecure value. Change this in production.", UserWarning)
        return v
        
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    MASTER_PASSWORD: str = "admin_master_secret"
    FIRST_SUPERUSER: str = "admin@example.com"
    FIRST_SUPERUSER_PASSWORD: str = "admin"
    
    # DATABASE
    POSTGRES_SERVER: str = "localhost"
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    POSTGRES_DB: str = "pld_backend"
    SQLALCHEMY_DATABASE_URI: Union[str, None] = None

    @validator("SQLALCHEMY_DATABASE_URI", pre=True)
    def assemble_db_connection(cls, v: Union[str, None], values: dict[str, any]) -> any:
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

    # CORS
    BACKEND_CORS_ORIGINS: List[AnyHttpUrl] = []

    model_config = SettingsConfigDict(case_sensitive=True, env_file=".env")

settings = Settings()
