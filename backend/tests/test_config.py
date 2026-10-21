from app.core.config import Settings


def test_url_do_neon_vira_driver_psycopg():
    s = Settings(database_url="postgresql://u:s@ep-x.neon.tech/db?sslmode=require")
    assert s.sqlalchemy_url == "postgresql+psycopg://u:s@ep-x.neon.tech/db?sslmode=require"


def test_url_postgres_curta_tambem_converte():
    s = Settings(database_url="postgres://u:s@host/db")
    assert s.sqlalchemy_url.startswith("postgresql+psycopg://")


def test_cors_aceita_lista_separada_por_virgula():
    s = Settings(
        database_url="postgresql://u:s@host/db",
        cors_origins="http://localhost:5173, https://na-mochila.vercel.app",
    )
    assert s.cors_origin_list == ["http://localhost:5173", "https://na-mochila.vercel.app"]
