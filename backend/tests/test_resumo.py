"""Resumo do mês na tela inicial (RF23): recebido, em atraso, despesas e saldo.

Os números não têm conta própria: são os do caixa do mês e os do painel de pendências. Por isso
os testes comparam o resumo com essas duas telas. Os cenários reaproveitam os ajudantes dos testes
do caixa e das pendências (tudo roda "em 15 de dezembro de 2026").
"""

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import event

from app.core import tempo
from app.db.session import engine
from app.models import Perfil
from tests import test_pendencias as pend
from tests.test_caixa import (
    MOTIVO,
    caixa,
    cobranca_paga,
    hoje_fixo,  # noqa: F401 (fixture: todos os testes rodam em 15/12/2026)
    lancar_despesa,
    lancar_receita,
    mensalidade_paga,
)


def resumo(cliente) -> dict:
    resposta = cliente.get("/api/resumo")
    assert resposta.status_code == 200, resposta.text
    return resposta.json()


def pagar_mensalidade(api, nome: str, mes: str, data: str) -> dict:
    """Paga a mensalidade do aluno naquele mês, pelo valor dela."""
    lista = api.get("/api/mensalidades", params={"mes": mes}).json()
    mensalidade = next(m for m in lista if m["aluno"]["nome"] == nome)
    resposta = api.post(
        f"/api/mensalidades/{mensalidade['id']}/pagamento",
        json={"data_pagamento": data, "valor_pago": mensalidade["valor"], "forma_pagamento": "pix"},
    )
    assert resposta.status_code == 201, resposta.text
    return resposta.json()


@pytest.fixture
def devedores(api) -> None:
    """Três alunos com mensalidades de outubro e novembro sem pagar (vencidas).

    Pedro (R$ 150,00) e os irmãos Lia e Leo (R$ 120,00 cada, mesmo responsável).
    Em atraso: 2 × 150 + 4 × 120 = 780,00 em 6 mensalidades, de 3 alunos e 2 responsáveis.
    """
    pedro = pend.aluno_em_atraso(api, "Pedro Souza", "150.00", inicio="2026-09-01")
    mae = pend.novo_responsavel(api, "Maria Lima")
    for nome in ("Lia Lima", "Leo Lima"):
        pend.aluno_em_atraso(api, nome, "120.00", responsaveis=[mae], inicio="2026-09-01")
    pend.gerar(api, "2026-10", "2026-11")
    assert pedro


@pytest.fixture
def cenario(api, devedores, novo_aluno) -> None:
    """Dezembro com todas as fontes, e dias de novembro que não podem entrar.

    Recebido em dezembro: mensalidade do Pedro 150,00 + empresa 300,00 + receita 1.000,50.
    Despesa em dezembro: 89,90. Em novembro: receita 700,00 e despesa 30,00 (fora do mês).
    Depois de pagar a mensalidade de novembro do Pedro, o atraso cai para 630,00 em 5 mensalidades.
    """
    pagar_mensalidade(api, "Pedro Souza", "2026-11", "2026-12-03")
    cobranca_paga(api, novo_aluno, data="2026-12-04", valor="300.00")
    lancar_receita(api, valor="1000.50", data="2026-12-02")
    lancar_despesa(api, valor="89.90", data="2026-12-10")
    lancar_receita(api, valor="700.00", data="2026-11-20")
    lancar_despesa(api, valor="30.00", data="2026-11-30")


# ---------- O resumo ----------


def test_sem_nenhum_movimento_o_resumo_zera_tudo(api):
    assert resumo(api) == {
        "mes": "2026-12",
        "recebido": {"total": "0.00", "quantidade": 0},
        "em_atraso": {"total": "0.00", "mensalidades": 0, "alunos": 0, "responsaveis": 0},
        "despesas": {"total": "0.00", "quantidade": 0},
        "saldo": "0.00",
    }


