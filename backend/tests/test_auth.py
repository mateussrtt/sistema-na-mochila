from datetime import UTC, datetime, timedelta

import pytest

from app.core.seguranca import criar_token
from app.models import Perfil
from tests.conftest import SENHA_DE_TESTE

# ---------- Login ----------


def test_login_devolve_token_e_usuario(sem_login, cria_usuario):
    usuario = cria_usuario(Perfil.OPERADOR)
    resposta = sem_login.post(
        "/api/auth/login", json={"email": usuario.email, "senha": SENHA_DE_TESTE}
    )
    assert resposta.status_code == 200
    dados = resposta.json()
    assert dados["token"]
    assert dados["usuario"]["perfil"] == "operador"
    assert "senha_hash" not in dados["usuario"]


def test_login_ignora_maiusculas_e_espacos_no_email(sem_login, cria_usuario):
    usuario = cria_usuario()
    email = f"  {usuario.email.upper()} "
    resposta = sem_login.post("/api/auth/login", json={"email": email, "senha": SENHA_DE_TESTE})
    assert resposta.status_code == 200


@pytest.mark.parametrize(
    "email, senha",
    [
        ("administrador1@teste.local", "senha-errada"),
        ("nao-existe@teste.local", SENHA_DE_TESTE),
    ],
)
def test_login_invalido_nao_revela_qual_campo_errou(sem_login, cria_usuario, email, senha):
    cria_usuario()
    resposta = sem_login.post("/api/auth/login", json={"email": email, "senha": senha})
    assert resposta.status_code == 401
    assert resposta.json()["detail"] == "E-mail ou senha incorretos"


def test_usuario_desativado_nao_consegue_entrar(sem_login, cria_usuario):
    usuario = cria_usuario(ativo=False)
    resposta = sem_login.post(
        "/api/auth/login", json={"email": usuario.email, "senha": SENHA_DE_TESTE}
    )
    assert resposta.status_code == 401
    assert resposta.json()["detail"] == "E-mail ou senha incorretos"


def test_eu_devolve_quem_esta_logado(api_como):
    resposta = api_como(Perfil.CONSULTA).get("/api/auth/eu")
    assert resposta.status_code == 200
    assert resposta.json()["perfil"] == "consulta"


# ---------- Token ----------


@pytest.mark.parametrize("rota", ["/api/alunos", "/api/responsaveis", "/api/matriculas"])
def test_rotas_exigem_login(sem_login, rota):
    resposta = sem_login.get(rota)
    assert resposta.status_code == 401
    assert resposta.json()["detail"] == "Faça login para continuar"


def test_token_invalido_e_recusado(sem_login):
    resposta = sem_login.get("/api/alunos", headers={"Authorization": "Bearer token-inventado"})
    assert resposta.status_code == 401


def test_token_vencido_e_recusado(sem_login, cria_usuario):
    usuario = cria_usuario()
    ontem = datetime.now(UTC) - timedelta(days=1)
    token = criar_token(usuario.id, agora=ontem)
    resposta = sem_login.get("/api/alunos", headers={"Authorization": f"Bearer {token}"})
    assert resposta.status_code == 401


def test_token_de_usuario_desativado_deixa_de_valer(sem_login, cria_usuario, db):
    usuario = cria_usuario()
    token = criar_token(usuario.id)
    usuario.ativo = False
    db.flush()
    resposta = sem_login.get("/api/alunos", headers={"Authorization": f"Bearer {token}"})
    assert resposta.status_code == 401


def test_saude_e_documentacao_continuam_abertas(sem_login):
    assert sem_login.get("/api/health").status_code == 200
    assert sem_login.get("/docs").status_code == 200


# ---------- Perfis ----------


@pytest.mark.parametrize("perfil", list(Perfil))
def test_todos_os_perfis_podem_consultar(api_como, perfil):
    assert api_como(perfil).get("/api/alunos").status_code == 200


def test_consulta_nao_pode_cadastrar(api_como):
    cliente = api_como(Perfil.CONSULTA)
    resposta = cliente.post("/api/responsaveis", json={"nome": "Ana", "email": "ana@ex.com"})
    assert resposta.status_code == 403
    assert resposta.json()["detail"] == "Seu perfil não pode fazer isso"


@pytest.mark.parametrize("perfil", [Perfil.OPERADOR, Perfil.ADMINISTRADOR])
def test_operador_e_administrador_podem_cadastrar(api_como, perfil):
    cliente = api_como(perfil)
    resposta = cliente.post("/api/responsaveis", json={"nome": "Ana", "email": "ana@ex.com"})
    assert resposta.status_code == 201


def test_login_com_caractere_nulo_nao_da_erro_500(sem_login):
    resposta = sem_login.post("/api/auth/login", json={"email": "a\x00@b.com", "senha": "x"})
    assert resposta.status_code == 422
