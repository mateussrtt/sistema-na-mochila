from datetime import datetime

from pydantic import BaseModel


class CancelamentoLeitura(BaseModel):
    """Quem cancelou um lançamento, quando e por quê (RF17, RF26)."""

    motivo: str
    cancelado_por: str
    cancelado_em: datetime


def cancelamento_de(lancamento: object) -> CancelamentoLeitura | None:
    """O cancelamento de qualquer lançamento com as colunas de cancelamento, ou None se ativo."""
    if getattr(lancamento, "cancelado_em", None) is None:
        return None
    return CancelamentoLeitura(
        motivo=lancamento.motivo_cancelamento,
        cancelado_por=lancamento.cancelado_por.nome,
        cancelado_em=lancamento.cancelado_em,
    )