def test_o_resumo_do_cenario(api, cenario):
    dados = resumo(api)

    assert dados["mes"] == "2026-12"
    assert dados["recebido"] == {"total": "1450.50", "quantidade": 3}
    assert dados["despesas"] == {"total": "89.90", "quantidade": 1}
    assert dados["saldo"] == "1360.60"
    assert dados["em_atraso"] == {
        "total": "630.00",
        "mensalidades": 5,
        "alunos": 3,
        "responsaveis": 2,
    }


def test_so_conta_o_mes_atual_no_recebido_e_nas_despesas(api, cenario):
    """A receita de 700,00 e a despesa de 30,00 de novembro ficam de fora."""
    dados = resumo(api)

    assert dados["recebido"]["total"] == "1450.50"
    assert dados["despesas"]["total"] == "89.90"


@pytest.mark.parametrize(
    ("data", "conta_em_dezembro"),
    [("2026-11-30", False), ("2026-12-01", True), ("2026-12-15", True)],
)
def test_o_primeiro_dia_do_mes_entra_e_o_ultimo_do_anterior_nao(api, data, conta_em_dezembro):
    lancar_despesa(api, valor="10.00", data=data)
    lancar_receita(api, valor="20.00", data=data)

    dados = resumo(api)

    esperado = (Decimal("20.00"), Decimal("10.00")) if conta_em_dezembro else (0, 0)
    assert (Decimal(dados["recebido"]["total"]), Decimal(dados["despesas"]["total"])) == esperado


def test_o_mes_vira_com_o_relogio_de_brasilia(api, cenario, monkeypatch):
    monkeypatch.setattr(tempo, "hoje", lambda: date(2027, 1, 1))

    dados = resumo(api)

    assert dados["mes"] == "2027-01"
    assert dados["recebido"] == {"total": "0.00", "quantidade": 0}
    assert dados["despesas"] == {"total": "0.00", "quantidade": 0}


# ---------- Os mesmos números do Caixa e das Pendências (RF23) ----------


def test_recebido_despesas_e_saldo_sao_os_do_caixa_do_mes(api, cenario):
    dados = resumo(api)
    do_caixa = caixa(api, "2026-12")

    assert dados["recebido"] == do_caixa["entradas"]
    assert dados["despesas"] == do_caixa["saidas"]
    assert dados["saldo"] == do_caixa["saldo"]


def test_em_atraso_e_o_resumo_do_painel_de_pendencias(api, cenario):
    dados = resumo(api)["em_atraso"]
    painel = api.get("/api/pendencias").json()["resumo"]

    assert dados["total"] == painel["total_em_aberto"]
    assert dados["mensalidades"] == painel["mensalidades"]
    assert dados["alunos"] == painel["alunos"]
    assert dados["responsaveis"] == painel["responsaveis"]


def test_o_saldo_e_recebido_menos_despesas(api, cenario):
    dados = resumo(api)

    esperado = Decimal(dados["recebido"]["total"]) - Decimal(dados["despesas"]["total"])
    assert Decimal(dados["saldo"]) == esperado


def test_os_numeros_continuam_iguais_aos_das_telas_depois_de_mudar_o_cenario(api, cenario):
    """Cancelar, pagar e registrar mexem nos três lugares ao mesmo tempo, sempre juntos."""
    despesa = lancar_despesa(api, valor="500.00", data="2026-12-12")
    api.patch(f"/api/despesas/{despesa['id']}/cancelar", json={"motivo": MOTIVO})
    pagar_mensalidade(api, "Lia Lima", "2026-10", "2026-12-12")
    lancar_despesa(api, valor="7.10", data="2026-12-13")

    dados = resumo(api)
    do_caixa = caixa(api, "2026-12")
    painel = api.get("/api/pendencias").json()["resumo"]

    assert dados["recebido"] == do_caixa["entradas"]
    assert dados["despesas"] == do_caixa["saidas"]
    assert dados["saldo"] == do_caixa["saldo"]
    assert dados["em_atraso"]["total"] == painel["total_em_aberto"] == "510.00"


