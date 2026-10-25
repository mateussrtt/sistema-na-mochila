"""Ao inativar o aluno, a matrícula ativa dele é encerrada junto."""

from datetime import date, timedelta

import pytest


@pytest.fixture
def responsavel(api):
    return api.post(
        "/api/responsaveis", json={"nome": "Maria Souza", "telefone": "31988887777"}
    ).json()


@pytest.fixture
def aluno(api, responsavel):
    dados = {"nome": "Pedro Souza", "responsavel_ids": [responsavel["id"]]}
    return api.post("/api/alunos", json=dados).json()


def matricular(api, aluno_id, data_inicio="2026-01-15"):
    dados = {"aluno_id": aluno_id, "data_inicio": data_inicio, "valor_mensalidade": "150.00"}
    return api.post("/api/matriculas", json=dados).json()


def mudar_situacao(api, aluno, responsavel, ativo):
    dados = {"nome": aluno["nome"], "responsavel_ids": [responsavel["id"]], "ativo": ativo}
    return api.put(f"/api/alunos/{aluno['id']}", json=dados)


def test_inativar_aluno_encerra_a_matricula_ativa(api, aluno, responsavel):
    matricula = matricular(api, aluno["id"])

    assert mudar_situacao(api, aluno, responsavel, ativo=False).status_code == 200

    encerrada = api.get(f"/api/matriculas/{matricula['id']}").json()
    assert encerrada["situacao"] == "encerrada"
    assert encerrada["data_encerramento"] == date.today().isoformat()


def test_matricula_que_ainda_nao_comecou_encerra_na_data_de_inicio(api, aluno, responsavel):
    inicio = (date.today() + timedelta(days=20)).isoformat()
    matricula = matricular(api, aluno["id"], data_inicio=inicio)

    mudar_situacao(api, aluno, responsavel, ativo=False)

    assert api.get(f"/api/matriculas/{matricula['id']}").json()["data_encerramento"] == inicio


def test_inativar_aluno_sem_matricula_continua_funcionando(api, aluno, responsavel):
    resposta = mudar_situacao(api, aluno, responsavel, ativo=False)
    assert resposta.status_code == 200
    assert resposta.json()["ativo"] is False


def test_reativar_aluno_nao_reabre_a_matricula(api, aluno, responsavel):
    matricula = matricular(api, aluno["id"])
    mudar_situacao(api, aluno, responsavel, ativo=False)

    mudar_situacao(api, aluno, responsavel, ativo=True)

    assert api.get(f"/api/matriculas/{matricula['id']}").json()["situacao"] == "encerrada"
    nova = api.post(
        "/api/matriculas",
        json={"aluno_id": aluno["id"], "data_inicio": "2026-10-01", "valor_mensalidade": "150"},
    )
    assert nova.status_code == 201


def test_editar_aluno_ativo_nao_mexe_na_matricula(api, aluno, responsavel):
    matricula = matricular(api, aluno["id"])

    mudar_situacao(api, aluno, responsavel, ativo=True)

    assert api.get(f"/api/matriculas/{matricula['id']}").json()["situacao"] == "ativa"
