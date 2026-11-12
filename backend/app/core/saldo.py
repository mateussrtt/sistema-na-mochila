"""Saldo do mês (RF19, RN10): o que entrou menos o que saiu, pela data em que o dinheiro mexeu.

É regime de caixa: o que conta é o dia do pagamento ou da despesa, e não o mês a que a
mensalidade se refere. Uma mensalidade de outubro paga em novembro entra no saldo de novembro.

De onde vem cada valor, para o mesmo dinheiro nunca ser contado duas vezes:
- mensalidades: os pagamentos de mensalidade (`pagamentos`);
- apadrinhamento: os pagamentos das empresas padrinhas (`pagamentos_cobranca`). As mensalidades
  dos alunos apadrinhados não têm pagamento próprio, então não entram de novo em "mensalidades";
- receitas: as receitas avulsas (patrocínios, projetos, doações), que não incluem mensalidades
  nem cobranças das empresas;
- saídas: as despesas.

Lançamento cancelado (`cancelado_em` preenchido) fica de fora de tudo (RN12). Uma correção cancela
o errado e registra o certo, então só o certo é somado.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core import tempo
from app.models import Despesa, Pagamento, PagamentoCobranca, Receita

CENTAVO = Decimal("0.01")


@dataclass(frozen=True)
class Parcela:
    """Soma de uma origem do dinheiro no mês e quantos lançamentos a formam."""

    total: Decimal
    quantidade: int


@dataclass(frozen=True)
class SaldoDoMes:
    mes: date
    mensalidades: Parcela
    apadrinhamento: Parcela
    receitas: Parcela
    despesas: Parcela

    @property
    def entradas(self) -> Parcela:
        origens = (self.mensalidades, self.apadrinhamento, self.receitas)
        return Parcela(somar(p.total for p in origens), sum(p.quantidade for p in origens))

    @property
    def saidas(self) -> Parcela:
        return self.despesas

    @property
    def saldo(self) -> Decimal:
        return calcular_saldo(self.entradas.total, self.saidas.total)


def somar(valores: Iterable[Decimal]) -> Decimal:
    """Soma valores em reais, sempre com 2 casas (RNF08)."""
    return sum(valores, Decimal(0)).quantize(CENTAVO)


def calcular_saldo(entradas: Decimal, saidas: Decimal) -> Decimal:
    """Saldo = total que entrou menos total que saiu (RN10). Pode ser negativo."""
    return (entradas - saidas).quantize(CENTAVO)


def _parcela(db: Session, valor, data, cancelado_em, de: date, ate: date) -> Parcela:
    """Soma e conta os lançamentos não cancelados com data de `de` (incluído) a `ate` (excluído)."""
    total, quantidade = db.execute(
        select(func.coalesce(func.sum(valor), 0), func.count()).where(
            data >= de, data < ate, cancelado_em.is_(None)
        )
    ).one()
    return Parcela(Decimal(total).quantize(CENTAVO), quantidade)


def saldo_do_mes(db: Session, mes: date) -> SaldoDoMes:
    """Calcula o saldo do mês que começa em `mes` (o dia 1)."""
    de, ate = mes, tempo.mes_seguinte(mes)
    return SaldoDoMes(
        mes=mes,
        mensalidades=_parcela(
            db, Pagamento.valor_pago, Pagamento.data_pagamento, Pagamento.cancelado_em, de, ate
        ),
        apadrinhamento=_parcela(
            db,
            PagamentoCobranca.valor_pago,
            PagamentoCobranca.data_pagamento,
            PagamentoCobranca.cancelado_em,
            de,
            ate,
        ),
        receitas=_parcela(db, Receita.valor, Receita.data_receita, Receita.cancelado_em, de, ate),
        despesas=_parcela(db, Despesa.valor, Despesa.data_despesa, Despesa.cancelado_em, de, ate),
    )