# ---------- Em atraso ----------


def test_em_atraso_junta_todos_os_meses_e_nao_so_o_atual(api, devedores):
    """As mensalidades de outubro e novembro contam, mesmo estando em dezembro."""
    dados = resumo(api)["em_atraso"]

    assert dados == {"total": "780.00", "mensalidades": 6, "alunos": 3, "responsaveis": 2}


def test_irmaos_com_o_mesmo_responsavel_contam_uma_pessoa_so(api, devedores):
    assert resumo(api)["em_atraso"]["responsaveis"] == 2


def test_pagar_tira_a_mensalidade_do_atraso_e_poe_no_recebido(api, devedores):
    pagar_mensalidade(api, "Lia Lima", "2026-10", "2026-12-05")

    dados = resumo(api)

    assert dados["em_atraso"] == {
        "total": "660.00",
        "mensalidades": 5,
        "alunos": 3,
        "responsaveis": 2,
    }
    assert dados["recebido"] == {"total": "120.00", "quantidade": 1}


def test_isenta_e_cancelada_nao_estao_em_atraso(api, devedores):
    lista = api.get("/api/mensalidades", params={"mes": "2026-10"}).json()
    ids = {m["aluno"]["nome"]: m["id"] for m in lista}
    api.patch(f"/api/mensalidades/{ids['Pedro Souza']}/isentar", json={"motivo": "Recesso"})
    api.patch(f"/api/mensalidades/{ids['Lia Lima']}/cancelar", json={"motivo": "Gerada errada"})

    assert resumo(api)["em_atraso"]["total"] == "510.00"


def test_a_cobranca_da_empresa_nao_entra_no_atraso_dos_responsaveis(api, novo_aluno):
    """A empresa tem a tela dela: os apadrinhados não devem ao responsável."""
    cobranca_paga(api, novo_aluno, data="2026-12-04", valor="300.00")

    dados = resumo(api)

    assert dados["em_atraso"]["total"] == "0.00"
    assert dados["recebido"]["total"] == "300.00"


@pytest.mark.parametrize(("hoje", "em_atraso"), [(15, "0.00"), (16, "150.00")])
def test_no_dia_do_vencimento_ainda_nao_esta_atrasada(api, monkeypatch, hoje, em_atraso):
    """RN07: até o dia 15 está a vencer; a partir do dia 16, atrasada."""
    pend.aluno_em_atraso(api, "Pedro Souza", "150.00", inicio="2026-11-01")
    monkeypatch.setattr(tempo, "hoje", lambda: date(2026, 11, hoje))
    pend.gerar(api, "2026-11")

    assert resumo(api)["em_atraso"]["total"] == em_atraso


# ---------- Cancelados (RN12) e saldo negativo ----------


def test_cancelado_sai_do_resumo_e_do_saldo(api, cenario):
    errado = lancar_despesa(api, valor="500.00", data="2026-12-12")
    antes = resumo(api)
    assert antes["despesas"]["total"] == "589.90"

    api.patch(f"/api/despesas/{errado['id']}/cancelar", json={"motivo": MOTIVO})

    depois = resumo(api)
    assert depois["despesas"] == {"total": "89.90", "quantidade": 1}
    assert depois["saldo"] == "1360.60"


def test_pagamento_cancelado_sai_do_recebido_e_a_mensalidade_volta_ao_atraso(api, matricula):
    pago = mensalidade_paga(api, matricula, "Ana Lima", competencia="2026-10", data="2026-12-05")
    assert resumo(api)["recebido"]["total"] == "150.00"
    assert resumo(api)["em_atraso"]["total"] == "0.00"

    api.patch(f"/api/mensalidades/{pago['id']}/pagamento/cancelar", json={"motivo": MOTIVO})

    dados = resumo(api)
    assert dados["recebido"] == {"total": "0.00", "quantidade": 0}
    assert dados["em_atraso"]["total"] == "150.00"


