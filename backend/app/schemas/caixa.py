from decimal import Decimal

from pydantic import BaseModel

from app.core.saldo import Parcela, SaldoDoMes


class ParcelaLeitura(BaseModel):
    """Quanto entrou ou saiu e em quantos lançamentos."""

    total: Decimal
    quantidade: int


class OrigemLeitura(ParcelaLeitura):
    """Uma origem das entradas, com o nome para mostrar na tela."""

    origem: str
    rotulo: str


class CaixaLeitura(BaseModel):
    """O caixa de um mês: entradas, saídas e saldo (RF19)."""

    # AAAA-MM
    mes: str
    entradas: ParcelaLeitura
    # Sempre as três origens, na mesma ordem, mesmo quando uma delas é zero
    origens_das_entradas: list[OrigemLeitura]
    saidas: ParcelaLeitura
    saldo: Decimal


def _parcela(parcela: Parcela) -> ParcelaLeitura:
    return ParcelaLeitura(total=parcela.total, quantidade=parcela.quantidade)


def para_leitura(saldo: SaldoDoMes) -> CaixaLeitura:
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
    )
