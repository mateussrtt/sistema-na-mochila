"""Saldo do mês (RF19, RN10, RNF14): entradas menos saídas, pela data em que o dinheiro mexeu.

Entradas: pagamentos de mensalidade, pagamentos das empresas padrinhas e receitas avulsas.
Saídas: despesas. Lançamento cancelado fica de fora, e o que foi corrigido conta uma vez só.
"""

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import event, select

from app.core import tempo
from app.core.saldo import calcular_saldo, somar
from app.db.session import engine
from app.models import Despesa, Pagamento, PagamentoCobranca, Perfil, Receita
from tests import test_cobrancas as cobrancas

HOJE = date(2026, 12, 15)
MOTIVO = "Lançado em dobro por engano"


@pytest.fixture(autouse=True)
def hoje_fixo(monkeypatch):
    """Os testes rodam "em 15 de dezembro de 2026", para não dependerem do dia em que rodam."""
    monkeypatch.setattr(tempo, "hoje", lambda: HOJE)


# ---------- Montagem do cenário ----------


def id_da(cliente, rota: str, nome: str) -> int:
    categorias = cliente.get(f"/api/{rota}", params={"situacao": "todos"}).json()
    return next(c["id"] for c in categorias if c["nome"] == nome)


def lancar_despesa(cliente, valor="89.90", data="2026-11-05", **campos) -> dict:
    corpo = {
        "data_despesa": data,
        "valor": valor,
        "categoria_id": id_da(cliente, "categorias-despesa", "Kits de robótica"),
        "descricao": "Placa controladora",
        "favorecido": "Loja Robótica Ltda",
    } | campos
    resposta = cliente.post("/api/despesas", json=corpo)
    assert resposta.status_code == 201, resposta.text
    return resposta.json()


def lancar_receita(cliente, valor="1000.50", data="2026-11-05", **campos) -> dict:
    corpo = {
        "data_receita": data,
        "valor": valor,
        "categoria_id": id_da(cliente, "categorias-receita", "Patrocínio"),
        "origem": "Mineração Vale Verde",
    } | campos
    resposta = cliente.post("/api/receitas", json=corpo)
    assert resposta.status_code == 201, resposta.text
    return resposta.json()


def mensalidade_paga(
    api, matricula, nome, competencia="2026-11", data="2026-11-05", valor="150.00"
) -> dict:
    """Matricula um aluno, gera a mensalidade do mês e a paga na data informada."""
    matricula(nome)
    cobrancas.gerar(api, competencia)
    lista = api.get("/api/mensalidades", params={"mes": competencia}).json()
    mensalidade = next(m for m in lista if m["aluno"]["nome"] == nome)
    resposta = api.post(
        f"/api/mensalidades/{mensalidade['id']}/pagamento",
        json={
            "data_pagamento": data,
            "valor_pago": valor,
            "forma_pagamento": "pix",
            "observacao": "Valor combinado com o responsável",
        },
    )
    assert resposta.status_code == 201, resposta.text
    return resposta.json()


def cobranca_paga(api, novo_aluno, data="2026-11-04", valor="300.00", alunos=2, numero="NF-1"):
    """Uma empresa apadrinha `alunos` alunos de R$ 150,00 e paga a cobrança de novembro."""
    padrinho = cobrancas.novo_padrinho(api)
    for i in range(alunos):
        cobrancas.apadrinhar(api, novo_aluno(f"Apadrinhado {numero} {i}"), padrinho)
    cobrancas.gerar(api)
    [cobranca] = cobrancas.cobrancas(api, padrinho_id=padrinho["id"])
    assert cobrancas.emitir(api, cobranca["id"], numero=numero).status_code == 200
    resposta = cobrancas.pagar(
        api,
        cobranca["id"],
        valor_pago=valor,
        data_pagamento=data,
        observacao="Valor combinado com a empresa",
    )
    assert resposta.status_code == 201, resposta.text
    return resposta.json()


