from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from fastapi.exceptions import RequestValidationError
from sqlalchemy.orm import Session

from app.core import tempo
from app.core.acesso import LOGADO
from app.core.fluxo import fluxo_do_mes
from app.core.periodo import ANTIGO_DEMAIS, NO_FUTURO, caixa_do_periodo, erro_do_periodo
from app.db.session import get_db
from app.routers.mensalidades import mes_do_filtro
from app.schemas.caixa import CaixaLeitura, PeriodoLeitura, para_leitura, periodo_para_leitura
from app.schemas.mensalidade import MENSAGEM_DO_MES, PRIMEIRO_MES_ACEITO, primeiro_dia_do_mes

# Só leitura: qualquer perfil logado vê o caixa. Não há nada para alterar aqui
router = APIRouter(prefix="/caixa", tags=["caixa"], dependencies=[LOGADO])

Banco = Annotated[Session, Depends(get_db)]


def erro_no_campo(campo: str, mensagem: str, valor: str) -> RequestValidationError:
    # Mesmo formato dos outros erros de validação: uma lista com o campo e a mensagem
    return RequestValidationError(
        [{"type": "value_error", "loc": ("query", campo), "msg": mensagem, "input": valor}]
    )


def erro_no_mes(mensagem: str, mes: str) -> RequestValidationError:
    return erro_no_campo("mes", mensagem, mes)


def mes_do_periodo(campo: str, valor: str | None) -> date | None:
    """Lê um mês do período ("AAAA-MM"). Vazio ou ausente é "não informado"."""
    if valor is None or not valor.strip():
        return None
    try:
        return primeiro_dia_do_mes(valor)
    except ValueError:
        raise erro_no_campo(campo, MENSAGEM_DO_MES, valor) from None


@router.get("", response_model=CaixaLeitura)
def consultar(db: Banco, mes: Annotated[str | None, Query(max_length=10)] = None) -> CaixaLeitura:
    """O caixa de um mês: total de entradas, total de saídas e saldo (RF19, RN10), e o fluxo
    de caixa, com as entradas e as saídas separadas por categoria (RF20).

    `mes` usa o formato AAAA-MM; sem ele, vale o mês atual. Conta o dia em que o dinheiro entrou
    ou saiu e deixa de fora os lançamentos cancelados.
    """
    atual = tempo.hoje().replace(day=1)
    primeiro_dia = mes_do_filtro(mes) or atual
    if primeiro_dia < PRIMEIRO_MES_ACEITO:
        raise erro_no_mes(ANTIGO_DEMAIS, mes or "")
    if primeiro_dia > atual:
        # Nenhum lançamento pode ter data no futuro (RN09): um mês que ainda não começou é vazio
        raise erro_no_mes(NO_FUTURO, mes or "")
    return para_leitura(fluxo_do_mes(db, primeiro_dia))


@router.get("/periodo", response_model=PeriodoLeitura)
def consultar_periodo(
    db: Banco,
    de: Annotated[str | None, Query(max_length=10)] = None,
    ate: Annotated[str | None, Query(max_length=10)] = None,
) -> PeriodoLeitura:
    """O caixa de um período de até 12 meses: o total e cada mês separado (RF24).

    `de` e `ate` usam o formato AAAA-MM e valem meses inteiros. Sem `ate`, vale o mês atual; sem
    `de`, o período é só o mês de `ate`. O total traz também o fluxo por categoria do período.
    Conta o dia em que o dinheiro entrou ou saiu e deixa de fora os lançamentos cancelados.
    """
    atual = tempo.hoje().replace(day=1)
    fim = mes_do_periodo("ate", ate) or atual
    inicio = mes_do_periodo("de", de) or fim
    erro = erro_do_periodo(inicio, fim, atual)
    if erro is not None:
        campo, mensagem = erro
        raise erro_no_campo(campo, mensagem, (de if campo == "de" else ate) or "")
    return periodo_para_leitura(caixa_do_periodo(db, inicio, fim))
