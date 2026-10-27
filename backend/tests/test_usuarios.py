import pytest

from app.core.seguranca import senha_confere
from app.models import Perfil, Usuario
from tests.conftest import SENHA_DE_TESTE

NOVO = {"nome": "Bruna Lacerda", "email": "bruna@exemplo.com", "perfil": "operador"}


def cadastra(api, **mudancas):
    dados = {**NOVO, "senha": "senha-inicial-1", **mudancas}
    return api.post("/api/usuarios", json=dados)


def edicao(usuario: Usuario, **mudancas) -> dict:
    dados = {
        "nome": usuario.nome,
        "email": usuario.email.replace(".local", ".com"),
        "perfil": usuario.perfil.value,
        "ativo": usuario.ativo,
    }
    return {**dados, **mudancas}


# ---------- Quem pode ----------


@pytest.mark.parametrize("perfil", [Perfil.OPERADOR, Perfil.CONSULTA])
def test_so_administrador_gerencia_usuarios(api_como, perfil):
    cliente = api_como(perfil)
    assert cliente.get("/api/usuarios").status_code == 403
    assert cadastra(cliente).status_code == 403


def test_gestao_de_usuarios_exige_login(sem_login):
    assert sem_login.get("/api/usuarios").status_code == 401


# ---------- Cadastro ----------


def test_cadastra_usuario_e_ele_consegue_entrar(api, sem_login, db):
    resposta = cadastra(api, email="  Bruna@Exemplo.com ")
    assert resposta.status_code == 201
    dados = resposta.json()
    assert dados["email"] == "bruna@exemplo.com"
    assert dados["perfil"] == "operador"
    assert dados["ativo"] is True
    assert "senha" not in dados and "senha_hash" not in dados

    salvo = db.get(Usuario, dados["id"])
    assert salvo.senha_hash != "senha-inicial-1"

    login = sem_login.post(
        "/api/auth/login", json={"email": "bruna@exemplo.com", "senha": "senha-inicial-1"}
    )
    assert login.status_code == 200


def test_email_repetido_vira_409(api):
    assert cadastra(api).status_code == 201
    resposta = cadastra(api, email="BRUNA@exemplo.com", nome="Outra pessoa")
    assert resposta.status_code == 409
    assert resposta.json()["detail"] == "Já existe um usuário com este e-mail"


@pytest.mark.parametrize(
    "mudanca, campo",
    [
        ({"senha": "curta"}, "senha"),
        ({"senha": "x" * 129}, "senha"),
        ({"email": "nao-e-email"}, "email"),
        ({"nome": " "}, "nome"),
        ({"nome": "Ana\x00"}, "nome"),
        ({"perfil": "dono"}, "perfil"),
    ],
)
def test_cadastro_invalido_vira_422(api, mudanca, campo):
    resposta = cadastra(api, **mudanca)
    assert resposta.status_code == 422
    assert resposta.json()["detail"][0]["loc"][-1] == campo


def test_lista_ativos_primeiro_e_em_ordem_alfabetica(api, cria_usuario):
    inativo = cria_usuario(Perfil.CONSULTA, ativo=False)
    lista = api.get("/api/usuarios").json()
    ids = [u["id"] for u in lista]
    assert ids.index(inativo.id) > max(ids.index(u["id"]) for u in lista if u["ativo"])
    ativos = [u["nome"] for u in lista if u["ativo"]]
    assert ativos == sorted(ativos)


# ---------- Edição ----------


def test_administrador_muda_perfil_e_desativa_outro(api, cria_usuario, logado_como):
    outro = cria_usuario(Perfil.OPERADOR)
    cliente_do_outro = logado_como(outro)
    assert cliente_do_outro.get("/api/alunos").status_code == 200

    resposta = api.put(f"/api/usuarios/{outro.id}", json=edicao(outro, perfil="consulta"))
    assert resposta.status_code == 200
    assert resposta.json()["perfil"] == "consulta"

    resposta = api.put(f"/api/usuarios/{outro.id}", json=edicao(outro, ativo=False))
    assert resposta.json()["ativo"] is False
    # O token que ele já tinha deixa de valer na hora
    assert cliente_do_outro.get("/api/alunos").status_code == 401