def caixa(cliente, mes="2026-11") -> dict:
    parametros = {} if mes is None else {"mes": mes}
    resposta = cliente.get("/api/caixa", params=parametros)
    assert resposta.status_code == 200, resposta.text
    return resposta.json()


def origem(dados: dict, nome: str) -> dict:
    return next(o for o in dados["origens_das_entradas"] if o["origem"] == nome)


def erros_de(resposta) -> dict[str, str]:
    assert resposta.status_code == 422, resposta.text
    return {
        str(e["loc"][-1]): e["msg"].removeprefix("Value error, ") for e in resposta.json()["detail"]
    }


# ---------- A conta (função pura, RNF14) ----------


def test_saldo_e_entradas_menos_saidas():
    assert calcular_saldo(Decimal("1500.00"), Decimal("400.00")) == Decimal("1100.00")


def test_saldo_pode_ser_negativo_ou_zero():
    assert calcular_saldo(Decimal("100.00"), Decimal("250.50")) == Decimal("-150.50")
    assert calcular_saldo(Decimal("80.00"), Decimal("80.00")) == Decimal("0.00")
    assert calcular_saldo(Decimal(0), Decimal(0)) == Decimal("0.00")


def test_a_conta_sai_com_duas_casas_exatas():
    assert str(calcular_saldo(Decimal("10"), Decimal("3"))) == "7.00"
    assert str(calcular_saldo(Decimal("0"), Decimal("0.1"))) == "-0.10"


def test_somar_nao_perde_centavos():
    """Com número comum, 0,1 + 0,2 daria 0,30000000000000004."""
    assert somar([Decimal("0.10"), Decimal("0.20")]) == Decimal("0.30")
    assert str(somar([Decimal("0.10")] * 30)) == "3.00"


def test_somar_nada_da_zero_com_duas_casas():
    assert str(somar([])) == "0.00"


# ---------- Mês sem movimento ----------


def test_mes_sem_nada_zera_tudo(api):
    dados = caixa(api)

    assert dados == {
        "mes": "2026-11",
        "entradas": {"total": "0.00", "quantidade": 0},
        "origens_das_entradas": [
            {"origem": "mensalidades", "rotulo": "Mensalidades", "total": "0.00", "quantidade": 0},
            {
                "origem": "apadrinhamento",
                "rotulo": "Apadrinhamento",
                "total": "0.00",
                "quantidade": 0,
            },
            {"origem": "receitas", "rotulo": "Receitas", "total": "0.00", "quantidade": 0},
        ],
        "saidas": {"total": "0.00", "quantidade": 0},
        "saldo": "0.00",
    }


# ---------- De onde vem cada valor ----------


def test_mensalidade_paga_entra_nas_entradas(api, matricula):
    mensalidade_paga(api, matricula, "Ana Lima", valor="150.00")

    dados = caixa(api)

    assert dados["entradas"] == {"total": "150.00", "quantidade": 1}
    assert origem(dados, "mensalidades")["total"] == "150.00"
    assert dados["saidas"]["total"] == "0.00"
    assert dados["saldo"] == "150.00"


def test_o_que_conta_e_o_valor_pago_de_verdade_e_nao_o_da_mensalidade(api, matricula):
    mensalidade = matricula("Ana Lima")
    assert mensalidade
    cobrancas.gerar(api, "2026-11")
    [m] = api.get("/api/mensalidades", params={"mes": "2026-11"}).json()
    resposta = api.post(
        f"/api/mensalidades/{m['id']}/pagamento",
        json={
            "data_pagamento": "2026-11-05",
            "valor_pago": "140.00",
            "forma_pagamento": "pix",
            "observacao": "Desconto combinado",
        },
    )
    assert resposta.status_code == 201

    assert caixa(api)["entradas"]["total"] == "140.00"


