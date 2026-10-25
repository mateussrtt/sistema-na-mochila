from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Path, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from app.db.session import get_db
from app.models import Aluno, Matricula, Responsavel, SituacaoMatricula
from app.schemas.aluno import AlunoEntrada, AlunoLeitura
from app.schemas.comum import ID_MAXIMO, termo_de_busca

router = APIRouter(prefix="/alunos", tags=["alunos"])

Banco = Annotated[Session, Depends(get_db)]
AlunoId = Annotated[int, Path(gt=0, le=ID_MAXIMO)]


def busca_aluno(db: Session, aluno_id: int) -> Aluno:
    aluno = db.get(Aluno, aluno_id, options=[selectinload(Aluno.responsaveis)])
    if aluno is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Aluno não encontrado")
    return aluno


def busca_responsaveis(db: Session, ids: list[int]) -> list[Responsavel]:
    """Confere se todos os responsáveis informados existem."""
    responsaveis = list(db.scalars(select(Responsavel).where(Responsavel.id.in_(ids))))
    if len(responsaveis) != len(ids):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Responsável não encontrado")
    return responsaveis

def encerra_matricula_ativa(db: Session, aluno_id: int) -> None:
    """Encerra a matrícula ativa do aluno, se houver, para ela não gerar mais mensalidades.

    A data de encerramento é hoje. Se a matrícula ainda nem começou, ela é encerrada na
    própria data de início, já que o encerramento não pode vir antes do início.
    """
    matricula = db.scalars(
        select(Matricula)
        .where(Matricula.aluno_id == aluno_id, Matricula.situacao == SituacaoMatricula.ATIVA)
        .with_for_update()
    ).first()
    if matricula is not None:
        matricula.situacao = SituacaoMatricula.ENCERRADA
        matricula.data_encerramento = max(date.today(), matricula.data_inicio)

@router.get("", response_model=list[AlunoLeitura])
def listar(
    db: Banco,
    busca: str | None = None,
    situacao: Literal["ativos", "inativos", "todos"] = "ativos",
) -> list[Aluno]:
    """Lista os alunos em ordem alfabética.

    A busca procura o texto no nome do aluno e no nome dos responsáveis.
    """
    consulta = select(Aluno).options(selectinload(Aluno.responsaveis)).order_by(Aluno.nome)
    if situacao != "todos":
        consulta = consulta.where(Aluno.ativo.is_(situacao == "ativos"))
    termo = termo_de_busca(busca)
    if termo:
        termo = f"%{termo}%"
        consulta = consulta.where(
            or_(Aluno.nome.ilike(termo), Aluno.responsaveis.any(Responsavel.nome.ilike(termo)))
        )
    return list(db.scalars(consulta))


@router.post("", response_model=AlunoLeitura, status_code=status.HTTP_201_CREATED)
def cadastrar(dados: AlunoEntrada, db: Banco) -> Aluno:
    aluno = Aluno(**dados.model_dump(exclude={"responsavel_ids"}))
    aluno.responsaveis = busca_responsaveis(db, dados.responsavel_ids)
    db.add(aluno)
    db.commit()
    return busca_aluno(db, aluno.id)


@router.get("/{aluno_id}", response_model=AlunoLeitura)
def consultar(aluno_id: AlunoId, db: Banco) -> Aluno:
    return busca_aluno(db, aluno_id)


@router.put("/{aluno_id}", response_model=AlunoLeitura)
def editar(aluno_id: AlunoId, dados: AlunoEntrada, db: Banco) -> Aluno:
    """Edita o aluno. Para inativar ou reativar, envie "ativo": false ou true.

    Ao inativar, a matrícula ativa do aluno é encerrada junto. Ao reativar, ela não volta:
    é preciso fazer uma nova matrícula.
    """
    aluno = busca_aluno(db, aluno_id)
    if aluno.ativo and not dados.ativo:
        encerra_matricula_ativa(db, aluno.id)
    for campo, valor in dados.model_dump(exclude={"responsavel_ids"}).items():
        setattr(aluno, campo, valor)
    aluno.responsaveis = busca_responsaveis(db, dados.responsavel_ids)
    db.commit()
    return busca_aluno(db, aluno.id)
