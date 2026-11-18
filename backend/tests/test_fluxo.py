"""Fluxo de caixa do mês (RF20, RN08, RN10, RN12): entradas e saídas separadas por categoria.

O fluxo abre em linhas o mesmo dinheiro do saldo (RF19): a soma das linhas fecha sempre com os
totais de entradas e de saídas. Os cenários reaproveitam os ajudantes dos testes do caixa.
"""

from decimal import Decimal

import pytest

from app.core.fluxo import LinhaDoFluxo, ordenar
from app.core.saldo import Parcela
from app.models import Perfil
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


def linhas(dados: dict, lado: str) -> list[tuple]:
    """As linhas de um lado do fluxo como (origem, nome, total, quantidade), na ordem da API."""
    return [
        (linha["origem"], linha["nome"], linha["total"], linha["quantidade"])
        for linha in dados[f"{lado}_por_categoria"]
    ]


def soma(dados: dict, lado: str) -> Decimal:
    return sum((Decimal(linha["total"]) for linha in dados[f"{lado}_por_categoria"]), Decimal(0))


def despesa_em(api, categoria: str, valor: str, **campos) -> dict:
    return lancar_despesa(
        api, valor=valor, categoria_id=id_da(api, "categorias-despesa", categoria), **campos
    )


def receita_em(api, categoria: str, valor: str, **campos) -> dict:
    return lancar_receita(
        api, valor=valor, categoria_id=id_da(api, "categorias-receita", categoria), **campos
    )


# ---------- A ordem das linhas (função pura) ----------


def linha(nome: str, total: str) -> LinhaDoFluxo:
    return LinhaDoFluxo("despesa", 1, nome, Parcela(Decimal(total), 1))


def test_ordena_do_maior_valor_para_o_menor():
    ordem = ordenar([linha("Peças", "10.00"), linha("Viagens", "300.00"), linha("Kits", "45.50")])
    assert [item.nome for item in ordem] == ["Viagens", "Kits", "Peças"]


def test_no_empate_ordena_pelo_nome_sem_ligar_para_maiusculas():
    ordem = ordenar([linha("viagens", "10.00"), linha("Custos", "10.00"), linha("kits", "10.00")])
    assert [item.nome for item in ordem] == ["Custos", "kits", "viagens"]


# ---------- Cada origem do dinheiro vira uma linha ----------


def test_mes_sem_movimento_nao_tem_linhas(api):
    dados = caixa(api)
    assert (dados["entradas_por_categoria"], dados["saidas_por_categoria"]) == ([], [])


def test_mensalidades_e_apadrinhamento_sao_uma_linha_cada_sem_categoria(api, matricula, novo_aluno):
    mensalidade_paga(api, matricula, "Ana Lima")
    mensalidade_paga(api, matricula, "Bruno Dias")
    cobranca_paga(api, novo_aluno)

    dados = caixa(api)

    assert dados["entradas_por_categoria"] == [
        {
            "origem": "apadrinhamento",
            "categoria_id": None,
            "nome": "Apadrinhamento",
            "total": "300.00",
            "quantidade": 1,
        },
        {
            "origem": "mensalidades",
            "categoria_id": None,
            "nome": "Mensalidades",
            "total": "300.00",
            "quantidade": 2,
        },
    ]


def test_receitas_abrem_uma_linha_por_categoria(api):
    receita_em(api, "Patrocínio", "1000.00")
    receita_em(api, "Patrocínio", "500.50", origem="Rotary Club")
    receita_em(api, "Doações", "80.00")

    dados = caixa(api)

    assert linhas(dados, "entradas") == [
        ("receita", "Patrocínio", "1500.50", 2),
        ("receita", "Doações", "80.00", 1),
    ]
    patrocinio = dados["entradas_por_categoria"][0]
    assert patrocinio["categoria_id"] == id_da(api, "categorias-receita", "Patrocínio")


def test_despesas_abrem_uma_linha_por_categoria(api):
    despesa_em(api, "Kits de robótica", "899.00")
    despesa_em(api, "Peças", "45.90")
    despesa_em(api, "Peças", "12.10", descricao="Parafusos")
    despesa_em(api, "Viagens", "450.00")

    assert linhas(caixa(api), "saidas") == [
        ("despesa", "Kits de robótica", "899.00", 1),
        ("despesa", "Viagens", "450.00", 1),
        ("despesa", "Peças", "58.00", 2),
    ]


def test_origem_sem_dinheiro_no_mes_nao_aparece(api, matricula):
    """Mensalidade gerada mas não paga não vira linha de R$ 0,00."""
    matricula("Ana Lima")
    receita_em(api, "Doações", "80.00")
    assert linhas(caixa(api), "entradas") == [("receita", "Doações", "80.00", 1)]


def test_categoria_sem_movimento_no_mes_nao_aparece(api):
    despesa_em(api, "Peças", "10.00")
    nomes = [linha["nome"] for linha in caixa(api)["saidas_por_categoria"]]
    assert nomes == ["Peças"]


# ---------- O fluxo fecha com o saldo ----------


