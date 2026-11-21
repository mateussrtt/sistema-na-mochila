"""Caixa por período (RF24, RN10, RN12, RNF14): de um mês inicial até um mês final, até 12 meses.

O total do período é a soma dos meses, e cada mês aparece separado. Vale a mesma regra do caixa
de um mês: conta a data em que o dinheiro mexeu e deixa de fora o que foi cancelado. Os cenários
reaproveitam os ajudantes dos testes do caixa (tudo roda "em 15 de dezembro de 2026").
"""

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import event

from app.core import periodo as modulo_periodo
from app.core import tempo
from app.core.periodo import (
    ANTIGO_DEMAIS,
    FIM_ANTES_DO_INICIO,
    MUITOS_MESES,
    NO_FUTURO,
    erro_do_periodo,
    quantidade_de_meses,
)
from app.core.saldo import (
    Movimento,
    Parcela,
    saldo_do_mes,
    saldo_por_mes,
    somar_movimentos,
)
from app.db.session import engine
from app.models import Perfil
from app.schemas.mensalidade import MENSAGEM_DO_MES
from tests.test_caixa import (
    MOTIVO,
    caixa,
    cobranca_paga,
    hoje_fixo,  # noqa: F401 (fixture: todos os testes rodam em 15/12/2026)
    id_da,
    lancar_despesa,
    lancar_receita,
    mensalidade_paga,
)

ATUAL = date(2026, 12, 1)


def periodo(cliente, de=None, ate=None) -> dict:
    parametros = {}
    if de is not None:
        parametros["de"] = de
    if ate is not None:
        parametros["ate"] = ate
    resposta = cliente.get("/api/caixa/periodo", params=parametros)
    assert resposta.status_code == 200, resposta.text
    return resposta.json()


def erros_de(resposta) -> dict[str, str]:
    assert resposta.status_code == 422, resposta.text
    return {
        str(e["loc"][-1]): e["msg"].removeprefix("Value error, ") for e in resposta.json()["detail"]
    }


def meses_de(dados: dict) -> dict[str, dict]:
    return {m["mes"]: m for m in dados["meses"]}


def valores(mes: dict) -> tuple[str, str, str]:
    """Entradas, saídas e saldo de um mês."""
    return mes["entradas"]["total"], mes["saidas"]["total"], mes["saldo"]


@pytest.fixture
def cenario(api, matricula, novo_aluno) -> None:
    """Quatro meses com movimento de todas as fontes, mais um dia fora do período.

    Setembro (só 30/09): despesa de 7,00.
    Outubro: receita 500,00, mensalidade 150,00 e despesa 100,00.
    Novembro: mensalidade 150,00, empresa 300,00, despesas 40,00 + 60,00 e 50,00 em viagens.
    Dezembro: receita 1.000,50 e despesa 89,90.
    """
    lancar_despesa(api, valor="7.00", data="2026-09-30")
    lancar_receita(api, valor="500.00", data="2026-10-05")
    mensalidade_paga(api, matricula, "Ana Lima", competencia="2026-10", data="2026-10-08")
    lancar_despesa(api, valor="100.00", data="2026-10-10")
    mensalidade_paga(api, matricula, "Bia Souza", competencia="2026-11", data="2026-11-05")
    cobranca_paga(api, novo_aluno, data="2026-11-04", valor="300.00")
    lancar_despesa(api, valor="40.00", data="2026-11-03")
    lancar_despesa(api, valor="60.00", data="2026-11-30")
    lancar_despesa(
        api,
        valor="50.00",
        data="2026-11-15",
        categoria_id=id_da(api, "categorias-despesa", "Viagens"),
    )
    lancar_receita(api, valor="1000.50", data="2026-12-02")
    lancar_despesa(api, valor="89.90", data="2026-12-10")


# ---------- A conta (funções puras, RNF14) ----------


@pytest.mark.parametrize(
    ("de", "ate", "esperado"),
    [
        (date(2026, 1, 1), date(2026, 1, 1), 1),
        (date(2026, 1, 1), date(2026, 3, 1), 3),
        (date(2026, 1, 1), date(2026, 12, 1), 12),
        (date(2025, 12, 1), date(2026, 1, 1), 2),
        (date(2025, 11, 1), date(2026, 10, 1), 12),
        (date(2025, 12, 1), date(2026, 12, 1), 13),
        (date(2024, 1, 1), date(2026, 12, 1), 36),
    ],
)
def test_quantidade_de_meses_conta_os_dois_extremos(de, ate, esperado):
    assert quantidade_de_meses(de, ate) == esperado


