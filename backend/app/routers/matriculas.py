from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, contains_eager, joinedload

from app.core.acesso import LOGADO, PODE_EDITAR
from app.db.session import get_db
from app.models import Aluno, Matricula, SituacaoMatricula
from app.schemas.matricula import (
    ID_MAXIMO,
    MatriculaEncerramento,
    MatriculaEntrada,
    MatriculaLeitura,
)

# Todas as rotas exigem login. As que alteram dados exigem perfil de operador ou administrador
router = APIRouter(prefix="/matriculas", tags=["matrículas"], dependencies=[LOGADO])

Banco = Annotated[Session, Depends(get_db)]
MatriculaId = Annotated[int, Path(gt=0, le=ID_MAXIMO)]

JA_MATRICULADO = "Este aluno já tem uma matrícula ativa"


def tem_matricula_ativa(db: Session, aluno_id: int) -> bool:
    return (
        db.scalar(
            select(Matricula.id).where(
                Matricula.aluno_id == aluno_id, Matricula.situacao == SituacaoMatricula.ATIVA
            )
        )
        is not None
    )


def busca_matricula(db: Session, matricula_id: int, bloquear: bool = False) -> Matricula:
    consulta = (
        select(Matricula)
        .where(Matricula.id == matricula_id)
        .options(joinedload(Matricula.aluno, innerjoin=True))
    )
    if bloquear:
        # Trava a linha até o commit: dois encerramentos ao mesmo tempo não passam juntos
        consulta = consulta.with_for_update(of=Matricula).execution_options(populate_existing=True)
    matricula = db.scalars(consulta).first()
    if matricula is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Matrícula não encontrada")
    return matricula


@router.get("", response_model=list[MatriculaLeitura])
def listar(
    db: Banco,
    busca: str | None = None,
    situacao: Literal["ativas", "encerradas", "todas"] = "ativas",
    aluno_id: Annotated[int | None, Query(gt=0, le=ID_MAXIMO)] = None,
) -> list[Matricula]:
    """Lista as matrículas em ordem alfabética pelo nome do aluno.

    A busca procura o texto no nome do aluno.
    """
    consulta = (
        select(Matricula)
        .join(Matricula.aluno)
        .options(contains_eager(Matricula.aluno))
        .order_by(Aluno.nome, Matricula.data_inicio.desc())
    )
    if situacao != "todas":
        esperada = SituacaoMatricula.ATIVA if situacao == "ativas" else SituacaoMatricula.ENCERRADA
        consulta = consulta.where(Matricula.situacao == esperada)
    if aluno_id is not None:
        consulta = consulta.where(Matricula.aluno_id == aluno_id)
    # O PostgreSQL não aceita o caractere nulo (\x00) em texto; ele é descartado
    termo = busca.replace("\x00", "").strip() if busca else ""
    if termo:
        # autoescape: "%" e "_" digitados na busca valem como texto, não como curinga do SQL
        consulta = consulta.where(Aluno.nome.icontains(termo, autoescape=True))
    return list(db.scalars(consulta))


@router.post(
    "",
    response_model=MatriculaLeitura,
    status_code=status.HTTP_201_CREATED,
    dependencies=[PODE_EDITAR],
)
def matricular(dados: MatriculaEntrada, db: Banco) -> Matricula:
    aluno = db.get(Aluno, dados.aluno_id)
    if aluno is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Aluno não encontrado")
    if not aluno.ativo:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "Aluno inativo não pode ser matriculado. Reative o aluno antes.",
        )
    if tem_matricula_ativa(db, aluno.id):
        raise HTTPException(status.HTTP_409_CONFLICT, JA_MATRICULADO)

    matricula = Matricula(
        aluno=aluno, data_inicio=dados.data_inicio, valor_mensalidade=dados.valor_mensalidade
    )
    db.add(matricula)
    try:
        db.commit()
    except IntegrityError:
        # Duas requisições ao mesmo tempo: a checagem acima passou nas duas, mas o índice
        # único do banco só deixa uma matrícula ativa por aluno
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, JA_MATRICULADO) from None
    return matricula


@router.get("/{matricula_id}", response_model=MatriculaLeitura)
def consultar(matricula_id: MatriculaId, db: Banco) -> Matricula:
    return busca_matricula(db, matricula_id)


@router.patch(
    "/{matricula_id}/encerrar", response_model=MatriculaLeitura, dependencies=[PODE_EDITAR]
)
def encerrar(matricula_id: MatriculaId, dados: MatriculaEncerramento, db: Banco) -> Matricula:
    """Encerra a matrícula. Nada é apagado: o histórico financeiro continua."""
    matricula = busca_matricula(db, matricula_id, bloquear=True)
    if matricula.situacao != SituacaoMatricula.ATIVA:
        raise HTTPException(status.HTTP_409_CONFLICT, "Esta matrícula já está encerrada")
    if dados.data_encerramento < matricula.data_inicio:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "A data de encerramento não pode ser antes do início da matrícula",
        )
    matricula.situacao = SituacaoMatricula.ENCERRADA
    matricula.data_encerramento = dados.data_encerramento
    db.commit()
    return matricula
