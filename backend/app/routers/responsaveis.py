from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import Responsavel
from app.schemas.responsavel import ResponsavelEntrada, ResponsavelLeitura

router = APIRouter(prefix="/responsaveis", tags=["responsáveis"])

Banco = Annotated[Session, Depends(get_db)]


def busca_responsavel(db: Session, responsavel_id: int) -> Responsavel:
    responsavel = db.get(Responsavel, responsavel_id)
    if responsavel is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Responsável não encontrado")
    return responsavel


@router.get("", response_model=list[ResponsavelLeitura])
def listar(db: Banco, busca: str | None = None) -> list[Responsavel]:
    """Lista os responsáveis em ordem alfabética, com busca opcional por nome."""
    consulta = select(Responsavel).order_by(Responsavel.nome)
    if busca and busca.strip():
        consulta = consulta.where(Responsavel.nome.ilike(f"%{busca.strip()}%"))
    return list(db.scalars(consulta))


@router.post("", response_model=ResponsavelLeitura, status_code=status.HTTP_201_CREATED)
def cadastrar(dados: ResponsavelEntrada, db: Banco) -> Responsavel:
    responsavel = Responsavel(**dados.model_dump())
    db.add(responsavel)
    db.commit()
    return responsavel


@router.get("/{responsavel_id}", response_model=ResponsavelLeitura)
def consultar(responsavel_id: int, db: Banco) -> Responsavel:
    return busca_responsavel(db, responsavel_id)


@router.put("/{responsavel_id}", response_model=ResponsavelLeitura)
def editar(responsavel_id: int, dados: ResponsavelEntrada, db: Banco) -> Responsavel:
    responsavel = busca_responsavel(db, responsavel_id)
    for campo, valor in dados.model_dump().items():
        setattr(responsavel, campo, valor)
    db.commit()
    return responsavel