@pytest.mark.parametrize(
    ("de", "ate"),
    [
        (date(2026, 12, 1), date(2026, 12, 1)),
        (date(2026, 10, 1), date(2026, 12, 1)),
        (date(2026, 1, 1), date(2026, 12, 1)),
        (date(2000, 1, 1), date(2000, 12, 1)),
        (date(2025, 12, 1), date(2026, 11, 1)),
    ],
)
def test_periodos_validos_nao_tem_erro(de, ate):
    assert erro_do_periodo(de, ate, ATUAL) is None


@pytest.mark.parametrize(
    ("de", "ate", "esperado"),
    [
        (date(1999, 12, 1), date(2000, 2, 1), ("de", ANTIGO_DEMAIS)),
        (date(1999, 1, 1), date(1999, 3, 1), ("de", ANTIGO_DEMAIS)),
        (date(2027, 1, 1), date(2027, 1, 1), ("de", NO_FUTURO)),
        (date(2026, 11, 1), date(2027, 1, 1), ("ate", NO_FUTURO)),
        (date(2026, 12, 1), date(2026, 11, 1), ("ate", FIM_ANTES_DO_INICIO)),
        (date(2026, 6, 1), date(2026, 1, 1), ("ate", FIM_ANTES_DO_INICIO)),
        (date(2025, 12, 1), date(2026, 12, 1), ("ate", MUITOS_MESES)),
        (date(2024, 1, 1), date(2026, 12, 1), ("ate", MUITOS_MESES)),
    ],
)
def test_cada_periodo_invalido_aponta_o_campo_e_a_mensagem(de, ate, esperado):
    assert erro_do_periodo(de, ate, ATUAL) == esperado


def test_mes_no_futuro_vence_o_fim_antes_do_inicio():
    """Os dois no futuro e invertidos: o que se diz é que o mês ainda não chegou."""
    assert erro_do_periodo(date(2027, 3, 1), date(2027, 1, 1), ATUAL) == ("de", NO_FUTURO)


def test_a_mensagem_do_limite_cita_os_12_meses():
    assert MUITOS_MESES == "O período pode ter no máximo 12 meses"


# ---------- Um mês só é o caixa daquele mês ----------


def test_um_mes_so_da_o_mesmo_resultado_do_caixa_do_mes(api, cenario):
    mensal = caixa(api, "2026-11")

    unico = periodo(api, "2026-11", "2026-11")["total"]

    for campo in (
        "entradas",
        "origens_das_entradas",
        "saidas",
        "saldo",
        "entradas_por_categoria",
        "saidas_por_categoria",
    ):
        assert unico[campo] == mensal[campo], campo


def test_o_periodo_de_um_mes_traz_so_esse_mes(api, cenario):
    dados = periodo(api, "2026-11", "2026-11")

    assert (dados["de"], dados["ate"], dados["quantidade_de_meses"]) == ("2026-11", "2026-11", 1)
    assert [m["mes"] for m in dados["meses"]] == ["2026-11"]


# ---------- O total do período e cada mês ----------


def test_cada_mes_aparece_separado_com_entradas_saidas_e_saldo(api, cenario):
    meses = meses_de(periodo(api, "2026-10", "2026-12"))

    assert valores(meses["2026-10"]) == ("650.00", "100.00", "550.00")
    assert valores(meses["2026-11"]) == ("450.00", "150.00", "300.00")
    assert valores(meses["2026-12"]) == ("1000.50", "89.90", "910.60")
    assert meses["2026-10"]["entradas"]["quantidade"] == 2
    assert meses["2026-11"]["saidas"]["quantidade"] == 3


def test_o_total_do_periodo_soma_os_meses(api, cenario):
    total = periodo(api, "2026-10", "2026-12")["total"]

    assert total["entradas"] == {"total": "2100.50", "quantidade": 5}
    assert total["saidas"] == {"total": "339.90", "quantidade": 5}
    assert total["saldo"] == "1760.60"


