from app.core.config import Settings


def test_url_do_neon_vira_driver_psycopg():
    s = Settings(database_url="postgresql://u:s@ep-x.neon.tech/db?sslmode=require")
    assert s.sqlalchemy_url == "postgresql+psycopg://u:s@ep-x.neon.tech/db?sslmode=require"


def test_url_postgres_curta_tambem_converte():
    s = Settings(database_url="postgres://u:s@host/db")
    assert s.sqlalchemy_url.startswith("postgresql+psycopg://")
