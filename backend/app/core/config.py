from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configurações lidas das variáveis de ambiente (ou do arquivo .env)."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str
    # Endereços do frontend que podem chamar a API, separados por vírgula
    cors_origins: str = "http://localhost:5173"
    # Chave que assina os tokens de login. Precisa ser longa e secreta
    secret_key: str = Field(min_length=32)
    # Por quantas horas o login vale antes de pedir a senha de novo
    horas_de_sessao: int = Field(default=8, gt=0)
    # Primeiro administrador, criado por "python -m app.criar_admin"
    admin_nome: str = "Administrador"
    admin_email: str | None = None
    admin_senha: str | None = None

    @property
    def sqlalchemy_url(self) -> str:
        """Converte a URL do Neon para o driver psycopg 3 usado pelo SQLAlchemy."""
        url = self.database_url
        for prefixo in ("postgres://", "postgresql://"):
            if url.startswith(prefixo):
                return "postgresql+psycopg://" + url[len(prefixo) :]
        return url

    @property
    def cors_origin_list(self) -> list[str]:
        """Transforma o texto do CORS_ORIGINS em uma lista de endereços."""
        return [origem.strip() for origem in self.cors_origins.split(",") if origem.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