@pytest.mark.parametrize(
    ("de", "ate", "entradas", "saidas", "saldo"),
    [
        ("2026-10", "2026-10", "650.00", "100.00", "550.00"),
        ("2026-10", "2026-11", "1100.00", "250.00", "850.00"),
        ("2026-11", "2026-12", "1450.50", "239.90", "1210.60"),
        ("2026-09", "2026-12", "2100.50", "346.90", "1753.60"),
        ("2026-09", "2026-09", "0.00", "7.00", "-7.00"),
        ("2026-12", "2026-12", "1000.50", "89.90", "910.60"),
    ],
)
def test_totais_de_varios_periodos(api, cenario, de, ate, entradas, saidas, saldo):
    total = periodo(api, de, ate)["total"]

    assert (total["entradas"]["total"], total["saidas"]["total"], total["saldo"]) == (
        entradas,
        saidas,
        saldo,
    )


def test_o_total_fecha_com_a_soma_dos_meses_em_tudo(api, cenario):
    dados = periodo(api, "2026-09", "2026-12")
    meses = dados["meses"]
    total = dados["total"]

    def soma(lado: str, campo: str):
        return sum(Decimal(str(m[lado][campo])) for m in meses)

    assert Decimal(total["entradas"]["total"]) == soma("entradas", "total")
    assert Decimal(total["saidas"]["total"]) == soma("saidas", "total")
    assert total["entradas"]["quantidade"] == soma("entradas", "quantidade")
    assert total["saidas"]["quantidade"] == soma("saidas", "quantidade")
    assert Decimal(total["saldo"]) == sum(Decimal(m["saldo"]) for m in meses)
    for mes in meses:
        assert Decimal(mes["saldo"]) == Decimal(mes["entradas"]["total"]) - Decimal(
            mes["saidas"]["total"]
        )


def test_os_meses_vem_do_mais_antigo_ao_mais_novo_e_sem_buracos(api, cenario):
    dados = periodo(api, "2026-06", "2026-12")

    assert [m["mes"] for m in dados["meses"]] == [
        "2026-06",
        "2026-07",
        "2026-08",
        "2026-09",
        "2026-10",
        "2026-11",
        "2026-12",
    ]
    assert dados["quantidade_de_meses"] == 7


def test_mes_sem_movimento_aparece_zerado(api, cenario):
    meses = meses_de(periodo(api, "2026-07", "2026-09"))

    assert valores(meses["2026-07"]) == ("0.00", "0.00", "0.00")
    assert meses["2026-07"]["entradas"] == {"total": "0.00", "quantidade": 0}
    assert valores(meses["2026-09"]) == ("0.00", "7.00", "-7.00")


def test_periodo_sem_nenhum_movimento_zera_tudo(api):
    dados = periodo(api, "2026-01", "2026-03")

    assert dados["total"]["saldo"] == "0.00"
    assert dados["total"]["entradas_por_categoria"] == []
    assert dados["total"]["saidas_por_categoria"] == []
    assert all(valores(m) == ("0.00", "0.00", "0.00") for m in dados["meses"])


def test_saldo_negativo_de_um_mes_e_positivo_de_outro_no_mesmo_periodo(api, cenario):
    meses = meses_de(periodo(api, "2026-09", "2026-10"))

    assert Decimal(meses["2026-09"]["saldo"]) < 0
    assert Decimal(meses["2026-10"]["saldo"]) > 0


# ---------- Limites do período ----------


def test_os_extremos_do_periodo_entram_e_o_dia_antes_e_o_depois_nao(api, cenario):
    """Outubro a novembro pega de 01/10 a 30/11: fora ficam 30/09 e 01/12."""
    lancar_despesa(api, valor="1.00", data="2026-10-01")
    lancar_despesa(api, valor="2.00", data="2026-11-30")

    total = periodo(api, "2026-10", "2026-11")["total"]

    assert total["saidas"] == {"total": "253.00", "quantidade": 6}
    assert periodo(api, "2026-09", "2026-09")["total"]["saidas"]["total"] == "7.00"
    assert periodo(api, "2026-12", "2026-12")["total"]["saidas"]["total"] == "89.90"