def test_saldo_negativo_sai_com_o_sinal(api):
    lancar_receita(api, valor="50.00", data="2026-12-02")
    lancar_despesa(api, valor="80.25", data="2026-12-03")

    dados = resumo(api)

    assert dados["saldo"] == "-30.25"
    assert Decimal(dados["saldo"]) < 0


def test_centavos_somam_sem_erro_de_arredondamento(api):
    for valor in ("0.10", "0.20", "0.30"):
        lancar_despesa(api, valor=valor, data="2026-12-02")

    assert resumo(api)["despesas"]["total"] == "0.60"


# ---------- Perfis, métodos e privacidade ----------


def test_sem_login_nao_acessa(sem_login):
    assert sem_login.get("/api/resumo").status_code == 401
    assert sem_login.get("/api/resumo", headers={"Authorization": "Bearer x"}).status_code == 401


@pytest.mark.parametrize("perfil", list(Perfil))
def test_todos_os_perfis_veem_o_resumo(api, api_como, devedores, perfil):
    lancar_despesa(api, valor="10.00", data="2026-12-02")

    dados = resumo(api_como(perfil))

    assert dados["despesas"]["total"] == "10.00"
    assert dados["em_atraso"]["total"] == "780.00"


@pytest.mark.parametrize("metodo", ["POST", "PUT", "PATCH", "DELETE"])
def test_o_resumo_so_pode_ser_lido(api, metodo):
    assert api.request(metodo, "/api/resumo", json={}).status_code == 405


def test_o_resumo_ignora_parametros_de_mes(api, cenario):
    """Ele é sempre o do mês atual: não há como pedir outro."""
    com_parametro = api.get("/api/resumo", params={"mes": "2026-10"}).json()

    assert com_parametro == resumo(api)


def test_a_resposta_so_traz_totais_sem_dados_pessoais(api, cenario):
    dados = resumo(api)

    assert set(dados) == {"mes", "recebido", "em_atraso", "despesas", "saldo"}
    assert set(dados["em_atraso"]) == {"total", "mensalidades", "alunos", "responsaveis"}
    texto = str(dados)
    for proibido in (
        "Pedro",
        "Lia",
        "Leo",
        "Maria",
        "Sartori",
        "Loja",
        "Mineração",
        "@",
        "Usuário",
    ):
        assert proibido not in texto


def test_nao_cria_nem_altera_nada_ao_consultar(api, cenario):
    antes = caixa(api, "2026-12")
    painel = api.get("/api/pendencias").json()

    for _ in range(3):
        resumo(api)

    assert caixa(api, "2026-12") == antes
    assert api.get("/api/pendencias").json() == painel


# ---------- Desempenho: não faz uma consulta por lançamento nem por aluno ----------


def contar_consultas(api) -> int:
    total = 0

    def conta(*_):
        nonlocal total
        total += 1

    event.listen(engine, "before_cursor_execute", conta)
    try:
        assert api.get("/api/resumo").status_code == 200
    finally:
        event.remove(engine, "before_cursor_execute", conta)
    return total


def test_o_numero_de_consultas_nao_depende_do_que_foi_lancado(api):
    pend.aluno_em_atraso(api, "Aluno 00", inicio="2026-09-01")
    pend.gerar(api, "2026-10")
    lancar_despesa(api, valor="1.00", data="2026-12-02")
    com_pouco = contar_consultas(api)

    for i in range(1, 8):
        pend.aluno_em_atraso(api, f"Aluno {i:02d}", inicio="2026-09-01")
        lancar_despesa(api, valor="1.00", data="2026-12-03", descricao=f"Despesa {i}")
        lancar_receita(api, valor="2.00", data="2026-12-04", origem=f"Origem {i}")
    pend.gerar(api, "2026-10", "2026-11")
    com_muito = contar_consultas(api)

    assert com_muito == com_pouco