def test_pagamento_da_empresa_padrinha_entra_como_apadrinhamento(api, novo_aluno):
    cobranca_paga(api, novo_aluno, valor="300.00")

    dados = caixa(api)

    assert origem(dados, "apadrinhamento") == {
        "origem": "apadrinhamento",
        "rotulo": "Apadrinhamento",
        "total": "300.00",
        "quantidade": 1,
    }
    assert dados["entradas"]["total"] == "300.00"


def test_receita_avulsa_entra_nas_entradas(api):
    lancar_receita(api, valor="1000.50")

    dados = caixa(api)

    assert origem(dados, "receitas")["total"] == "1000.50"
    assert dados["entradas"] == {"total": "1000.50", "quantidade": 1}


def test_despesa_entra_nas_saidas(api):
    lancar_despesa(api, valor="89.90")

    dados = caixa(api)

    assert dados["saidas"] == {"total": "89.90", "quantidade": 1}
    assert dados["entradas"]["total"] == "0.00"
    assert dados["saldo"] == "-89.90"


def test_saldo_junta_todas_as_fontes(api, matricula, novo_aluno):
    mensalidade_paga(api, matricula, "Ana Lima", valor="150.00")
    cobranca_paga(api, novo_aluno, valor="300.00")
    lancar_receita(api, valor="1000.50")
    lancar_despesa(api, valor="89.90")
    lancar_despesa(api, valor="10.10", descricao="Cabos")

    dados = caixa(api)

    assert dados["entradas"] == {"total": "1450.50", "quantidade": 3}
    assert dados["saidas"] == {"total": "100.00", "quantidade": 2}
    assert dados["saldo"] == "1350.50"
    assert [origem(dados, o)["total"] for o in ("mensalidades", "apadrinhamento", "receitas")] == [
        "150.00",
        "300.00",
        "1000.50",
    ]


def test_o_total_das_entradas_fecha_com_a_soma_das_origens(api, matricula, novo_aluno):
    mensalidade_paga(api, matricula, "Ana Lima", valor="150.10")
    cobranca_paga(api, novo_aluno, valor="300.20")
    lancar_receita(api, valor="0.30")

    dados = caixa(api)

    soma = sum(Decimal(o["total"]) for o in dados["origens_das_entradas"])
    assert Decimal(dados["entradas"]["total"]) == soma == Decimal("450.60")
    assert dados["entradas"]["quantidade"] == sum(
        o["quantidade"] for o in dados["origens_das_entradas"]
    )


def test_o_dinheiro_da_empresa_nao_conta_em_dobro(api, novo_aluno):
    """As mensalidades dos apadrinhados ficam quitadas, mas só o pagamento da empresa entra."""
    cobranca_paga(api, novo_aluno, valor="300.00", alunos=2)

    dados = caixa(api)

    assert dados["entradas"] == {"total": "300.00", "quantidade": 1}
    assert origem(dados, "mensalidades")["total"] == "0.00"
    assert origem(dados, "mensalidades")["quantidade"] == 0


def test_o_que_nao_foi_pago_nao_entra(api, matricula, novo_aluno):
    """Mensalidade pendente, isenta ou cancelada e cobrança só emitida não movimentam o caixa."""
    for nome in ("Ana Lima", "Bruno Dias", "Carla Reis"):
        matricula(nome)
    padrinho = cobrancas.novo_padrinho(api)
    cobrancas.apadrinhar(api, novo_aluno("Apadrinhado"), padrinho)
    cobrancas.gerar(api, "2026-11")
    lista = api.get("/api/mensalidades", params={"mes": "2026-11"}).json()
    ids = {m["aluno"]["nome"]: m["id"] for m in lista}
    api.patch(f"/api/mensalidades/{ids['Bruno Dias']}/isentar", json={"motivo": "Recesso"})
    api.patch(f"/api/mensalidades/{ids['Carla Reis']}/cancelar", json={"motivo": "Gerada errada"})
    [cobranca] = cobrancas.cobrancas(api)
    assert cobrancas.emitir(api, cobranca["id"]).status_code == 200

    dados = caixa(api)

    assert dados["entradas"] == {"total": "0.00", "quantidade": 0}
    assert dados["saldo"] == "0.00"


