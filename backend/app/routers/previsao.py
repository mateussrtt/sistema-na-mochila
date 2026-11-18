from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.acesso import LOGADO
from app.core.previsao import previsao_de_receita
from app.db.session import get_db
from app.schemas.previsao import PrevisaoLeitura, para_leitura

# Só leitura: qualquer perfil logado vê a previsão
router = APIRouter(prefix="/previsao", tags=["previsão"], dependencies=[LOGADO])

Banco = Annotated[Session, Depends(get_db)]


@router.get("", response_model=PrevisaoLeitura)
def consultar(db: Banco) -> PrevisaoLeitura:
    """A previsão de receita do mês atual e dos 11 seguintes (RF21, RF22, RN11).

    Cada mês soma as mensalidades das matrículas em vigor nele, pela mesma regra da geração das
    mensalidades. No mês atual, mostra também quanto já foi recebido e quanto falta.
    """
    return para_leitura(previsao_de_receita(db))