def test_virada_de_ano_no_periodo(api, monkeypatch):
    monkeypatch.setattr(tempo, "hoje", lambda: date(2027, 2, 15))
    lancar_despesa(api, valor="1.00", data="2026-11-30")
    lancar_despesa(api, valor="2.00", data="2026-12-31")
    lancar_despesa(api, valor="4.00", data="2027-01-01")
    lancar_despesa(api, valor="8.00", data="2027-02-14")

    dados = periodo(api, "2026-12", "2027-01")

    assert [m["mes"] for m in dados["meses"]] == ["2026-12", "2027-01"]
    assert dados["total"]["saidas"] == {"total": "6.00", "quantidade": 2}
    assert [m["saidas"]["total"] for m in dados["meses"]] == ["2.00", "4.00"]


def test_doze_meses_atravessando_o_ano_sao_aceitos(api, monkeypatch):
    monkeypatch.setattr(tempo, "hoje", lambda: date(2027, 2, 15))

    dados = periodo(api, "2026-03", "2027-02")

    assert dados["quantidade_de_meses"] == 12
    assert [m["mes"] for m in dados["meses"]][:3] == ["2026-03", "2026-04", "2026-05"]
    assert dados["meses"][-1]["mes"] == "2027-02"


def test_o_ano_inteiro_ate_o_mes_atual(api, cenario):
    dados = periodo(api, "2026-01", "2026-12")

    assert dados["quantidade_de_meses"] == 12
    assert len(dados["meses"]) == 12
    assert dados["total"]["saldo"] == "1753.60"


def test_treze_meses_nao_podem(api):
    resposta = api.get("/api/caixa/periodo", params={"de": "2025-12", "ate": "2026-12"})

    assert erros_de(resposta) == {"ate": "O período pode ter no máximo 12 meses"}


# ---------- Cancelados e regime de caixa ----------


def test_cancelado_fica_fora_do_total_e_do_mes(api, cenario):
    errado = lancar_despesa(api, valor="500.00", data="2026-11-20")
    api.patch(f"/api/despesas/{errado['id']}/cancelar", json={"motivo": MOTIVO})

    dados = periodo(api, "2026-10", "2026-12")

    assert dados["total"]["saidas"] == {"total": "339.90", "quantidade": 5}
    assert valores(meses_de(dados)["2026-11"]) == ("450.00", "150.00", "300.00")


def test_correcao_conta_so_o_valor_certo_e_no_mes_certo(api):
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

    meses = meses_de(periodo(api, "2026-10", "2026-11"))

    assert meses["2026-10"]["saidas"]["total"] == "0.00"
    assert meses["2026-11"]["saidas"]["total"] == "100.00"


def test_mensalidade_de_outubro_paga_em_novembro_conta_em_novembro(api, matricula):
    mensalidade_paga(api, matricula, "Ana Lima", competencia="2026-10", data="2026-11-03")

    meses = meses_de(periodo(api, "2026-10", "2026-11"))

    assert meses["2026-10"]["entradas"]["total"] == "0.00"
    assert meses["2026-11"]["entradas"]["total"] == "150.00"


def test_dinheiro_da_empresa_nao_conta_em_dobro_no_periodo(api, novo_aluno):
    cobranca_paga(api, novo_aluno, valor="300.00", data="2026-11-04")

    total = periodo(api, "2026-10", "2026-12")["total"]

    assert total["entradas"] == {"total": "300.00", "quantidade": 1}
    origens = {o["origem"]: o["total"] for o in total["origens_das_entradas"]}
    assert origens == {"mensalidades": "0.00", "apadrinhamento": "300.00", "receitas": "0.00"}


# ---------- Fluxo por categoria no período ----------


def test_a_mesma_categoria_de_meses_diferentes_vira_uma_linha_so(api, cenario):
    total = periodo(api, "2026-10", "2026-12")["total"]

    saidas = [(x["nome"], x["total"], x["quantidade"]) for x in total["saidas_por_categoria"]]
    entradas = [(x["nome"], x["total"], x["quantidade"]) for x in total["entradas_por_categoria"]]

    assert saidas == [("Kits de robótica", "289.90", 4), ("Viagens", "50.00", 1)]
    assert entradas == [
        ("Patrocínio", "1500.50", 2),
        ("Apadrinhamento", "300.00", 1),
        ("Mensalidades", "300.00", 2),
    ]


