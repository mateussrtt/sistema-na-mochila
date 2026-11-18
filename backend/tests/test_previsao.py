"""Previsão de receita (RF21, RF22, RN11): mensalidades das matrículas em vigor em cada mês.

Os testes rodam "em 17 de novembro de 2026": o mês atual é novembro, e os 12 meses vão de
novembro de 2026 a outubro de 2027.
"""

from datetime import date
from decimal import Decimal

import pytest

from app.core import tempo
from app.core.previsao import MatriculaPrevista, previsto_no_mes
from app.models import Perfil
from app.models.matricula import Bolsa
from tests import test_cobrancas as cobrancas

HOJE = date(2026, 11, 17)
NOVEMBRO = date(2026, 11, 1)


@pytest.fixture(autouse=True)
def hoje_fixo(monkeypatch):
    monkeypatch.setattr(tempo, "hoje", lambda: HOJE)


def previsao(cliente) -> dict:
    resposta = cliente.get("/api/previsao")
    assert resposta.status_code == 200, resposta.text
    return resposta.json()


def por_mes(dados: dict) -> dict[str, tuple[str, int]]:
    """{"2026-11": ("300.00", 2), ...}: o previsto e quantos alunos pagam, em cada mês."""
    return {m["mes"][:7]: (m["previsto"], m["alunos"]) for m in dados["meses"]}


def pagar(api, mensalidade_id: int, valor="150.00"):
    resposta = api.post(
        f"/api/mensalidades/{mensalidade_id}/pagamento",
        json={
            "data_pagamento": "2026-11-10",
            "valor_pago": valor,
            "forma_pagamento": "pix",
            "observacao": "Pagou junto a camiseta do time",
        },
    )
    assert resposta.status_code == 201, resposta.text


def mensalidades_de_novembro(api) -> dict[str, dict]:
    cobrancas.gerar(api, "2026-11")
    lista = api.get("/api/mensalidades", params={"mes": "2026-11"}).json()
    return {m["aluno"]["nome"]: m for m in lista}


# ---------- A regra do mês (função pura) ----------


def m(id, aluno, inicio, valor="150.00", fim=None, bolsa=Bolsa.NENHUMA) -> MatriculaPrevista:
    return MatriculaPrevista(id, aluno, inicio, fim, Decimal(valor), bolsa)


def test_soma_as_mensalidades_das_matriculas_em_vigor():
    mes = previsto_no_mes([m(1, 1, date(2026, 1, 1)), m(2, 2, date(2026, 3, 5), "90.50")], NOVEMBRO)
    assert (mes.previsto, mes.alunos) == (Decimal("240.50"), 2)


def test_matricula_que_comeca_no_ultimo_dia_do_mes_ja_conta():
    mes = previsto_no_mes([m(1, 1, date(2026, 11, 30))], NOVEMBRO)
    assert mes.alunos == 1


def test_matricula_que_so_comeca_no_mes_seguinte_nao_conta():
    mes = previsto_no_mes([m(1, 1, date(2026, 12, 1))], NOVEMBRO)
    assert (mes.previsto, mes.alunos) == (Decimal("0.00"), 0)


def test_encerrada_no_meio_do_mes_ainda_conta_nesse_mes():
    mes = previsto_no_mes([m(1, 1, date(2026, 1, 1), fim=date(2026, 11, 1))], NOVEMBRO)
    assert mes.alunos == 1


def test_encerrada_antes_do_mes_nao_conta():
    mes = previsto_no_mes([m(1, 1, date(2026, 1, 1), fim=date(2026, 10, 31))], NOVEMBRO)
    assert mes.alunos == 0


@pytest.mark.parametrize("bolsa", [Bolsa.INTEGRAL, Bolsa.APADRINHADA])
def test_quem_nao_paga_a_mensalidade_fica_de_fora(bolsa):
    valor = "0.00" if bolsa == Bolsa.INTEGRAL else "150.00"
    mes = previsto_no_mes([m(1, 1, date(2026, 1, 1), valor, bolsa=bolsa)], NOVEMBRO)
    assert mes.alunos == 0


