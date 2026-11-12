from typing import Annotated

from fastapi import APIRouter, Depends, Query
from fastapi.exceptions import RequestValidationError
from sqlalchemy.orm import Session

from app.core import tempo
from app.core.acesso import LOGADO
from app.core.saldo import saldo_do_mes
from app.db.session import get_db
from app.routers.mensalidades import mes_do_filtro
from app.schemas.caixa import CaixaLeitura, para_leitura
from app.schemas.mensalidade import PRIMEIRO_MES_ACEITO

# Só leitura: qualquer perfil logado vê o caixa. Não há nada para alterar aqui
router = APIRouter(prefix="/caixa", tags=["caixa"], dependencies=[LOGADO])

Banco = Annotated[Session, Depends(get_db)]


def erro_no_mes(mensagem: str, mes: str) -> RequestValidationError:
    # Mesmo formato dos outros erros de validação: uma lista com o campo e a mensagem
    return RequestValidationError(
        [{"type": "value_error", "loc": ("query", "mes"), "msg": mensagem, "input": mes}]
    )


@router.get("", response_model=CaixaLeitura)
def consultar(db: Banco, mes: Annotated[str | None, Query(max_length=10)] = None) -> CaixaLeitura:
    """O caixa de um mês: total de entradas, total de saídas e saldo (RF19, RN10).

    `mes` usa o formato AAAA-MM; sem ele, vale o mês atual. Conta o dia em que o dinheiro entrou
    ou saiu e deixa de fora os lançamentos cancelados.
    """
    atual = tempo.hoje().replace(day=1)
    primeiro_dia = mes_do_filtro(mes) or atual
    if primeiro_dia < PRIMEIRO_MES_ACEITO:
        raise erro_no_mes("Esse mês é antigo demais", mes or "")
    if primeiro_dia > atual:
        # Nenhum lançamento pode ter data no futuro (RN09): um mês que ainda não começou é vazio
        raise erro_no_mes("Escolha o mês atual ou um mês anterior", mes or "")
    return para_leitura(saldo_do_mes(db, primeiro_dia))