def test_as_linhas_do_fluxo_fecham_com_os_totais_do_periodo(api, cenario):
    total = periodo(api, "2026-09", "2026-12")["total"]

    for lado in ("entradas", "saidas"):
        soma = sum(Decimal(x["total"]) for x in total[f"{lado}_por_categoria"])
        assert soma == Decimal(total[lado]["total"])
        quantidade = sum(x["quantidade"] for x in total[f"{lado}_por_categoria"])
        assert quantidade == total[lado]["quantidade"]


def test_as_origens_das_entradas_somam_o_periodo(api, cenario):
    total = periodo(api, "2026-10", "2026-12")["total"]

    assert [o["origem"] for o in total["origens_das_entradas"]] == [
        "mensalidades",
        "apadrinhamento",
        "receitas",
    ]
    assert [o["total"] for o in total["origens_das_entradas"]] == ["300.00", "300.00", "1500.50"]


# ---------- Valores e formato ----------


def test_centavos_somam_sem_erro_de_arredondamento_no_periodo(api):
    for valor, data in (("0.10", "2026-10-01"), ("0.20", "2026-11-01"), ("0.30", "2026-12-01")):
        lancar_despesa(api, valor=valor, data=data)

    assert periodo(api, "2026-10", "2026-12")["total"]["saidas"]["total"] == "0.60"


def test_valores_grandes_somam_certo_no_periodo(api):
    lancar_despesa(api, valor="99999999.99", data="2026-10-10")
    lancar_despesa(api, valor="99999999.99", data="2026-11-10")
    lancar_receita(api, valor="99999999.99", data="2026-12-10")

    total = periodo(api, "2026-10", "2026-12")["total"]

    assert total["saidas"]["total"] == "199999999.98"
    assert total["saldo"] == "-99999999.99"


def test_a_resposta_tem_so_os_campos_combinados(api, cenario):
    dados = periodo(api, "2026-10", "2026-11")

    assert set(dados) == {"de", "ate", "quantidade_de_meses", "total", "meses"}
    assert set(dados["total"]) == {
        "entradas",
        "origens_das_entradas",
        "saidas",
        "saldo",
        "entradas_por_categoria",
        "saidas_por_categoria",
    }
    assert set(dados["meses"][0]) == {"mes", "entradas", "saidas", "saldo"}


def test_a_resposta_nao_expoe_dados_pessoais(api, cenario):
    texto = str(periodo(api, "2026-10", "2026-12"))

    for proibido in ("Ana Lima", "Bia Souza", "Sartori", "Loja Robótica", "Mineração", "@"):
        assert proibido not in texto


# ---------- Quando não se informa o período ----------


def test_sem_parametros_vale_o_mes_atual(api, cenario):
    dados = periodo(api)

    assert (dados["de"], dados["ate"], dados["quantidade_de_meses"]) == ("2026-12", "2026-12", 1)
    assert dados["total"]["saidas"]["total"] == "89.90"


def test_so_o_mes_final_da_um_periodo_de_um_mes(api, cenario):
    dados = periodo(api, ate="2026-11")

    assert (dados["de"], dados["ate"]) == ("2026-11", "2026-11")


def test_so_o_mes_inicial_vai_ate_o_mes_atual(api, cenario):
    dados = periodo(api, de="2026-10")

    assert (dados["de"], dados["ate"], dados["quantidade_de_meses"]) == ("2026-10", "2026-12", 3)


@pytest.mark.parametrize("vazio", ["", "   "])
def test_parametro_em_branco_vale_como_nao_informado(api, vazio):
    dados = periodo(api, de=vazio, ate=vazio)

    assert (dados["de"], dados["ate"]) == ("2026-12", "2026-12")


def test_aceita_a_data_completa_e_usa_o_mes_dela(api, cenario):
    dados = periodo(api, "2026-10-25", "2026-11-03")

    assert (dados["de"], dados["ate"]) == ("2026-10", "2026-11")


# ---------- Período inválido: erro em português, sem quebrar ----------


@pytest.mark.parametrize("campo", ["de", "ate"])
@pytest.mark.parametrize(
    "valor", ["abc", "2026-13", "2026-00", "2026", "2026-1", "11/2026", "x" * 10, "2026-02-30"]
)
def test_mes_em_formato_invalido_da_422_no_campo_certo(api, campo, valor):
    resposta = api.get("/api/caixa/periodo", params={campo: valor})

    assert erros_de(resposta) == {campo: MENSAGEM_DO_MES}