def test_administrador_nao_se_desativa_nem_muda_o_proprio_perfil(cria_usuario, logado_como):
    admin = cria_usuario(Perfil.ADMINISTRADOR)
    cliente = logado_como(admin)

    resposta = cliente.put(f"/api/usuarios/{admin.id}", json=edicao(admin, ativo=False))
    assert resposta.status_code == 422
    assert resposta.json()["detail"] == "Você não pode desativar o seu próprio usuário"

    resposta = cliente.put(f"/api/usuarios/{admin.id}", json=edicao(admin, perfil="operador"))
    assert resposta.status_code == 422
    assert resposta.json()["detail"] == "Você não pode mudar o seu próprio perfil"

    # Nome e e-mail ele pode mudar
    resposta = cliente.put(f"/api/usuarios/{admin.id}", json=edicao(admin, nome="Novo Nome"))
    assert resposta.status_code == 200
    assert resposta.json()["nome"] == "Novo Nome"


def test_edicao_nao_aceita_email_de_outro_usuario(api, cria_usuario):
    primeiro = cadastra(api).json()
    segundo = cria_usuario(Perfil.CONSULTA)
    resposta = api.put(f"/api/usuarios/{segundo.id}", json=edicao(segundo, email=primeiro["email"]))
    assert resposta.status_code == 409


def test_usuario_inexistente(api):
    assert api.get("/api/usuarios/2147483647").status_code == 404
    assert api.get("/api/usuarios/2147483648").status_code == 422
    assert api.get("/api/usuarios/0").status_code == 422


def test_usuario_nao_pode_ser_apagado(api, cria_usuario):
    outro = cria_usuario(Perfil.CONSULTA)
    assert api.delete(f"/api/usuarios/{outro.id}").status_code == 405


# ---------- Senhas ----------


def test_administrador_redefine_a_senha_de_outro(api, cria_usuario, sem_login, db):
    outro = cria_usuario(Perfil.OPERADOR)
    resposta = api.patch(f"/api/usuarios/{outro.id}/senha", json={"senha": "senha-nova-123"})
    assert resposta.status_code == 200
    db.refresh(outro)
    assert senha_confere("senha-nova-123", outro.senha_hash)
    assert not senha_confere(SENHA_DE_TESTE, outro.senha_hash)


def test_redefinir_senha_curta_vira_422(api, cria_usuario):
    outro = cria_usuario(Perfil.OPERADOR)
    resposta = api.patch(f"/api/usuarios/{outro.id}/senha", json={"senha": "1234567"})
    assert resposta.status_code == 422


@pytest.mark.parametrize("perfil", list(Perfil))
def test_qualquer_perfil_troca_a_propria_senha(cria_usuario, logado_como, db, perfil):
    usuario = cria_usuario(perfil)
    resposta = logado_como(usuario).patch(
        "/api/auth/senha", json={"senha_atual": SENHA_DE_TESTE, "nova_senha": "minha-senha-nova"}
    )
    assert resposta.status_code == 200
    db.refresh(usuario)
    assert senha_confere("minha-senha-nova", usuario.senha_hash)


def test_troca_de_senha_exige_a_senha_atual_certa(cria_usuario, logado_como, db):
    usuario = cria_usuario(Perfil.OPERADOR)
    resposta = logado_como(usuario).patch(
        "/api/auth/senha", json={"senha_atual": "chute-errado", "nova_senha": "minha-senha-nova"}
    )
    assert resposta.status_code == 422
    assert resposta.json()["detail"] == "A senha atual não confere"
    db.refresh(usuario)
    assert senha_confere(SENHA_DE_TESTE, usuario.senha_hash)


def test_troca_de_senha_exige_login(sem_login):
    resposta = sem_login.patch(
        "/api/auth/senha", json={"senha_atual": "x", "nova_senha": "minha-senha-nova"}
    )
    assert resposta.status_code == 401


def test_senha_nunca_aparece_nas_respostas(api, cria_usuario):
    cria_usuario(Perfil.CONSULTA)
    texto = api.get("/api/usuarios").text
    assert "senha" not in texto
    assert "argon2" not in texto