# ---------- Regime de caixa (RN10): vale a data do dinheiro, não a da competência ----------


def test_mensalidade_de_outubro_paga_em_novembro_entra_em_novembro(api, matricula):
    mensalidade_paga(api, matricula, "Ana Lima", competencia="2026-10", data="2026-11-03")

    assert caixa(api, "2026-11")["entradas"]["total"] == "150.00"
    assert caixa(api, "2026-10")["entradas"]["total"] == "0.00"


def test_mensalidade_de_novembro_paga_em_dezembro_so_entra_em_dezembro(api, matricula):
    mensalidade_paga(api, matricula, "Ana Lima", competencia="2026-11", data="2026-12-02")

    assert caixa(api, "2026-11")["entradas"]["total"] == "0.00"
    assert caixa(api, "2026-12")["entradas"]["total"] == "150.00"


def test_pagamento_adiantado_conta_no_mes_em_que_o_dinheiro_entrou(api, matricula):
    mensalidade_paga(api, matricula, "Ana Lima", competencia="2026-12", data="2026-11-28")

    assert caixa(api, "2026-11")["entradas"]["total"] == "150.00"
    assert caixa(api, "2026-12")["entradas"]["total"] == "0.00"


@pytest.mark.parametrize(
    ("data", "entra_em_novembro"),
    [
        ("2026-10-31", False),
        ("2026-11-01", True),
        ("2026-11-30", True),
        ("2026-12-01", False),
    ],
)
def test_limites_do_mes_para_cada_fonte(api, matricula, novo_aluno, data, entra_em_novembro):
    esperado = 1 if entra_em_novembro else 0
    mensalidade_paga(api, matricula, "Ana Lima", data=data)
    cobranca_paga(api, novo_aluno, data=data)
    lancar_receita(api, data=data)
    lancar_despesa(api, data=data)

    dados = caixa(api, "2026-11")

    assert dados["entradas"]["quantidade"] == 3 * esperado
    assert dados["saidas"]["quantidade"] == esperado


def test_cada_mes_mostra_so_o_que_e_dele(api):
    lancar_despesa(api, valor="10.00", data="2026-10-15")
    lancar_despesa(api, valor="20.00", data="2026-11-15")
    lancar_despesa(api, valor="30.00", data="2026-12-15")

    assert caixa(api, "2026-10")["saidas"]["total"] == "10.00"
    assert caixa(api, "2026-11")["saidas"]["total"] == "20.00"
    assert caixa(api, "2026-12")["saidas"]["total"] == "30.00"


# ---------- Cancelados ficam de fora (RN12) ----------


def cancelar_pagamento_de_mensalidade(api, matricula):
    paga = mensalidade_paga(api, matricula, "Ana Lima")
    return api.patch(f"/api/mensalidades/{paga['id']}/pagamento/cancelar", json={"motivo": MOTIVO})


def cancelar_pagamento_da_empresa(api, novo_aluno):
    paga = cobranca_paga(api, novo_aluno)
    return api.patch(f"/api/cobrancas/{paga['id']}/pagamento/cancelar", json={"motivo": MOTIVO})


def cancelar_receita(api, matricula, novo_aluno):
    receita = lancar_receita(api)
    return api.patch(f"/api/receitas/{receita['id']}/cancelar", json={"motivo": MOTIVO})


def cancelar_despesa(api, matricula, novo_aluno):
    despesa = lancar_despesa(api)
    return api.patch(f"/api/despesas/{despesa['id']}/cancelar", json={"motivo": MOTIVO})