def test_bolsa_parcial_entra_pelo_valor_da_matricula():
    mes = previsto_no_mes([m(1, 1, date(2026, 1, 1), "75.00", bolsa=Bolsa.PARCIAL)], NOVEMBRO)
    assert mes.previsto == Decimal("75.00")


def test_aluno_que_saiu_e_voltou_no_mes_conta_uma_vez_pela_matricula_mais_recente():
    saiu = m(1, 1, date(2026, 1, 1), "150.00", fim=date(2026, 11, 5))
    voltou = m(2, 1, date(2026, 11, 20), "120.00")
    mes = previsto_no_mes([saiu, voltou], NOVEMBRO)
    assert (mes.previsto, mes.alunos) == (Decimal("120.00"), 1)


def test_se_a_matricula_mais_recente_tem_bolsa_integral_o_aluno_nao_paga_no_mes():
    saiu = m(1, 1, date(2026, 1, 1), fim=date(2026, 11, 5))
    voltou = m(2, 1, date(2026, 11, 6), "0.00", bolsa=Bolsa.INTEGRAL)
    assert previsto_no_mes([saiu, voltou], NOVEMBRO).alunos == 0


# ---------- A rota ----------


def test_sem_matriculas_a_previsao_e_zero(api):
    dados = previsao(api)
    assert dados["atual"] == {
        "mes": "2026-11-01",
        "previsto": "0.00",
        "alunos": 0,
        "recebido": "0.00",
        "dispensado": "0.00",
        "falta": "0.00",
    }
    assert len(dados["meses"]) == 12
    assert dados["total"] == "0.00"


def test_os_12_meses_vao_do_mes_atual_ate_11_meses_depois(api):
    meses = [m["mes"] for m in previsao(api)["meses"]]
    assert meses[0] == "2026-11-01"
    assert meses[1] == "2026-12-01"
    assert meses[2] == "2027-01-01"
    assert meses[-1] == "2027-10-01"


def test_previsao_do_mes_e_dos_12_meses(api, matricula):
    matricula("Ana Lima", valor_mensalidade="150.00")
    matricula("Bruno Dias", valor_mensalidade="120.00", bolsa="parcial")
    matricula("Caio Reis", valor_mensalidade="0.00", bolsa="integral")

    dados = previsao(api)

    assert (dados["atual"]["previsto"], dados["atual"]["alunos"]) == ("270.00", 2)
    assert set(por_mes(dados).values()) == {("270.00", 2)}
    assert dados["total"] == "3240.00"


def test_matricula_futura_entra_a_partir_do_mes_dela(api, matricula):
    matricula("Ana Lima")
    matricula("Bruno Dias", data_inicio="2027-02-01", valor_mensalidade="100.00")

    meses = por_mes(previsao(api))

    assert meses["2027-01"] == ("150.00", 1)
    assert meses["2027-02"] == ("250.00", 2)
    assert meses["2027-10"] == ("250.00", 2)


def test_previsao_muda_na_hora_ao_matricular_e_ao_encerrar(api, matricula):
    ana = matricula("Ana Lima")
    assert previsao(api)["atual"]["alunos"] == 1

    matricula("Bruno Dias")
    assert previsao(api)["atual"]["alunos"] == 2

    resposta = api.patch(
        f"/api/matriculas/{ana['id']}/encerrar", json={"data_encerramento": "2026-11-10"}
    )
    assert resposta.status_code == 200, resposta.text
    meses = por_mes(previsao(api))
    # Saiu em novembro: ainda paga novembro, mas não dezembro em diante
    assert meses["2026-11"] == ("300.00", 2)
    assert meses["2026-12"] == ("150.00", 1)


