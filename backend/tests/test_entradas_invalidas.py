"""Entradas que antes viravam erro 500 e agora precisam ser recusadas com 404 ou 422."""

import json

import pytest

ID_GIGANTE = 99_999_999_999


@pytest.fixture
def responsavel(api):
    return api.post(
        "/api/responsaveis", json={"nome": "Ana Lima", "email": "ana@exemplo.com"}
    ).json()


@pytest.mark.parametrize("rota", ["/api/alunos", "/api/responsaveis"])
def test_id_gigante_na_rota_e_recusado(api, rota):
    assert api.get(f"{rota}/{ID_GIGANTE}").status_code == 422


def test_id_gigante_ao_editar_aluno_e_recusado(api, responsavel):
    dados = {"nome": "Pedro Lima", "responsavel_ids": [responsavel["id"]]}
    assert api.put(f"/api/alunos/{ID_GIGANTE}", json=dados).status_code == 422


def test_id_gigante_de_responsavel_e_recusado(api):
    dados = {"nome": "Pedro Lima", "responsavel_ids": [ID_GIGANTE]}
    assert api.post("/api/alunos", json=dados).status_code == 422


@pytest.mark.parametrize("campo", ["nome", "escola", "municipio"])
def test_aluno_com_caractere_nulo_e_recusado(api, responsavel, campo):
    dados = {"nome": "Pedro Lima", "responsavel_ids": [responsavel["id"]]}
    dados[campo] = "Texto\x00com nulo"
    assert api.post("/api/alunos", json=dados).status_code == 422


@pytest.mark.parametrize(
    "dados",
    [
        {"nome": "Ana\x00 Lima", "email": "ana@exemplo.com"},
        {"nome": "Ana Lima", "telefone": "31988887777\x00"},
        {"nome": "Ana Lima", "email": "ana\x00@exemplo.com"},
    ],
)
def test_responsavel_com_caractere_nulo_e_recusado(api, dados):
    assert api.post("/api/responsaveis", json=dados).status_code == 422


def test_aluno_com_unicode_invalido_e_recusado(api, responsavel):
    # json.dumps escreve o pedaço solto como \\ud800, do jeito que chegaria de um navegador
    corpo = json.dumps({"nome": "Pedro \ud800 Lima", "responsavel_ids": [responsavel["id"]]})
    resposta = api.post("/api/alunos", content=corpo, headers={"Content-Type": "application/json"})
    assert resposta.status_code == 422


def test_responsavel_com_unicode_invalido_e_recusado(api):
    corpo = json.dumps({"nome": "Ana \ud800 Lima", "email": "ana@exemplo.com"})
    resposta = api.post(
        "/api/responsaveis", content=corpo, headers={"Content-Type": "application/json"}
    )
    assert resposta.status_code == 422


@pytest.mark.parametrize("rota", ["/api/alunos", "/api/responsaveis"])
def test_caractere_nulo_na_busca_e_ignorado(api, rota):
    assert api.get(rota, params={"busca": "a\x00b"}).status_code == 200
