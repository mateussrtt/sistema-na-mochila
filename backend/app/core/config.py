from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configurações lidas das variáveis de ambiente (ou do arquivo .env)."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str

    @property
    def sqlalchemy_url(self) -> str:
        """Converte a URL do Neon para o driver psycopg 3 usado pelo SQLAlchemy."""
        url = self.database_url
        for prefixo in ("postgres://", "postgresql://"):
            if url.startswith(prefixo):
                return "postgresql+psycopg://" + url[len(prefixo) :]
        return url


@lru_cache
def get_settings() -> Settings:
    return Settings()
