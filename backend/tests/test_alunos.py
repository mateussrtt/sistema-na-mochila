import pytest


@pytest.fixture
def responsavel(api):
    return api.post(
        "/api/responsaveis", json={"nome": "Maria Souza", "telefone": "31988887777"}
    ).json()


def novo_aluno(api, responsavel_ids, **campos):
    dados = {"nome": "Pedro Souza", "responsavel_ids": responsavel_ids} | campos
    return api.post("/api/alunos", json=dados)


def test_cadastra_aluno_com_responsavel(api, responsavel):
    resposta = novo_aluno(api, [responsavel["id"]], escola="E. E. Central", municipio="Itabira")
    assert resposta.status_code == 201
    aluno = resposta.json()
    assert aluno["ativo"] is True
    assert [r["nome"] for r in aluno["responsaveis"]] == ["Maria Souza"]


def test_aluno_exige_responsavel(api):
    assert novo_aluno(api, []).status_code == 422


def test_aluno_exige_nome(api, responsavel):
    assert novo_aluno(api, [responsavel["id"]], nome=" ").status_code == 422


def test_aluno_rejeita_responsavel_inexistente(api):
    assert novo_aluno(api, [999999]).status_code == 422


def test_aluno_rejeita_nascimento_no_futuro(api, responsavel):
    resposta = novo_aluno(api, [responsavel["id"]], data_nascimento="2999-01-01")
    assert resposta.status_code == 422


def test_responsavel_com_varios_alunos(api, responsavel):
    novo_aluno(api, [responsavel["id"]], nome="Pedro Souza")
    novo_aluno(api, [responsavel["id"]], nome="Laura Souza")
    alunos = api.get("/api/alunos", params={"busca": "souza"}).json()
    assert {a["nome"] for a in alunos} == {"Pedro Souza", "Laura Souza"}


def test_busca_aluno_pelo_nome_do_responsavel(api):
    resp = api.post("/api/responsaveis", json={"nome": "Roberta Dias", "email": "r@exemplo.com"})
    novo_aluno(api, [resp.json()["id"]], nome="Lucas Ferreira")
    nomes = [a["nome"] for a in api.get("/api/alunos", params={"busca": "roberta"}).json()]
    assert nomes == ["Lucas Ferreira"]


def test_inativa_aluno(api, responsavel):
    aluno = novo_aluno(api, [responsavel["id"]]).json()
    dados = {"nome": aluno["nome"], "responsavel_ids": [responsavel["id"]], "ativo": False}
    assert api.put(f"/api/alunos/{aluno['id']}", json=dados).json()["ativo"] is False

    ativos = [a["id"] for a in api.get("/api/alunos").json()]
    inativos = [a["id"] for a in api.get("/api/alunos", params={"situacao": "inativos"}).json()]
    assert aluno["id"] not in ativos
    assert aluno["id"] in inativos


def test_aluno_inexistente(api):
    assert api.get("/api/alunos/999999").status_code == 404
