from decimal import Decimal

from pydantic import BaseModel

from app.core.fluxo import FluxoDoMes, LinhaDoFluxo, Origem
from app.core.periodo import CaixaDoPeriodo, quantidade_de_meses
from app.core.saldo import Movimento, Parcela, SaldoDoMes


class ParcelaLeitura(BaseModel):
    """Quanto entrou ou saiu e em quantos lançamentos."""

    total: Decimal
    quantidade: int


class OrigemLeitura(ParcelaLeitura):
    """Uma origem das entradas, com o nome para mostrar na tela."""

    origem: str
    rotulo: str


class LinhaDoFluxoLeitura(ParcelaLeitura):
    """Uma linha do fluxo de caixa: mensalidades, apadrinhamento ou uma categoria (RF20)."""

    origem: Origem
    # Só as linhas de receita e de despesa têm categoria
    categoria_id: int | None
    nome: str


class CaixaLeitura(BaseModel):
    """O caixa de um mês: entradas, saídas e saldo (RF19)."""

    # AAAA-MM
    mes: str
    entradas: ParcelaLeitura
    # Sempre as três origens, na mesma ordem, mesmo quando uma delas é zero
    origens_das_entradas: list[OrigemLeitura]
    saidas: ParcelaLeitura
    saldo: Decimal
    # Fluxo de caixa (RF20): só as linhas com movimento no mês, do maior valor para o menor.
    # A soma de cada lista fecha com o total de entradas e de saídas
    entradas_por_categoria: list[LinhaDoFluxoLeitura]
    saidas_por_categoria: list[LinhaDoFluxoLeitura]


def _parcela(parcela: Parcela) -> ParcelaLeitura:
    return ParcelaLeitura(total=parcela.total, quantidade=parcela.quantidade)


def _linha(linha: LinhaDoFluxo) -> LinhaDoFluxoLeitura:
    return LinhaDoFluxoLeitura(
        origem=linha.origem,
        categoria_id=linha.categoria_id,
        nome=linha.nome,
        total=linha.parcela.total,
        quantidade=linha.parcela.quantidade,
    )


def para_leitura(fluxo: FluxoDoMes) -> CaixaLeitura:
    saldo = fluxo.saldo
    origens = (
        ("mensalidades", "Mensalidades", saldo.mensalidades),
        ("apadrinhamento", "Apadrinhamento", saldo.apadrinhamento),
        ("receitas", "Receitas", saldo.receitas),
    )
    return CaixaLeitura(
        mes=saldo.mes.strftime("%Y-%m"),
        entradas=_parcela(saldo.entradas),
        origens_das_entradas=[
            OrigemLeitura(origem=chave, rotulo=rotulo, total=p.total, quantidade=p.quantidade)
            for chave, rotulo, p in origens
        ],
        saidas=_parcela(saldo.saidas),
        saldo=saldo.saldo,
        entradas_por_categoria=[_linha(linha) for linha in fluxo.entradas],
        saidas_por_categoria=[_linha(linha) for linha in fluxo.saidas],
    )


class MesDoPeriodoLeitura(BaseModel):
    """O caixa de um dos meses do período, para comparar um mês com o outro (RF24)."""

    # AAAA-MM
    mes: str
    entradas: ParcelaLeitura
    saidas: ParcelaLeitura
    saldo: Decimal


class TotalDoPeriodoLeitura(BaseModel):
    """O caixa do período inteiro: os mesmos totais e o mesmo fluxo de um mês, somados."""

    entradas: ParcelaLeitura
    origens_das_entradas: list[OrigemLeitura]
    saidas: ParcelaLeitura
    saldo: Decimal
    entradas_por_categoria: list[LinhaDoFluxoLeitura]
    saidas_por_categoria: list[LinhaDoFluxoLeitura]


class PeriodoLeitura(BaseModel):
    """O caixa de um período de até 12 meses: o total e cada mês separado (RF24)."""

    # AAAA-MM
    de: str
    ate: str
    quantidade_de_meses: int
    total: TotalDoPeriodoLeitura
    # Do mês mais antigo ao mais novo, todos os do período, mesmo os sem movimento
    meses: list[MesDoPeriodoLeitura]


def _origens(movimento: Movimento) -> list[OrigemLeitura]:
    origens = (
        ("mensalidades", "Mensalidades", movimento.mensalidades),
        ("apadrinhamento", "Apadrinhamento", movimento.apadrinhamento),
        ("receitas", "Receitas", movimento.receitas),
    )
    return [
        OrigemLeitura(origem=chave, rotulo=rotulo, total=p.total, quantidade=p.quantidade)
        for chave, rotulo, p in origens
    ]


def _mes(saldo: SaldoDoMes) -> MesDoPeriodoLeitura:
    return MesDoPeriodoLeitura(
        mes=saldo.mes.strftime("%Y-%m"),
        entradas=_parcela(saldo.entradas),
        saidas=_parcela(saldo.saidas),
        saldo=saldo.saldo,
    )


def periodo_para_leitura(caixa: CaixaDoPeriodo) -> PeriodoLeitura:
    movimento = caixa.total.movimento
    return PeriodoLeitura(
        de=caixa.de.strftime("%Y-%m"),
        ate=caixa.ate.strftime("%Y-%m"),
        quantidade_de_meses=quantidade_de_meses(caixa.de, caixa.ate),
        total=TotalDoPeriodoLeitura(
            entradas=_parcela(movimento.entradas),
            origens_das_entradas=_origens(movimento),
            saidas=_parcela(movimento.saidas),
            saldo=movimento.saldo,
            entradas_por_categoria=[_linha(linha) for linha in caixa.total.entradas],
            saidas_por_categoria=[_linha(linha) for linha in caixa.total.saidas],
        ),
        meses=[_mes(mes) for mes in caixa.meses],
    )
