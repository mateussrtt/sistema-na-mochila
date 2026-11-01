import calendar
from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query
from fastapi.exceptions import RequestValidationError
from sqlalchemy import Row, func, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session, contains_eager

from app.core import tempo
from app.core.acesso import LOGADO, PODE_EDITAR, UsuarioLogado
from app.db.session import get_db
from app.models import (
    Aluno,
    Bolsa,
    Matricula,
    Mensalidade,
    SituacaoMatricula,
    SituacaoMensalidade,
    StatusMensalidade,
    data_de_vencimento,
    situacao_da_mensalidade,
)
from app.schemas.comum import ID_MAXIMO, termo_de_busca
from app.schemas.matricula import AlunoResumo
from app.schemas.mensalidade import (
    GeracaoEntrada,
    GeracaoResultado,
    MensalidadeLeitura,
    primeiro_dia_do_mes,
)

# Todas as rotas exigem login. Gerar mensalidades exige perfil de operador ou administrador
router = APIRouter(prefix="/mensalidades", tags=["mensalidades"], dependencies=[LOGADO])

Banco = Annotated[Session, Depends(get_db)]

SituacaoDoFiltro = Literal["todas", "a_vencer", "atrasada", "paga", "isenta", "cancelada"]


def mes_do_filtro(mes: str | None) -> date | None:
    """Converte o "AAAA-MM" do filtro no dia 1 do mês. Vazio significa "todos os meses"."""
    if mes is None or not mes.strip():
        return None
    try:
        return primeiro_dia_do_mes(mes)
    except ValueError as erro:
        # Mesmo formato dos outros erros de validação: uma lista com o campo e a mensagem
        raise RequestValidationError(
            [{"type": "value_error", "loc": ("query", "mes"), "msg": str(erro), "input": mes}]
        ) from None


def alunos_ja_cobrados(db: Session, competencia: date) -> set[int]:
    """Alunos que já têm mensalidade no mês, de qualquer matrícula."""
    return set(
        db.scalars(
            select(Matricula.aluno_id)
            .join(Mensalidade, Mensalidade.matricula_id == Matricula.id)
            .where(Mensalidade.competencia == competencia)
        )
    )


def para_leitura(mensalidade: Mensalidade, hoje: date) -> MensalidadeLeitura:
    situacao = situacao_da_mensalidade(mensalidade.status, mensalidade.data_vencimento, hoje)
    atraso = (hoje - mensalidade.data_vencimento).days
    matricula = mensalidade.matricula
    return MensalidadeLeitura(
        id=mensalidade.id,
        matricula_id=matricula.id,
        aluno=AlunoResumo.model_validate(matricula.aluno),
        bolsa=matricula.bolsa,
        competencia=mensalidade.competencia,
        valor=mensalidade.valor,
        data_vencimento=mensalidade.data_vencimento,
        status=mensalidade.status,
        situacao=situacao,
        dias_em_atraso=atraso if situacao == SituacaoMensalidade.ATRASADA else 0,
    )


@router.get("", response_model=list[MensalidadeLeitura])
def listar(
    db: Banco,
    mes: Annotated[str | None, Query(max_length=10)] = None,
    situacao: SituacaoDoFiltro = "todas",
    busca: str | None = None,
    matricula_id: Annotated[int | None, Query(gt=0, le=ID_MAXIMO)] = None,
) -> list[MensalidadeLeitura]:
    """Lista as mensalidades, por aluno e depois do mês mais recente para o mais antigo.

    `mes` usa o formato AAAA-MM. A busca procura o texto no nome do aluno.
    """
    hoje = tempo.hoje()
    consulta = (
        select(Mensalidade)
        .join(Mensalidade.matricula)
        .join(Matricula.aluno)
        .options(contains_eager(Mensalidade.matricula).contains_eager(Matricula.aluno))
        .order_by(Aluno.nome, Mensalidade.competencia.desc(), Mensalidade.id)
    )
    primeiro_dia = mes_do_filtro(mes)
    if primeiro_dia is not None:
        consulta = consulta.where(Mensalidade.competencia == primeiro_dia)
    if matricula_id is not None:
        consulta = consulta.where(Mensalidade.matricula_id == matricula_id)

    pendente = Mensalidade.status == StatusMensalidade.PENDENTE
    if situacao == "a_vencer":
        consulta = consulta.where(pendente, Mensalidade.data_vencimento >= hoje)
    elif situacao == "atrasada":
        consulta = consulta.where(pendente, Mensalidade.data_vencimento < hoje)
    elif situacao != "todas":
        consulta = consulta.where(Mensalidade.status == StatusMensalidade(situacao))

    termo = termo_de_busca(busca)
    if termo:
        # autoescape: "%" e "_" digitados na busca valem como texto, não como curinga do SQL
        consulta = consulta.where(Aluno.nome.icontains(termo, autoescape=True))
    return [para_leitura(m, hoje) for m in db.scalars(consulta)]


