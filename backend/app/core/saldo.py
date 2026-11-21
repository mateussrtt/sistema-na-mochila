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
class Movimento:
    """O dinheiro que entrou e saiu num intervalo de datas, separado por origem (RF19, RF24)."""

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

    def do_mes(self, mes: date) -> "SaldoDoMes":
        return SaldoDoMes(
            mes=mes,
            mensalidades=self.mensalidades,
            apadrinhamento=self.apadrinhamento,
            receitas=self.receitas,
            despesas=self.despesas,
        )


@dataclass(frozen=True)
class SaldoDoMes(Movimento):
    mes: date


def somar(valores: Iterable[Decimal]) -> Decimal:
    """Soma valores em reais, sempre com 2 casas (RNF08)."""
    return sum(valores, Decimal(0)).quantize(CENTAVO)


def somar_movimentos(movimentos: Iterable[Movimento]) -> Movimento:
    """Soma vários movimentos (por exemplo, os meses de um período) num só, origem por origem."""
    lista = list(movimentos)

    def junta(origem: str) -> Parcela:
        parcelas = [getattr(m, origem) for m in lista]
        return Parcela(somar(p.total for p in parcelas), sum(p.quantidade for p in parcelas))

    return Movimento(*(junta(nome) for nome in _ORIGENS))


def calcular_saldo(entradas: Decimal, saidas: Decimal) -> Decimal:
    """Saldo = total que entrou menos total que saiu (RN10). Pode ser negativo."""
    return (entradas - saidas).quantize(CENTAVO)


_ORIGENS = ("mensalidades", "apadrinhamento", "receitas", "despesas")
SEM_MOVIMENTO = Parcela(Decimal("0.00"), 0)


def _fontes() -> dict[str, tuple]:
    """Para cada origem: o valor, a data do dinheiro e a marca de cancelado (RN10, RN12)."""
    return {
        "mensalidades": (Pagamento.valor_pago, Pagamento.data_pagamento, Pagamento.cancelado_em),
        "apadrinhamento": (
            PagamentoCobranca.valor_pago,
            PagamentoCobranca.data_pagamento,
            PagamentoCobranca.cancelado_em,
        ),
        "receitas": (Receita.valor, Receita.data_receita, Receita.cancelado_em),
        "despesas": (Despesa.valor, Despesa.data_despesa, Despesa.cancelado_em),
    }


def _parcela(db: Session, valor, data, cancelado_em, de: date, ate: date) -> Parcela:
    """Soma e conta os lançamentos não cancelados com data de `de` (incluído) a `ate` (excluído)."""
    total, quantidade = db.execute(
        select(func.coalesce(func.sum(valor), 0), func.count()).where(
            data >= de, data < ate, cancelado_em.is_(None)
        )
    ).one()
    return Parcela(Decimal(total).quantize(CENTAVO), quantidade)


def _parcelas_por_mes(db: Session, valor, data, cancelado_em, de: date, ate: date):
    """Soma e conta os lançamentos de cada mês do intervalo, numa consulta só agrupada no banco.

    Só voltam os meses que tiveram movimento: os outros ficam sem linha.
    """
    ano, mes = func.extract("year", data), func.extract("month", data)
    linhas = db.execute(
        select(ano, mes, func.sum(valor), func.count())
        .where(data >= de, data < ate, cancelado_em.is_(None))
        .group_by(ano, mes)
    ).all()
    return {
        date(int(a), int(m), 1): Parcela(Decimal(total).quantize(CENTAVO), quantidade)
        for a, m, total, quantidade in linhas
    }


def saldo_entre(db: Session, de: date, ate: date) -> Movimento:
    """O movimento das datas de `de` (incluído) até `ate` (excluído), tudo junto (RF24)."""
    fontes = _fontes()
    return Movimento(*(_parcela(db, *fontes[nome], de, ate) for nome in _ORIGENS))


def saldo_do_mes(db: Session, mes: date) -> SaldoDoMes:
    """Calcula o saldo do mês que começa em `mes` (o dia 1)."""
    return saldo_entre(db, mes, tempo.mes_seguinte(mes)).do_mes(mes)


def saldo_por_mes(db: Session, de: date, ate: date) -> list[SaldoDoMes]:
    """O saldo de cada mês de `de` até `ate` (dois dias 1, incluídos), do mais antigo ao mais novo.

    São 4 consultas, uma por origem, não importa quantos meses nem lançamentos haja. Um mês sem
    movimento aparece zerado, para o período não ter buracos.
    """
    fim = tempo.mes_seguinte(ate)
    fontes = _fontes()
    por_origem = {nome: _parcelas_por_mes(db, *fontes[nome], de, fim) for nome in _ORIGENS}
    meses = []
    mes = de
    while mes <= ate:
        parcelas = [por_origem[nome].get(mes, SEM_MOVIMENTO) for nome in _ORIGENS]
        meses.append(Movimento(*parcelas).do_mes(mes))
        mes = tempo.mes_seguinte(mes)
    return meses