@pytest.mark.parametrize(
    ("cancela", "tabela", "lado"),
    [
        (lambda api, m, n: cancelar_pagamento_de_mensalidade(api, m), Pagamento, "entradas"),
        (lambda api, m, n: cancelar_pagamento_da_empresa(api, n), PagamentoCobranca, "entradas"),
        (cancelar_receita, Receita, "entradas"),
        (cancelar_despesa, Despesa, "saidas"),
    ],
    ids=["pagamento de mensalidade", "pagamento da empresa", "receita", "despesa"],
)
def test_lancamento_cancelado_sai_do_saldo_mas_continua_no_banco(
    api, db, matricula, novo_aluno, cancela, tabela, lado
):
    resposta = cancela(api, matricula, novo_aluno)
    assert resposta.status_code == 200, resposta.text

    dados = caixa(api)

    assert dados[lado] == {"total": "0.00", "quantidade": 0}
    assert dados["saldo"] == "0.00"
    db.expire_all()
    [lancamento] = db.scalars(select(tabela)).all()
    assert lancamento.cancelado_em is not None


def test_so_o_cancelado_sai_e_o_resto_continua(api, matricula):
    manter = lancar_despesa(api, valor="40.00")
    cancelar = lancar_despesa(api, valor="60.00")
    api.patch(f"/api/despesas/{cancelar['id']}/cancelar", json={"motivo": MOTIVO})

    dados = caixa(api)

    assert manter
    assert dados["saidas"] == {"total": "40.00", "quantidade": 1}
    assert dados["saldo"] == "-40.00"


def test_pagamento_cancelado_e_refeito_conta_uma_vez_so(api, matricula):
    paga = mensalidade_paga(api, matricula, "Ana Lima", valor="150.00")
    api.patch(f"/api/mensalidades/{paga['id']}/pagamento/cancelar", json={"motivo": MOTIVO})
    resposta = api.post(
        f"/api/mensalidades/{paga['id']}/pagamento",
        json={"data_pagamento": "2026-11-06", "valor_pago": "150.00", "forma_pagamento": "pix"},
    )
    assert resposta.status_code == 201, resposta.text

    assert caixa(api)["entradas"] == {"total": "150.00", "quantidade": 1}


def test_pagamento_da_empresa_cancelado_e_refeito_conta_uma_vez_so(api, novo_aluno):
    paga = cobranca_paga(api, novo_aluno, valor="300.00")
    api.patch(f"/api/cobrancas/{paga['id']}/pagamento/cancelar", json={"motivo": MOTIVO})
    resposta = cobrancas.pagar(api, paga["id"], valor_pago="300.00", data_pagamento="2026-11-09")
    assert resposta.status_code == 201, resposta.text

    assert caixa(api)["entradas"] == {"total": "300.00", "quantidade": 1}


@pytest.mark.parametrize("tipo", ["despesas", "receitas"])
def test_corrigir_conta_so_o_valor_certo(api, tipo):
    """A correção cancela o errado e lança o certo: o saldo vê apenas o certo."""
    if tipo == "despesas":
        errado = lancar_despesa(api, valor="100.00")
        corpo = {
            "data_despesa": "2026-11-05",
            "valor": "98.90",
            "categoria_id": errado["categoria"]["id"],
            "descricao": "Placa controladora",
            "favorecido": "Loja Robótica Ltda",
            "motivo": MOTIVO,
        }
        lado = "saidas"
    else:
        errado = lancar_receita(api, valor="100.00")
        corpo = {
            "data_receita": "2026-11-05",
            "valor": "98.90",
            "categoria_id": errado["categoria"]["id"],
            "origem": "Mineração Vale Verde",
            "motivo": MOTIVO,
        }
        lado = "entradas"

    resposta = api.post(f"/api/{tipo}/{errado['id']}/corrigir", json=corpo)
    assert resposta.status_code == 201, resposta.text

    assert caixa(api)[lado] == {"total": "98.90", "quantidade": 1}


