from decimal import Decimal

from pydantic import BaseModel


class RecebidoLeitura(BaseModel):
    """O dinheiro que entrou no mês e em quantos lançamentos."""

    total: Decimal
    quantidade: int


class DespesasLeitura(BaseModel):
    """O dinheiro que saiu no mês e em quantos lançamentos."""

    total: Decimal
    quantidade: int


class EmAtrasoLeitura(BaseModel):
    """As mensalidades em atraso de todos os meses, como no painel de pendências."""

    total: Decimal
    mensalidades: int
    alunos: int
    responsaveis: int


class ResumoDoMesLeitura(BaseModel):
    """O resumo do mês atual para a tela inicial (RF23).

    Os números não têm conta própria: `recebido`, `despesas` e `saldo` são os do caixa do mês,
    e `em_atraso` é o resumo do painel de pendências.
    """

    # AAAA-MM
    mes: str
    recebido: RecebidoLeitura
    em_atraso: EmAtrasoLeitura
    despesas: DespesasLeitura
    # Pode ser negativo
    saldo: Decimal
