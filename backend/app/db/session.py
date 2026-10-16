from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings

# pool_pre_ping evita erro ao reutilizar conexões que o Neon encerrou
# depois de o banco "dormir" por inatividade.
engine = create_engine(
    get_settings().sqlalchemy_url,
    pool_pre_ping=True,
    connect_args={"connect_timeout": 10},
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    """Abre uma sessão com o banco por requisição e fecha no final."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
