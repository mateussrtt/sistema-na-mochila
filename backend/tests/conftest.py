from collections.abc import Callable, Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.seguranca import criar_token, gerar_hash
from app.db.session import engine, get_db
from app.main import app
from app.models import Perfil, Usuario

SENHA_DE_TESTE = "senha-de-teste"
# Calculado uma vez só: o hash da senha é lento de propósito
HASH_DE_TESTE = gerar_hash(SENHA_DE_TESTE)


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
def cria_usuario(db: Session) -> Callable[..., Usuario]:
    """Cria um usuário no banco de teste. O e-mail muda a cada chamada."""
    contador = 0

    def criar(perfil: Perfil = Perfil.ADMINISTRADOR, ativo: bool = True) -> Usuario:
        nonlocal contador
        contador += 1
        usuario = Usuario(
            nome=f"Usuário {perfil.value} {contador}",
            email=f"{perfil.value}{contador}@teste.local",
            senha_hash=HASH_DE_TESTE,
            perfil=perfil,
            ativo=ativo,
        )
        db.add(usuario)
        db.flush()
        return usuario

    return criar


@pytest.fixture
def sem_login(db: Session) -> Iterator[TestClient]:
    """Cliente da API sem token, como alguém que ainda não entrou."""
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as cliente:
        yield cliente
    app.dependency_overrides.clear()


@pytest.fixture
def logado_como(sem_login: TestClient) -> Callable[[Usuario], TestClient]:
    """Devolve um cliente logado como o usuário informado."""

    def logar(usuario: Usuario) -> TestClient:
        cliente = TestClient(app)
        cliente.headers["Authorization"] = f"Bearer {criar_token(usuario.id)}"
        return cliente

    return logar


@pytest.fixture
def api_como(logado_como, cria_usuario) -> Callable[[Perfil], TestClient]:
    """Devolve um cliente logado com o perfil pedido."""

    def logar(perfil: Perfil) -> TestClient:
        return logado_como(cria_usuario(perfil))

    return logar


@pytest.fixture
def api(api_como) -> TestClient:
    """Cliente da API logado como administrador, que pode fazer tudo."""
    return api_como(Perfil.ADMINISTRADOR)


@pytest.fixture
def novo_aluno(api) -> Callable[..., dict]:
    """Cria um aluno com responsável. Cada chamada cria um aluno diferente."""
    contador = 0

    def criar(nome: str | None = None) -> dict:
        nonlocal contador
        contador += 1
        responsavel = api.post(
            "/api/responsaveis", json={"nome": "Ana Prado", "telefone": "31977776666"}
        ).json()
        return api.post(
            "/api/alunos",
            json={
                "nome": nome or f"Aluno Teste {contador:03d}",
                "responsavel_ids": [responsavel["id"]],
            },
        ).json()

    return criar


@pytest.fixture
def matricula(api, novo_aluno) -> Callable[..., dict]:
    """Matricula um aluno novo e devolve a matrícula."""

    def criar(nome: str | None = None, **campos) -> dict:
        dados = {
            "aluno_id": novo_aluno(nome)["id"],
            "data_inicio": "2026-01-15",
            "valor_mensalidade": "150.00",
        } | campos
        resposta = api.post("/api/matriculas", json=dados)
        assert resposta.status_code == 201, resposta.text
        return resposta.json()

    return criar
