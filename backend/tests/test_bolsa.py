from decimal import Decimal

import pytest
from sqlalchemy.exc import IntegrityError

from app.models import Bolsa, Matricula


@pytest.fixture
def novo_aluno(api):
    """Cria um aluno com responsável. Cada chamada cria um aluno diferente."""

    def criar(nome: str = "Lucas Prado") -> dict:
        responsavel = api.post(
            "/api/responsaveis", json={"nome": "Ana Prado", "telefone": "31977776666"}
        ).json()
        return api.post(
            "/api/alunos", json={"nome": nome, "responsavel_ids": [responsavel["id"]]}
        ).json()

    return criar


def matricular(api, aluno_id, **campos):
    dados = {"aluno_id": aluno_id, "data_inicio": "2026-03-01"} | campos
    return api.post("/api/matriculas", json=dados)


def test_sem_informar_bolsa_a_matricula_fica_sem_bolsa(api, novo_aluno):
    resposta = matricular(api, novo_aluno()["id"], valor_mensalidade="150.00")
    assert resposta.status_code == 201
    assert resposta.json()["bolsa"] == "nenhuma"


def test_bolsa_integral_tem_mensalidade_zero(api, novo_aluno):
    resposta = matricular(api, novo_aluno()["id"], bolsa="integral")
    assert resposta.status_code == 201
    dados = resposta.json()
    assert dados["bolsa"] == "integral"
    assert dados["valor_mensalidade"] == "0.00"


@pytest.mark.parametrize("valor", ["0", "0,00", ""])
def test_bolsa_integral_aceita_valor_zero_ou_em_branco(api, novo_aluno, valor):
    resposta = matricular(api, novo_aluno()["id"], bolsa="integral", valor_mensalidade=valor)
    assert resposta.status_code == 201


def test_bolsa_integral_nao_aceita_valor_cobrado(api, novo_aluno):
    resposta = matricular(api, novo_aluno()["id"], bolsa="integral", valor_mensalidade="80")
    assert resposta.status_code == 422
    erro = resposta.json()["detail"][0]
    assert erro["loc"][-1] == "valor_mensalidade"
    assert "bolsa integral" in erro["msg"]


def test_bolsa_parcial_guarda_o_valor_com_desconto(api, novo_aluno):
    resposta = matricular(api, novo_aluno()["id"], bolsa="parcial", valor_mensalidade="75,50")
    assert resposta.status_code == 201
    assert resposta.json()["valor_mensalidade"] == "75.50"


@pytest.mark.parametrize("bolsa", ["nenhuma", "parcial"])
@pytest.mark.parametrize("valor", ["0", ""])
def test_sem_bolsa_integral_o_valor_precisa_ser_positivo(api, novo_aluno, bolsa, valor):
    resposta = matricular(api, novo_aluno()["id"], bolsa=bolsa, valor_mensalidade=valor)
    assert resposta.status_code == 422
    assert resposta.json()["detail"][0]["loc"][-1] == "valor_mensalidade"


@pytest.mark.parametrize("bolsa", ["total", "", None, 1])
def test_tipo_de_bolsa_invalido_vira_422(api, novo_aluno, bolsa):
    resposta = matricular(api, novo_aluno()["id"], bolsa=bolsa, valor_mensalidade="100")
    assert resposta.status_code == 422


def test_filtro_mostra_so_bolsistas(api, novo_aluno):
    pagante = matricular(api, novo_aluno("Pagante")["id"], valor_mensalidade="150")
    parcial = matricular(api, novo_aluno("Parcial")["id"], bolsa="parcial", valor_mensalidade="70")
    integral = matricular(api, novo_aluno("Integral")["id"], bolsa="integral")

    ids = {m["id"] for m in api.get("/api/matriculas?so_bolsistas=true").json()}
    assert parcial.json()["id"] in ids
    assert integral.json()["id"] in ids
    assert pagante.json()["id"] not in ids


@pytest.mark.parametrize(
    "bolsa, valor",
    [
        (Bolsa.INTEGRAL, Decimal("50.00")),
        (Bolsa.NENHUMA, Decimal("0.00")),
        (Bolsa.PARCIAL, Decimal("0.00")),
    ],
)
def test_banco_recusa_valor_que_nao_combina_com_a_bolsa(db, novo_aluno, bolsa, valor):
    aluno = novo_aluno()
    db.add(
        Matricula(
            aluno_id=aluno["id"], data_inicio="2026-03-01", valor_mensalidade=valor, bolsa=bolsa
        )
    )
    with pytest.raises(IntegrityError):
        db.flush()