def test_corrigir_para_outro_mes_move_o_valor_de_mes(api):
    errado = lancar_despesa(api, valor="100.00", data="2026-10-20")
    corpo = {
        "data_despesa": "2026-11-02",
        "valor": "100.00",
        "categoria_id": errado["categoria"]["id"],
        "descricao": "Placa controladora",
        "favorecido": "Loja Robótica Ltda",
        "motivo": MOTIVO,
    }
    assert api.post(f"/api/despesas/{errado['id']}/corrigir", json=corpo).status_code == 201

    assert caixa(api, "2026-10")["saidas"]["total"] == "0.00"
    assert caixa(api, "2026-11")["saidas"]["total"] == "100.00"


# ---------- Valores ----------


def test_centavos_somam_sem_erro_de_arredondamento(api):
    for valor in ("0.10", "0.20", "0.30"):
        lancar_despesa(api, valor=valor)

    assert caixa(api)["saidas"]["total"] == "0.60"


def test_valores_grandes_somam_certo(api):
    lancar_despesa(api, valor="99999999.99")
    lancar_despesa(api, valor="99999999.99")
    lancar_receita(api, valor="99999999.99")

    dados = caixa(api)

    assert dados["saidas"]["total"] == "199999999.98"
    assert dados["saldo"] == "-99999999.99"


def test_saldo_negativo_sai_com_o_sinal(api):
    lancar_receita(api, valor="50.00")
    lancar_despesa(api, valor="80.25")

    assert caixa(api)["saldo"] == "-30.25"


# ---------- Mês pedido ----------


def test_sem_mes_vale_o_mes_atual(api):
    lancar_despesa(api, valor="12.00", data="2026-12-10")
    lancar_despesa(api, valor="99.00", data="2026-11-10")

    for dados in (caixa(api, None), caixa(api, ""), caixa(api, "   ")):
        assert dados["mes"] == "2026-12"
        assert dados["saidas"]["total"] == "12.00"


def test_o_mes_vem_de_volta_no_formato_aaaa_mm(api):
    assert caixa(api, "2026-11")["mes"] == "2026-11"
    assert caixa(api, "2026-11-25")["mes"] == "2026-11"


def test_mes_atual_e_o_inicio_do_calendario_sao_aceitos(api):
    assert caixa(api, "2026-12")["mes"] == "2026-12"
    assert caixa(api, "2000-01")["saldo"] == "0.00"


@pytest.mark.parametrize(
    "mes", ["abc", "2026-13", "2026-00", "2026", "2026-1", "11/2026", "x" * 10]
)
def test_mes_em_formato_invalido_da_422_no_formato_padrao(api, mes):
    assert "mes" in erros_de(api.get("/api/caixa", params={"mes": mes}))


def test_mes_comprido_demais_da_422(api):
    assert api.get("/api/caixa", params={"mes": "2026-11-05-extra"}).status_code == 422


def test_mes_antigo_demais_da_422(api):
    erros = erros_de(api.get("/api/caixa", params={"mes": "1999-12"}))
    assert erros["mes"] == "Esse mês é antigo demais"


@pytest.mark.parametrize("mes", ["2027-01", "2030-06", "9999-12"])
def test_mes_que_ainda_nao_chegou_nao_existe(api, mes):
    erros = erros_de(api.get("/api/caixa", params={"mes": mes}))
    assert erros["mes"] == "Escolha o mês atual ou um mês anterior"


def test_uma_data_dentro_do_mes_atual_vale_como_o_mes_atual(api):
    assert caixa(api, "2026-12-31")["mes"] == "2026-12"


