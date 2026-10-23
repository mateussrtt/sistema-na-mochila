from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from app.db.session import get_db
from app.models import Aluno, Responsavel
from app.schemas.aluno import AlunoEntrada, AlunoLeitura

router = APIRouter(prefix="/alunos", tags=["alunos"])

Banco = Annotated[Session, Depends(get_db)]


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
    if busca and busca.strip():
        termo = f"%{busca.strip()}%"
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
def consultar(aluno_id: int, db: Banco) -> Aluno:
    return busca_aluno(db, aluno_id)


@router.put("/{aluno_id}", response_model=AlunoLeitura)
def editar(aluno_id: int, dados: AlunoEntrada, db: Banco) -> Aluno:
    """Edita o aluno. Para inativar ou reativar, envie "ativo": false ou true."""
    aluno = busca_aluno(db, aluno_id)
    for campo, valor in dados.model_dump(exclude={"responsavel_ids"}).items():
        setattr(aluno, campo, valor)
    aluno.responsaveis = busca_responsaveis(db, dados.responsavel_ids)
    db.commit()
    return busca_aluno(db, aluno.id)