@router.post("/gerar", response_model=GeracaoResultado, dependencies=[PODE_EDITAR])
def gerar(dados: GeracaoEntrada, db: Banco, usuario: UsuarioLogado) -> GeracaoResultado:
    """Gera a mensalidade do mês de cada matrícula que estava em vigor nesse mês.

    Em vigor = começou até o último dia do mês e não foi encerrada antes do primeiro dia dele.
    Assim o resultado não depende do dia em que alguém clica em gerar: quem saiu no meio do
    mês é cobrado nesse mês, e um mês passado pode ser gerado depois.

    - Bolsa integral (não paga) e matrícula que só começa depois do mês ficam de fora.
    - Se o aluno teve duas matrículas no mesmo mês (saiu e voltou), vale a mais recente: ele
      não é cobrado em dobro.
    - O vencimento é no dia 10, ou na data de início para quem entrou depois do dia 10.
    - Pode ser chamada de novo para o mesmo mês: só entram as mensalidades que faltam.
    """
    primeiro = dados.competencia
    ultimo = primeiro.replace(day=calendar.monthrange(primeiro.year, primeiro.month)[1])

    em_vigor = db.execute(
        select(
            Matricula.id,
            Matricula.aluno_id,
            Matricula.valor_mensalidade,
            Matricula.bolsa,
            Matricula.data_inicio,
        )
        .where(
            Matricula.data_inicio <= ultimo,
            or_(Matricula.data_encerramento.is_(None), Matricula.data_encerramento >= primeiro),
        )
        # a mais recente de cada aluno vem primeiro
        .order_by(Matricula.aluno_id, Matricula.data_inicio.desc(), Matricula.id.desc())
    ).all()
    vale_no_mes: dict[int, Row] = {}
    for matricula in em_vigor:
        vale_no_mes.setdefault(matricula.aluno_id, matricula)
    com_bolsa_integral = [m for m in vale_no_mes.values() if m.bolsa == Bolsa.INTEGRAL]
    a_cobrar = [m for m in vale_no_mes.values() if m.bolsa != Bolsa.INTEGRAL]

    ainda_nao_comecaram = db.scalar(
        select(func.count())
        .select_from(Matricula)
        .where(
            Matricula.situacao == SituacaoMatricula.ATIVA,
            Matricula.bolsa != Bolsa.INTEGRAL,
            Matricula.data_inicio > ultimo,
        )
    )

    ja_cobrados = alunos_ja_cobrados(db, primeiro)
    a_gerar = [m for m in a_cobrar if m.aluno_id not in ja_cobrados]

    geradas = 0
    if a_gerar:
        linhas = [
            {
                "matricula_id": m.id,
                "competencia": primeiro,
                "valor": m.valor_mensalidade,
                "data_vencimento": data_de_vencimento(primeiro, m.data_inicio),
                "status": StatusMensalidade.PENDENTE,
                "criado_por_id": usuario.id,
            }
            for m in a_gerar
        ]
        # "Se já existe, ignora": é o banco que impede a duplicata, mesmo que dois operadores
        # gerem o mesmo mês ao mesmo tempo
        inseridas = db.execute(
            insert(Mensalidade)
            .values(linhas)
            .on_conflict_do_nothing(constraint="uq_mensalidades_matricula_competencia")
            .returning(Mensalidade.id)
        ).all()
        geradas = len(inseridas)
    db.commit()

    return GeracaoResultado(
        competencia=primeiro,
        geradas=geradas,
        ja_existiam=len(a_cobrar) - geradas,
        bolsa_integral=len(com_bolsa_integral),
        ainda_nao_comecaram=ainda_nao_comecaram or 0,
    )
