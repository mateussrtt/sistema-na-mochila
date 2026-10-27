from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.acesso import LOGADO, PODE_EDITAR
from app.db.session import get_db
from app.models import Responsavel
from app.schemas.comum import ID_MAXIMO, termo_de_busca
from app.schemas.responsavel import ResponsavelEntrada, ResponsavelLeitura

# Todas as rotas exigem login. As que alteram dados exigem perfil de operador ou administrador
router = APIRouter(prefix="/responsaveis", tags=["responsáveis"], dependencies=[LOGADO])

Banco = Annotated[Session, Depends(get_db)]
ResponsavelId = Annotated[int, Path(gt=0, le=ID_MAXIMO)]


def busca_responsavel(db: Session, responsavel_id: int) -> Responsavel:
    responsavel = db.get(Responsavel, responsavel_id)
    if responsavel is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Responsável não encontrado")
    return responsavel


@router.get("", response_model=list[ResponsavelLeitura])
def listar(db: Banco, busca: str | None = None) -> list[Responsavel]:
    """Lista os responsáveis em ordem alfabética, com busca opcional por nome."""
    consulta = select(Responsavel).order_by(Responsavel.nome)
    termo = termo_de_busca(busca)
    if termo:
        consulta = consulta.where(Responsavel.nome.ilike(f"%{termo}%"))
    return list(db.scalars(consulta))


@router.post(
    "",
    response_model=ResponsavelLeitura,
    status_code=status.HTTP_201_CREATED,
    dependencies=[PODE_EDITAR],
)
def cadastrar(dados: ResponsavelEntrada, db: Banco) -> Responsavel:
    responsavel = Responsavel(**dados.model_dump())
    db.add(responsavel)
    db.commit()
    return responsavel


@router.get("/{responsavel_id}", response_model=ResponsavelLeitura)
def consultar(responsavel_id: ResponsavelId, db: Banco) -> Responsavel:
    return busca_responsavel(db, responsavel_id)


@router.put("/{responsavel_id}", response_model=ResponsavelLeitura, dependencies=[PODE_EDITAR])
def editar(responsavel_id: ResponsavelId, dados: ResponsavelEntrada, db: Banco) -> Responsavel:
    responsavel = busca_responsavel(db, responsavel_id)
    for campo, valor in dados.model_dump().items():
        setattr(responsavel, campo, valor)
    db.commit()
    return responsavel