def test_a_soma_das_linhas_fecha_com_os_totais(api, matricula, novo_aluno):
    mensalidade_paga(api, matricula, "Ana Lima", valor="150.00")
    cobranca_paga(api, novo_aluno, valor="300.00")
    receita_em(api, "Patrocínio", "1000.33")
    receita_em(api, "Projetos e editais", "250.10")
    despesa_em(api, "Kits de robótica", "899.99")
    despesa_em(api, "Custos fixos", "0.01")

    dados = caixa(api)

    assert soma(dados, "entradas") == Decimal(dados["entradas"]["total"]) == Decimal("1700.43")
    assert soma(dados, "saidas") == Decimal(dados["saidas"]["total"]) == Decimal("900.00")
    assert sum(linha["quantidade"] for linha in dados["entradas_por_categoria"]) == 4
    assert sum(linha["quantidade"] for linha in dados["saidas_por_categoria"]) == 2


def test_as_receitas_do_fluxo_fecham_com_a_origem_receitas_do_saldo(api):
    receita_em(api, "Patrocínio", "100.00")
    receita_em(api, "Doações", "0.10")
    receita_em(api, "Projetos e editais", "0.20")

    dados = caixa(api)
    [origem] = [o for o in dados["origens_das_entradas"] if o["origem"] == "receitas"]

    assert soma(dados, "entradas") == Decimal(origem["total"]) == Decimal("100.30")


def test_cada_mes_mostra_so_as_linhas_dele(api):
    despesa_em(api, "Viagens", "450.00", data="2026-10-31")
    despesa_em(api, "Peças", "10.00", data="2026-11-01")
    receita_em(api, "Doações", "80.00", data="2026-12-01")

    novembro = caixa(api, "2026-11")
    assert linhas(novembro, "saidas") == [("despesa", "Peças", "10.00", 1)]
    assert linhas(novembro, "entradas") == []
    assert linhas(caixa(api, "2026-10"), "saidas") == [("despesa", "Viagens", "450.00", 1)]
    assert linhas(caixa(api, "2026-12"), "entradas") == [("receita", "Doações", "80.00", 1)]


# ---------- Cancelados e corrigidos ----------


def test_lancamento_cancelado_sai_da_linha_da_categoria(api):
    despesa_em(api, "Peças", "10.00")
    errada = despesa_em(api, "Peças", "10.00", descricao="Lançada em dobro")
    api.patch(f"/api/despesas/{errada['id']}/cancelar", json={"motivo": MOTIVO})

    assert linhas(caixa(api), "saidas") == [("despesa", "Peças", "10.00", 1)]


def test_categoria_so_com_lancamentos_cancelados_nao_aparece(api):
    receita = receita_em(api, "Doações", "80.00")
    api.patch(f"/api/receitas/{receita['id']}/cancelar", json={"motivo": MOTIVO})
    assert caixa(api)["entradas_por_categoria"] == []


def test_pagamento_cancelado_sai_da_linha_de_mensalidades(api, matricula):
    pagamento = mensalidade_paga(api, matricula, "Ana Lima")
    api.patch(f"/api/mensalidades/{pagamento['id']}/pagamento/cancelar", json={"motivo": MOTIVO})
    assert caixa(api)["entradas_por_categoria"] == []


def test_corrigir_para_outra_categoria_move_o_valor_de_linha(api):
    errada = despesa_em(api, "Peças", "120.00", descricao="Passagem de ônibus")
    resposta = api.post(
        f"/api/despesas/{errada['id']}/corrigir",
        json={
            "data_despesa": "2026-11-05",
            "valor": "120.00",
            "categoria_id": id_da(api, "categorias-despesa", "Viagens"),
            "descricao": "Passagem de ônibus",
            "favorecido": "Viação Pássaro Verde",
            "motivo": "Era viagem, não peça",
        },
    )
    assert resposta.status_code == 201, resposta.text

    assert linhas(caixa(api), "saidas") == [("despesa", "Viagens", "120.00", 1)]


# ---------- Categorias inativas ----------


def test_categoria_inativa_com_movimento_no_mes_continua_no_fluxo(api):
    despesa_em(api, "Custos fixos", "200.00")
    categoria_id = id_da(api, "categorias-despesa", "Custos fixos")
    resposta = api.put(
        f"/api/categorias-despesa/{categoria_id}", json={"nome": "Custos fixos", "ativo": False}
    )
    assert resposta.status_code == 200, resposta.text

    assert linhas(caixa(api), "saidas") == [("despesa", "Custos fixos", "200.00", 1)]


def test_categoria_renomeada_aparece_com_o_nome_novo(api):
    receita_em(api, "Doações", "80.00")
    categoria_id = id_da(api, "categorias-receita", "Doações")
    api.put(f"/api/categorias-receita/{categoria_id}", json={"nome": "Doações de pessoas"})

    assert linhas(caixa(api), "entradas") == [("receita", "Doações de pessoas", "80.00", 1)]


# ---------- Quem vê e o que a resposta traz ----------


@pytest.mark.parametrize("perfil", list(Perfil))
def test_todos_os_perfis_veem_o_fluxo(api, api_como, perfil):
    despesa_em(api, "Peças", "10.00")
    dados = caixa(api_como(perfil))
    assert linhas(dados, "saidas") == [("despesa", "Peças", "10.00", 1)]


def test_o_fluxo_nao_traz_dados_pessoais_nem_descricoes(api, matricula):
    mensalidade_paga(api, matricula, "Ana Lima")
    despesa_em(api, "Peças", "10.00", favorecido="Loja do Zé", descricao="Parafuso sextavado")
    receita_em(api, "Doações", "80.00", origem="Maria Souza")

    texto = str(caixa(api)["entradas_por_categoria"] + caixa(api)["saidas_por_categoria"])

    for proibido in ("Ana Lima", "Loja do Zé", "Parafuso", "Maria Souza", "@"):
        assert proibido not in texto
