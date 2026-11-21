from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core import tempo
from app.core.acesso import LOGADO
from app.core.saldo import saldo_do_mes
from app.db.session import get_db
from app.routers.pendencias import listar as listar_pendencias
from app.schemas.resumo import (
    DespesasLeitura,
    EmAtrasoLeitura,
    RecebidoLeitura,
    ResumoDoMesLeitura,
)

# Só leitura: qualquer perfil logado vê o resumo. Não há nada para alterar aqui
router = APIRouter(prefix="/resumo", tags=["resumo"], dependencies=[LOGADO])

Banco = Annotated[Session, Depends(get_db)]


@router.get("", response_model=ResumoDoMesLeitura)
def consultar(db: Banco) -> ResumoDoMesLeitura:
    """O resumo do mês atual para a tela inicial: recebido, em atraso, despesas e saldo (RF23).

    Sem conta própria, para os números nunca destoarem das telas que os detalham:
    - recebido, despesas e saldo vêm do caixa do mês (`/caixa`), pela data em que o dinheiro
      entrou ou saiu e sem os lançamentos cancelados (RN10, RN12);
    - em atraso vem do painel de pendências (`/pendencias`), de todos os meses (RN07).
    """
    mes = tempo.hoje().replace(day=1)
    caixa = saldo_do_mes(db, mes)
    pendencias = listar_pendencias(db=db, mes=None).resumo
    return ResumoDoMesLeitura(
        mes=mes.strftime("%Y-%m"),
        recebido=RecebidoLeitura(total=caixa.entradas.total, quantidade=caixa.entradas.quantidade),
        em_atraso=EmAtrasoLeitura(
            total=pendencias.total_em_aberto,
            mensalidades=pendencias.mensalidades,
            alunos=pendencias.alunos,
            responsaveis=pendencias.responsaveis,
        ),
        despesas=DespesasLeitura(total=caixa.saidas.total, quantidade=caixa.saidas.quantidade),
        saldo=caixa.saldo,
    )