@pytest.mark.parametrize("campo", ["de", "ate"])
def test_mes_comprido_demais_da_422(api, campo):
    assert api.get("/api/caixa/periodo", params={campo: "2026-11-05-extra"}).status_code == 422


def test_fim_antes_do_inicio_da_422_em_portugues(api):
    resposta = api.get("/api/caixa/periodo", params={"de": "2026-12", "ate": "2026-10"})

    assert erros_de(resposta) == {"ate": "O mês final não pode ser antes do mês inicial"}


def test_mais_de_12_meses_da_422_em_portugues(api):
    resposta = api.get("/api/caixa/periodo", params={"de": "2024-01", "ate": "2026-12"})

    assert erros_de(resposta) == {"ate": "O período pode ter no máximo 12 meses"}


@pytest.mark.parametrize(
    ("de", "ate", "campo"),
    [
        ("2027-01", "2027-01", "de"),
        ("2026-12", "2027-01", "ate"),
        ("2030-06", "2030-07", "de"),
        ("9999-12", "9999-12", "de"),
        ("2026-12", "9999-12", "ate"),
    ],
)
def test_mes_no_futuro_da_422_e_nunca_500(api, de, ate, campo):
    resposta = api.get("/api/caixa/periodo", params={"de": de, "ate": ate})

    assert erros_de(resposta) == {campo: "Escolha o mês atual ou um mês anterior"}


@pytest.mark.parametrize("campo", ["de", "ate"])
def test_mes_antigo_demais_da_422(api, campo):
    outro = {"de": "ate", "ate": "de"}[campo]
    resposta = api.get("/api/caixa/periodo", params={campo: "1999-12", outro: "2000-01"})

    assert erros_de(resposta) == {campo: "Esse mês é antigo demais"}


def test_o_primeiro_mes_aceito_e_o_ultimo_mes_existente(api):
    assert periodo(api, "2000-01", "2000-03")["quantidade_de_meses"] == 3
    assert periodo(api, "2026-12", "2026-12")["de"] == "2026-12"


def test_periodo_invalido_nao_grava_nem_altera_nada(api, cenario):
    antes = periodo(api, "2026-10", "2026-12")

    api.get("/api/caixa/periodo", params={"de": "2026-12", "ate": "2026-10"})
    api.get("/api/caixa/periodo", params={"de": "abc"})

    assert periodo(api, "2026-10", "2026-12") == antes


# ---------- Perfis e métodos ----------


def test_sem_login_nao_acessa(sem_login):
    assert sem_login.get("/api/caixa/periodo").status_code == 401
    headers = {"Authorization": "Bearer x"}
    assert sem_login.get("/api/caixa/periodo", headers=headers).status_code == 401


@pytest.mark.parametrize("perfil", list(Perfil))
def test_todos_os_perfis_veem_o_caixa_do_periodo(api, api_como, perfil):
    lancar_despesa(api, valor="10.00", data="2026-11-10")

    dados = periodo(api_como(perfil), "2026-10", "2026-12")

    assert dados["total"]["saidas"]["total"] == "10.00"


@pytest.mark.parametrize("metodo", ["POST", "PUT", "PATCH", "DELETE"])
def test_o_periodo_so_pode_ser_lido(api, metodo):
    assert api.request(metodo, "/api/caixa/periodo", json={}).status_code == 405


def test_o_caixa_de_um_mes_continua_como_antes(api, cenario):
    dados = caixa(api, "2026-11")

    assert dados["mes"] == "2026-11"
    assert dados["saldo"] == "300.00"


# ---------- Desempenho: não faz uma consulta por mês nem por lançamento ----------


def contar_consultas(cliente, **parametros) -> int:
    total = 0

    def conta(*_):
        nonlocal total
        total += 1

    event.listen(engine, "before_cursor_execute", conta)
    try:
        assert cliente.get("/api/caixa/periodo", params=parametros).status_code == 200
    finally:
        event.remove(engine, "before_cursor_execute", conta)
    return total


def test_o_numero_de_consultas_nao_depende_dos_meses_nem_dos_lancamentos(api):
    lancar_despesa(api, valor="1.00", data="2026-12-01")
    um_mes = contar_consultas(api, de="2026-12", ate="2026-12")

    for i in range(1, 12):
        lancar_despesa(api, valor="1.00", data=f"2026-{i:02d}-05")
        lancar_receita(api, valor="2.00", data=f"2026-{i:02d}-06")
    doze_meses = contar_consultas(api, de="2026-01", ate="2026-12")

    assert doze_meses == um_mes