def test_patrocinios_e_doacoes_nao_entram_na_previsao(api, matricula):
    matricula("Ana Lima")
    categoria = api.get("/api/categorias-receita").json()[0]["id"]
    resposta = api.post(
        "/api/receitas",
        json={
            "data_receita": "2026-11-10",
            "valor": "5000.00",
            "categoria_id": categoria,
            "origem": "Mineração Vale Verde",
        },
    )
    assert resposta.status_code == 201, resposta.text

    dados = previsao(api)
    assert (dados["atual"]["previsto"], dados["atual"]["recebido"]) == ("150.00", "0.00")


def test_aluno_apadrinhado_nao_entra_por_aqui(api, novo_aluno, matricula):
    """O valor dos apadrinhados vem da cobrança da empresa (#22), não do responsável."""
    matricula("Ana Lima")
    cobrancas.apadrinhar(api, novo_aluno("Bruno Dias"), cobrancas.novo_padrinho(api))
    assert previsao(api)["atual"]["alunos"] == 1


# ---------- O mês atual: recebido e o que falta ----------


def test_no_mes_atual_mostra_o_recebido_e_o_que_falta(api, matricula):
    matricula("Ana Lima")
    matricula("Bruno Dias")
    pagar(api, mensalidades_de_novembro(api)["Ana Lima"]["id"])

    atual = previsao(api)["atual"]

    assert (atual["previsto"], atual["recebido"], atual["falta"]) == ("300.00", "150.00", "150.00")


def test_mensalidade_ainda_nao_gerada_conta_como_falta(api, matricula):
    matricula("Ana Lima")
    assert previsao(api)["atual"]["falta"] == "150.00"


def test_pagamento_cancelado_volta_a_faltar(api, matricula):
    matricula("Ana Lima")
    mensalidade = mensalidades_de_novembro(api)["Ana Lima"]
    pagar(api, mensalidade["id"])
    api.patch(
        f"/api/mensalidades/{mensalidade['id']}/pagamento/cancelar",
        json={"motivo": "Lançado no aluno errado"},
    )

    atual = previsao(api)["atual"]
    assert (atual["recebido"], atual["falta"]) == ("0.00", "150.00")


def test_mensalidade_isenta_nao_falta(api, matricula):
    matricula("Ana Lima")
    matricula("Bruno Dias")
    mensalidade = mensalidades_de_novembro(api)["Bruno Dias"]
    resposta = api.patch(
        f"/api/mensalidades/{mensalidade['id']}/isentar", json={"motivo": "Combinado com a família"}
    )
    assert resposta.status_code == 200, resposta.text

    atual = previsao(api)["atual"]
    assert (atual["dispensado"], atual["falta"]) == ("150.00", "150.00")


def test_pagar_a_mais_nao_deixa_falta_negativa(api, matricula):
    matricula("Ana Lima")
    pagar(api, mensalidades_de_novembro(api)["Ana Lima"]["id"], valor="200.00")

    atual = previsao(api)["atual"]
    assert (atual["recebido"], atual["falta"]) == ("200.00", "0.00")


def test_pagamento_de_outro_mes_nao_conta_no_recebido_de_novembro(api, matricula):
    """O recebido é o das mensalidades de novembro, não o dinheiro que entrou em novembro."""
    matricula("Ana Lima", data_inicio="2026-10-01")
    cobrancas.gerar(api, "2026-10")
    [outubro] = api.get("/api/mensalidades", params={"mes": "2026-10"}).json()
    pagar(api, outubro["id"])

    assert previsao(api)["atual"]["recebido"] == "0.00"


# ---------- Quem vê ----------


@pytest.mark.parametrize("perfil", list(Perfil))
def test_todos_os_perfis_veem_a_previsao(api_como, perfil):
    assert api_como(perfil).get("/api/previsao").status_code == 200


def test_previsao_exige_login(sem_login):
    assert sem_login.get("/api/previsao").status_code == 401


def test_a_previsao_nao_traz_dados_pessoais(api, matricula):
    matricula("Ana Lima")
    assert "Ana" not in str(previsao(api))