def test_virada_de_ano_pega_dezembro_inteiro_e_nao_janeiro(api, monkeypatch):
    monkeypatch.setattr(tempo, "hoje", lambda: date(2027, 2, 1))
    lancar_despesa(api, valor="1.00", data="2026-11-30")
    lancar_despesa(api, valor="2.00", data="2026-12-01")
    lancar_despesa(api, valor="4.00", data="2026-12-31")
    lancar_despesa(api, valor="8.00", data="2027-01-01")

    assert caixa(api, "2026-12")["saidas"] == {"total": "6.00", "quantidade": 2}
    assert caixa(api, "2027-01")["saidas"] == {"total": "8.00", "quantidade": 1}


# ---------- O limite do calendário (bug do filtro de mês, achado ao fazer o caixa) ----------


@pytest.mark.parametrize(
    ("dia", "esperado"),
    [
        (date(2026, 1, 1), date(2026, 2, 1)),
        (date(2026, 11, 1), date(2026, 12, 1)),
        (date(2026, 12, 1), date(2027, 1, 1)),
        (date(2024, 2, 1), date(2024, 3, 1)),
        (date(9999, 11, 1), date(9999, 12, 1)),
        (date(9999, 12, 1), date.max),
    ],
)
def test_mes_seguinte(dia, esperado):
    assert tempo.mes_seguinte(dia) == esperado


@pytest.mark.parametrize("rota", ["despesas", "receitas"])
def test_listas_de_despesas_e_receitas_aguentam_o_ultimo_mes_do_calendario(api, rota):
    """mes=9999-12 estourava um erro 500 ao calcular o mês seguinte."""
    resposta = api.get(f"/api/{rota}", params={"mes": "9999-12"})
    assert resposta.status_code == 200, resposta.text
    assert resposta.json() == []


# ---------- Perfis e métodos ----------


def test_sem_login_nao_acessa(sem_login):
    assert sem_login.get("/api/caixa").status_code == 401
    assert sem_login.get("/api/caixa", headers={"Authorization": "Bearer x"}).status_code == 401


@pytest.mark.parametrize("perfil", list(Perfil))
def test_todos_os_perfis_veem_o_caixa(api, api_como, perfil):
    lancar_despesa(api, valor="10.00")
    assert caixa(api_como(perfil))["saidas"]["total"] == "10.00"


@pytest.mark.parametrize("metodo", ["POST", "PUT", "PATCH", "DELETE"])
def test_o_caixa_so_pode_ser_lido(api, metodo):
    assert api.request(metodo, "/api/caixa", json={}).status_code == 405


def test_a_resposta_so_traz_totais_sem_dados_pessoais(api, matricula, novo_aluno):
    mensalidade_paga(api, matricula, "Ana Lima")
    cobranca_paga(api, novo_aluno)
    lancar_despesa(api)

    texto = str(caixa(api))

    assert set(caixa(api)) == {"mes", "entradas", "origens_das_entradas", "saidas", "saldo"}
    for proibido in ("Ana Lima", "Sartori", "Loja Robótica", "Mineração", "@", "Usuário"):
        assert proibido not in texto


def test_a_consulta_nao_faz_uma_consulta_por_lancamento(api, db):
    def contar() -> int:
        total = 0

        def conta(*_):
            nonlocal total
            total += 1

        event.listen(engine, "before_cursor_execute", conta)
        try:
            assert api.get("/api/caixa", params={"mes": "2026-11"}).status_code == 200
        finally:
            event.remove(engine, "before_cursor_execute", conta)
        return total

    lancar_despesa(api)
    com_um = contar()
    for i in range(10):
        lancar_despesa(api, descricao=f"Despesa {i}")
        lancar_receita(api, origem=f"Origem {i}")
    com_muitos = contar()

    assert com_muitos == com_um


def test_nao_cria_nem_altera_nada_ao_consultar(api, db):
    lancar_despesa(api)
    db.expire_all()
    antes = [(d.id, d.valor, d.cancelado_em) for d in db.scalars(select(Despesa))]

    for _ in range(3):
        caixa(api)

    db.expire_all()
    depois = [(d.id, d.valor, d.cancelado_em) for d in db.scalars(select(Despesa))]
    assert antes == depois