def test_saldo_por_mes_devolve_um_saldo_para_cada_mes(db, api):
    lancar_despesa(api, valor="5.00", data="2026-11-02")

    meses = saldo_por_mes(db, date(2026, 10, 1), date(2026, 12, 1))

    assert [m.mes for m in meses] == [date(2026, 10, 1), date(2026, 11, 1), date(2026, 12, 1)]
    assert [m.saidas.total for m in meses] == [Decimal("0.00"), Decimal("5.00"), Decimal("0.00")]


def test_saldo_do_mes_soma_so_o_mes(db, api):
    lancar_despesa(api, valor="5.00", data="2026-11-02")
    lancar_despesa(api, valor="9.00", data="2026-12-02")

    novembro = saldo_do_mes(db, date(2026, 11, 1))

    assert novembro.mes == date(2026, 11, 1)
    assert novembro.saidas == Parcela(Decimal("5.00"), 1)
    assert saldo_do_mes(db, date(2026, 10, 1)).saidas == Parcela(Decimal("0.00"), 0)


def test_lancamento_do_primeiro_e_do_ultimo_dia_cai_no_mes_certo(api):
    for valor, data in (
        ("1.00", "2026-10-01"),
        ("2.00", "2026-10-31"),
        ("4.00", "2026-11-01"),
        ("8.00", "2026-11-30"),
    ):
        lancar_despesa(api, valor=valor, data=data)

    dados = periodo(api, "2026-10", "2026-11")
    meses = meses_de(dados)

    assert meses["2026-10"]["saidas"] == {"total": "3.00", "quantidade": 2}
    assert meses["2026-11"]["saidas"] == {"total": "12.00", "quantidade": 2}
    assert dados["total"]["saidas"] == {"total": "15.00", "quantidade": 4}


def zero() -> Parcela:
    return Parcela(Decimal("0.00"), 0)


def test_somar_movimentos_soma_cada_origem():
    um = Movimento(Parcela(Decimal("1.10"), 1), zero(), Parcela(Decimal("5.00"), 2), zero())
    dois = Movimento(Parcela(Decimal("2.20"), 2), zero(), zero(), Parcela(Decimal("0.30"), 1))

    soma = somar_movimentos([um, dois])

    assert soma.mensalidades == Parcela(Decimal("3.30"), 3)
    assert soma.apadrinhamento == zero()
    assert soma.receitas == Parcela(Decimal("5.00"), 2)
    assert soma.despesas == Parcela(Decimal("0.30"), 1)
    assert soma.entradas == Parcela(Decimal("8.30"), 5)


def test_somar_movimentos_de_nada_e_zero():
    assert somar_movimentos([]) == Movimento(zero(), zero(), zero(), zero())


def test_o_total_e_sempre_a_soma_dos_meses_mesmo_que_o_banco_mude_no_meio(api, monkeypatch):
    """Se um lançamento entrar entre a conta dos meses e a do total, os dois ainda fecham."""
    lancar_despesa(api, valor="10.00", data="2026-11-02")
    conta_dos_meses = modulo_periodo.saldo_por_mes

    def meses_e_depois_um_lancamento(db, de, ate):
        meses = conta_dos_meses(db, de, ate)
        lancar_despesa(api, valor="500.00", data="2026-11-03")  # chega depois dos meses
        return meses

    monkeypatch.setattr(modulo_periodo, "saldo_por_mes", meses_e_depois_um_lancamento)

    dados = periodo(api, "2026-10", "2026-12")

    assert dados["total"]["saidas"] == {"total": "10.00", "quantidade": 1}
    assert sum(Decimal(m["saidas"]["total"]) for m in dados["meses"]) == Decimal("10.00")


def test_o_total_nao_repete_a_conta_dos_meses(api, monkeypatch):
    """Sem a segunda conta, o período faz menos consultas que a soma dos pedaços."""

    def nao_deve_ser_chamada(*_):
        raise AssertionError("o total foi calculado de novo em vez de somar os meses")

    monkeypatch.setattr("app.core.fluxo.saldo_entre", nao_deve_ser_chamada)

    assert periodo(api, "2026-10", "2026-12")["quantidade_de_meses"] == 3
