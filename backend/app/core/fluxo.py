"""Fluxo de caixa do mês (RF20): as entradas e as saídas separadas por categoria.

É o mesmo dinheiro do saldo (RF19), aberto em linhas, com as mesmas regras: vale a data em que o
dinheiro entrou ou saiu (RN10) e lançamento cancelado fica de fora (RN12). Por isso a soma das
linhas fecha sempre com os totais do saldo.

Entradas: mensalidades e apadrinhamento são uma linha cada (não têm categoria), e as receitas
avulsas abrem uma linha por categoria de receita (RN08). Saídas: uma linha por categoria de
despesa. Só aparece a categoria que teve movimento no mês, mesmo que hoje esteja inativa.
"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Literal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core import tempo
from app.core.saldo import CENTAVO, Parcela, SaldoDoMes, saldo_do_mes
from app.models import CategoriaDespesa, CategoriaReceita, Despesa, Receita

Origem = Literal["mensalidades", "apadrinhamento", "receita", "despesa"]


@dataclass(frozen=True)
class LinhaDoFluxo:
    """Uma linha do fluxo: uma origem das entradas ou uma categoria (de receita ou de despesa)."""

    origem: Origem
    # Só as linhas de receita e de despesa têm categoria
    categoria_id: int | None
    nome: str
    parcela: Parcela


@dataclass(frozen=True)
class FluxoDoMes:
    saldo: SaldoDoMes
    entradas: list[LinhaDoFluxo]
    saidas: list[LinhaDoFluxo]


def ordenar(linhas: list[LinhaDoFluxo]) -> list[LinhaDoFluxo]:
    """Do maior valor para o menor. No empate, pelo nome, para a ordem não mudar à toa."""
    return sorted(linhas, key=lambda linha: (-linha.parcela.total, linha.nome.casefold()))


def _por_categoria(db: Session, modelo, categoria, data, de: date, ate: date):
    """Soma e conta, por categoria, os lançamentos não cancelados com data de `de` a `ate`.

    Uma consulta só, agrupada no banco: não importa quantos lançamentos o mês tenha.
    """
    return db.execute(
        select(categoria.id, categoria.nome, func.sum(modelo.valor), func.count())
        .join(categoria, modelo.categoria_id == categoria.id)
        .where(data >= de, data < ate, modelo.cancelado_em.is_(None))
        .group_by(categoria.id, categoria.nome)
    ).all()


def _linhas(origem: Origem, resultado) -> list[LinhaDoFluxo]:
    return [
        LinhaDoFluxo(origem, categoria_id, nome, Parcela(Decimal(total).quantize(CENTAVO), quantos))
        for categoria_id, nome, total, quantos in resultado
    ]


def fluxo_do_mes(db: Session, mes: date) -> FluxoDoMes:
    """Calcula o fluxo do mês que começa em `mes` (o dia 1)."""
    de, ate = mes, tempo.mes_seguinte(mes)
    saldo = saldo_do_mes(db, mes)
    sem_categoria = [
        LinhaDoFluxo("mensalidades", None, "Mensalidades", saldo.mensalidades),
        LinhaDoFluxo("apadrinhamento", None, "Apadrinhamento", saldo.apadrinhamento),
    ]
    receitas = _linhas(
        "receita", _por_categoria(db, Receita, CategoriaReceita, Receita.data_receita, de, ate)
    )
    despesas = _linhas(
        "despesa", _por_categoria(db, Despesa, CategoriaDespesa, Despesa.data_despesa, de, ate)
    )
    entradas = [linha for linha in sem_categoria if linha.parcela.quantidade > 0] + receitas
    return FluxoDoMes(saldo=saldo, entradas=ordenar(entradas), saidas=ordenar(despesas))
