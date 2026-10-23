from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.session import engine, get_db
from app.main import app


@pytest.fixture
def db() -> Iterator[Session]:
    """Sessão dentro de uma transação que é desfeita no final do teste.

    Assim os testes podem gravar à vontade sem deixar lixo no banco.
    """
    conexao = engine.connect()
    transacao = conexao.begin()
    sessao = Session(bind=conexao, join_transaction_mode="create_savepoint", expire_on_commit=False)
    try:
        yield sessao
    finally:
        sessao.close()
        transacao.rollback()
        conexao.close()


@pytest.fixture
def api(db: Session) -> Iterator[TestClient]:
    """Cliente da API que usa a sessão de teste no lugar da real."""
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as cliente:
        yield cliente
    app.dependency_overrides.clear()
