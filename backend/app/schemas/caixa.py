from decimal import Decimal

from pydantic import BaseModel

from app.core.fluxo import FluxoDoMes, LinhaDoFluxo, Origem
from app.core.saldo import Parcela


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
