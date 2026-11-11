"""Cancelamento e correção de lançamentos (RF17).

Nenhum lançamento é apagado nem editado depois de salvo (RN12). O erro é cancelado com motivo,
quem cancelou e quando (RF26), e continua visível. Corrigir é cancelar o errado e registrar o
certo, que aponta para o que ele substitui.
"""

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Usuario


def travar(db: Session, modelo: type, lancamento_id: int, nao_encontrado: str):
    """Busca o lançamento e trava a linha até o fim: dois cancelamentos não passam juntos."""
    lancamento = db.scalar(select(modelo).where(modelo.id == lancamento_id).with_for_update())
    if lancamento is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, nao_encontrado)
    return lancamento


def marcar_cancelado(lancamento: object, motivo: str, usuario: Usuario) -> None:
    lancamento.cancelado_em = func.now()
    lancamento.motivo_cancelamento = motivo
    lancamento.cancelado_por_id = usuario.id


def substitutos(db: Session, modelo: type, ids: list[int]) -> dict[int, int]:
    """Para cada lançamento da lista que foi corrigido, o id do lançamento que o substituiu."""
    if not ids:
        return {}
    linhas = db.execute(
        select(modelo.substitui_id, modelo.id).where(modelo.substitui_id.in_(ids))
    ).all()
    return {antigo: novo for antigo, novo in linhas}
